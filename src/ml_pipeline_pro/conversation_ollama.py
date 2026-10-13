"""Local LangChain inference only; the host validates and dispatches proposals."""

import asyncio
import hashlib
import json
import re
from collections.abc import Callable
from importlib.metadata import version
from typing import Any

import httpx
from langchain_core.globals import get_debug
from langchain_core.messages import AIMessage
from langchain_ollama import ChatOllama
from langsmith import tracing_context
from pydantic import ValidationError

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.conversation_guidance import (
    GUIDED_NAMES,
    current_evidence_ids,
    draft_request,
    explicit_missing_inputs,
    guided_instructions,
    guided_schema,
    inspection_target,
)
from ml_pipeline_pro.conversation_model import (
    REPLY_INSTRUCTIONS,
    ConversationModelError,
    native_conversation_tools,
)
from ml_pipeline_pro.conversation_schemas import (
    CONTEXT_BYTES,
    RECORD_BYTES,
    ModelReply,
    ModelStep,
    fingerprint,
    serialized,
)
from ml_pipeline_pro.logging import JsonFormatter, configured_secrets
from ml_pipeline_pro.snippet_generation import snippet_instructions
from ml_pipeline_pro.snippet_schemas import SnippetCandidate
from ml_pipeline_pro.tool_schemas import ToolCall


def _invalid() -> ConversationModelError:
    return ConversationModelError("model_invalid_response", "Local model returned invalid output")


def _json_object(text: str) -> dict[str, Any]:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError
            result[key] = value
        return result

    def constant(_):
        raise ValueError

    value = json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    if not isinstance(value, dict):
        raise ValueError
    return value


class OllamaConversationModel:
    """No network at construction, no downloads/retries, and no tool execution.

    Use as an async context manager to verify the installed artifact and close
    both SDK clients. ``count_input_tokens`` must count the complete Ollama
    request using the selected artifact's tokenizer and chat/tool template.
    An absent counter permits inspection but fails closed before inference.
    A generic LangChain/GPT-2 token estimate is not a verified local-model budget.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        count_input_tokens: Callable[[dict[str, Any]], int] | None = None,
        async_transport: httpx.AsyncBaseTransport | None = None,
        sync_transport: httpx.BaseTransport | None = None,
    ):
        if settings.chat_model is None:
            raise ConversationModelError("model_unavailable", "An installed model tag is required")
        self._settings = settings.model_copy(deep=True)
        self._redactor = JsonFormatter(configured_secrets(settings))
        self._count_input_tokens = count_input_tokens
        self._closed = False
        self._prepared = False
        self._tools = native_conversation_tools()
        self._model = ChatOllama(
            model=settings.chat_model,
            base_url=settings.chat_model_origin,
            temperature=0,
            num_ctx=settings.chat_context_tokens,
            num_predict=settings.chat_max_output_tokens,
            reasoning=False,
            validate_model_on_init=False,
            disable_streaming=True,
            cache=False,
            verbose=False,
            callbacks=[],
            client_kwargs={
                "timeout": httpx.Timeout(settings.chat_model_timeout_seconds),
                "follow_redirects": False,
                "trust_env": False,
            },
            async_client_kwargs={
                "transport": async_transport or httpx.AsyncHTTPTransport(retries=0),
                "event_hooks": {
                    "request": [self._admit_chat_request],
                    "response": [self._check_chat_response],
                },
            },
            sync_client_kwargs={"transport": sync_transport or httpx.HTTPTransport(retries=0)},
        )
        # The locked Ollama SDK inherits OLLAMA_API_KEY even for local origins.
        # ChatOllama has no public client-lifecycle API; keep access isolated here.
        self._http = self._model._async_client._client
        self._http.headers.pop("authorization", None)
        self._model._client._client.headers.pop("authorization", None)
        self._bound = self._model.bind_tools(self._tools, stream=False)
        self.provenance: dict[str, Any] = {
            "backend": "ollama",
            "model_tag": settings.chat_model,
            "packages": {
                name: version(name) for name in ("langchain-core", "langchain-ollama", "ollama")
            },
            "context_tokens": settings.chat_context_tokens,
            "max_output_tokens": settings.chat_max_output_tokens,
            "tools_hash": fingerprint(self._tools),
            "instructions_hash": fingerprint(REPLY_INSTRUCTIONS),
        }
        if settings.chat_protocol == "guided":
            self.provenance.update(
                protocol="guided",
                instructions_hash=fingerprint(guided_instructions()),
                tools_hash=fingerprint(guided_schema()),
            )

    async def __aenter__(self):
        try:
            await self.prepare()
        except BaseException:
            await self.close()
            raise
        return self

    async def __aexit__(self, *_):
        await self.close()

    async def close(self) -> None:
        if not self._closed:
            self._closed = True
            try:
                await self._model._async_client.close()
            finally:
                self._model._client.close()

    async def _metadata(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        response = await self._http.request(method, path, **kwargs)
        response.raise_for_status()
        if len(response.content) > RECORD_BYTES:
            raise _invalid()
        return _json_object(response.text)

    async def prepare(self) -> None:
        """Read local identity/capabilities; never pull or load a model."""
        if self._closed:
            raise ConversationModelError("model_unavailable", "Local model client is closed")
        if self._prepared:
            return
        try:
            async with asyncio.timeout(self._settings.chat_model_timeout_seconds):
                tags = await self._metadata("GET", "/api/tags")
                artifact = next(
                    item for item in tags["models"] if item["name"] == self._settings.chat_model
                )
                digest = artifact["digest"]
                if not isinstance(digest, str) or not re.fullmatch(
                    r"(?:sha256:)?[a-f0-9]{64}", digest
                ):
                    raise ValueError
                info = await self._metadata(
                    "POST", "/api/show", json={"model": self._settings.chat_model}
                )
                if info.get("remote_host") or info.get("remote_model"):
                    raise ValueError
                if (
                    not isinstance(info["capabilities"], list)
                    or "tools" not in info["capabilities"]
                ):
                    raise ValueError
                model_info = info["model_info"]
                context = model_info[model_info["general.architecture"] + ".context_length"]
                if type(context) is not int or context < self._settings.chat_context_tokens:
                    raise ValueError
                runtime = (await self._metadata("GET", "/api/version"))["version"]
                if not isinstance(runtime, str) or not re.fullmatch(
                    r"[a-zA-Z0-9._+-]{1,80}", runtime
                ):
                    raise ValueError
                license_text = info.get("license")
                if license_text is not None and not isinstance(license_text, str):
                    raise ValueError
                self.provenance.update(
                    artifact_digest=digest,
                    runtime_version=runtime,
                    supported_context_tokens=context,
                    license_sha256=(
                        hashlib.sha256(license_text.encode()).hexdigest() if license_text else None
                    ),
                    template_hash=fingerprint(info.get("template")),
                )
                self._prepared = True
        except (TimeoutError, httpx.TimeoutException):
            raise ConversationModelError(
                "chat_timeout", "Local model inspection timed out"
            ) from None
        except Exception:
            raise ConversationModelError(
                "model_unavailable", "Installed local tool-calling model could not be verified"
            ) from None

    def _redact(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {self._redactor.redact(key): self._redact(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._redact(item) for item in value]
        return self._redactor.redact(value)

    async def _admit_chat_request(self, request: httpx.Request) -> None:
        if request.url.path != "/api/chat":
            return
        # HTTP hooks see the SDK-normalized payload that actually reaches Ollama.
        payload = _json_object(request.content.decode("utf-8"))
        context = {"messages": payload["messages"], "tools": payload.get("tools", [])}
        if payload.get("format"):
            context["format"] = payload["format"]
        if len(serialized(context)) > CONTEXT_BYTES:
            raise ConversationModelError("chat_limit_exceeded", "Model context exceeds byte limit")
        input_tokens = self._count_input_tokens(payload)
        if type(input_tokens) is not int or input_tokens < 0:
            raise ValueError
        if (
            input_tokens + self._settings.chat_max_output_tokens
            > self._settings.chat_context_tokens
        ):
            raise ConversationModelError("chat_limit_exceeded", "Model context exceeds token limit")

    async def _check_chat_response(self, response: httpx.Response) -> None:
        """Reject partial/malformed native replies before SDK normalization."""
        chunks = []
        size = 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > RECORD_BYTES:
                raise _invalid()
            chunks.append(chunk)
        body = b"".join(chunks)
        # Preserve the bounded decoded body for the SDK's subsequent JSON read.
        # This httpx cache detail is covered by actual SDK/streaming tests.
        response._content = body
        if response.request.url.path != "/api/chat" or not response.is_success:
            return
        try:
            data = _json_object(body.decode("utf-8"))
            if data["done"] is not True or data["done_reason"] != "stop":
                raise ValueError
            if data["model"] != self._settings.chat_model:
                raise ValueError
            message = data["message"]
            if message["role"] != "assistant" or not isinstance(message["content"], str):
                raise ValueError
            calls = message.get("tool_calls", [])
            if not isinstance(calls, list) or len(calls) > 1:
                raise ValueError
            for call in calls:
                if not isinstance(call["function"]["arguments"], dict):
                    raise ValueError
            for field, maximum in (
                (
                    "prompt_eval_count",
                    self._settings.chat_context_tokens - self._settings.chat_max_output_tokens,
                ),
                ("eval_count", self._settings.chat_max_output_tokens),
            ):
                if type(data[field]) is not int or not 0 <= data[field] <= maximum:
                    raise ValueError
        except (ValueError, KeyError, TypeError):
            raise _invalid() from None

    async def generate(self, messages: list[dict[str, Any]]) -> ModelStep:
        return await self._generate(messages, snippet=False)

    async def generate_snippet(self, messages: list[dict[str, Any]]) -> ModelStep:
        return await self._generate(messages, snippet=True)

    async def _generate(self, messages: list[dict[str, Any]], *, snippet: bool) -> ModelStep:
        if self._closed or not self._prepared:
            raise ConversationModelError("model_unavailable", "Local model is not prepared")
        if self._count_input_tokens is None:
            raise ConversationModelError(
                "model_unavailable", "Verified input token counter required"
            )
        if get_debug():
            raise ConversationModelError(
                "model_unavailable", "LangChain debug output must be disabled"
            )
        guided = self._settings.chat_protocol == "guided"
        instructions = (
            snippet_instructions(messages)
            if snippet
            else guided_instructions()
            if guided
            else REPLY_INSTRUCTIONS
        )
        tools = [] if snippet or guided else self._tools
        context = [{"role": "system", "content": instructions}, *self._redact(messages)]
        try:
            payload = {"messages": context, "tools": tools}
            schema = None
            if guided:
                schema = (
                    SnippetCandidate.model_json_schema()
                    if snippet
                    else guided_schema(
                        current_evidence_ids(context),
                        fact_ids=current_evidence_ids(context, facts_only=True),
                        missing_inputs=explicit_missing_inputs(context),
                        target=inspection_target(context),
                        draft=draft_request(context),
                    )
                )
                payload["format"] = schema
            if len(serialized(payload)) > CONTEXT_BYTES:
                raise ConversationModelError(
                    "chat_limit_exceeded", "Model context exceeds byte limit"
                )
            async with asyncio.timeout(self._settings.chat_model_timeout_seconds):
                with tracing_context(enabled=False):
                    bound = (
                        self._model.bind(tools=[], format=schema, stream=False)
                        if guided
                        else self._model.bind_tools([], stream=False)
                        if snippet
                        else self._bound
                    )
                    result = await bound.ainvoke(context, config={"callbacks": []})
            if not isinstance(result, AIMessage) or result.invalid_tool_calls:
                raise ValueError
            usage = {
                "input_tokens": result.usage_metadata["input_tokens"],
                "output_tokens": result.usage_metadata["output_tokens"],
            }
            if snippet:
                if result.tool_calls or not isinstance(result.content, str):
                    raise ValueError
                # Preserve raw code until host validation; known secrets cause rejection,
                # rather than silently rewriting code into an accepted draft.
                return ModelStep(
                    snippet=SnippetCandidate.model_validate(_json_object(result.content)),
                    usage=usage,
                )
            if guided:
                if result.tool_calls or not isinstance(result.content, str):
                    raise ValueError
                envelope = self._redact(_json_object(result.content))
                if set(envelope) not in ({"call"}, {"reply"}):
                    raise ValueError
                step = ModelStep.model_validate({**envelope, "usage": usage})
                if step.call is not None and step.call.name not in GUIDED_NAMES:
                    raise ValueError
                if (
                    draft_request(context)
                    and step.call is not None
                    and step.call.name != "generate_pipeline_snippet"
                ):
                    raise ValueError
                missing_inputs = explicit_missing_inputs(context)
                target = inspection_target(context)
                if missing_inputs and (
                    step.reply is None or tuple(step.reply.required_inputs) != missing_inputs
                ):
                    raise ValueError
                if (
                    not missing_inputs
                    and target
                    and (
                        step.call is None
                        or step.call.name != target[0]
                        or step.call.arguments.get(target[1]) != target[2]
                    )
                ):
                    raise ValueError
                return step
            if result.tool_calls:
                if len(result.tool_calls) != 1:
                    raise ValueError
                call = result.tool_calls[0]
                if call["name"] == "finish_conversation":
                    if result.content != "":
                        raise ValueError
                    return ModelStep(
                        reply=ModelReply.model_validate(self._redact(call["args"])),
                        usage=usage,
                    )
                # Argument validation and missing-input guidance belong to the host.
                return ModelStep(
                    call=ToolCall(name=call["name"], arguments=self._redact(call["args"])),
                    usage=usage,
                )
            if not isinstance(result.content, str):
                raise ValueError
            return ModelStep(
                reply=ModelReply.model_validate(self._redact(_json_object(result.content))),
                usage=usage,
            )
        except ConversationModelError:
            raise
        except (TimeoutError, httpx.TimeoutException):
            raise ConversationModelError(
                "chat_timeout", "Local model inference timed out"
            ) from None
        except (ValueError, TypeError, KeyError, ValidationError):
            raise _invalid() from None
        except Exception:
            # SDK exceptions can embed raw arguments, prompts, and connection URLs.
            raise ConversationModelError(
                "model_unavailable", "Local model inference failed"
            ) from None
