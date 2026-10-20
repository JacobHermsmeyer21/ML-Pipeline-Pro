"""LangChain Responses adapter; the host retains evidence, execution and replay."""

import asyncio
from importlib.metadata import version
from time import monotonic

import httpx
from langchain_core.globals import get_debug
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from langsmith import tracing_context
from openai import APITimeoutError, AsyncOpenAI, OpenAI
from pydantic import ValidationError

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.conversation_diagnostics import ReplyValidationError
from ml_pipeline_pro.conversation_grounding import fact_guided_tools
from ml_pipeline_pro.conversation_model import (
    REPLY_INSTRUCTIONS,
    ConversationModelError,
    native_conversation_tools,
)
from ml_pipeline_pro.conversation_ollama import _json_object
from ml_pipeline_pro.conversation_schemas import (
    CONTEXT_BYTES,
    RECORD_BYTES,
    ModelReply,
    ModelStep,
    fingerprint,
)
from ml_pipeline_pro.conversation_timing import timed_boundary
from ml_pipeline_pro.logging import JsonFormatter, configured_secrets
from ml_pipeline_pro.monitoring import MONITORING_INSTRUCTIONS
from ml_pipeline_pro.monitoring_schemas import MonitoringAdvice, MonitoringStep
from ml_pipeline_pro.snippet_generation import snippet_instructions
from ml_pipeline_pro.snippet_schemas import SnippetCandidate
from ml_pipeline_pro.tool_schemas import ToolCall

DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"
OPENAI_REPLY_INSTRUCTIONS = REPLY_INSTRUCTIONS + (
    " If a supplied record ID returns unavailable/404 or access fails, finish with "
    "an explanation and empty required_inputs. An unavailable record is not an "
    "omitted input. Only list required_inputs when the user's requested action "
    "actually lacks those inputs; do not ask to supply an ID already supplied."
)
OPENAI_ORIGIN = "https://api.openai.com/v1"
COUNT_FIELDS = frozenset(
    {
        "model",
        "input",
        "instructions",
        "tools",
        "tool_choice",
        "parallel_tool_calls",
        "text",
        "reasoning",
        "truncation",
    }
)


def _invalid(stage="provider_response", reason="invalid_envelope") -> ReplyValidationError:
    return ReplyValidationError(stage, reason)


def _reply_json(text, stage="reply_schema"):
    try:
        return _json_object(text)
    except (ValueError, TypeError):
        raise _invalid(stage, "invalid_json") from None


class OpenAIConversationModel:
    """No network at construction; admission sees the actual SDK-normalized JSON.

    Optional budget reservations are injected only by the controlled live runner.
    They run before either counting or generation and never expose credentials.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        async_transport=None,
        sync_transport=None,
        budget=None,
        observer=None,
    ):
        self._settings = settings.model_copy(deep=True)
        if not settings.openai_api_key or not settings.openai_api_key.get_secret_value().strip():
            raise ConversationModelError("model_unavailable", "OpenAI API key is not configured")
        self._closed = False
        self._budget = budget
        self._observer = observer
        self._redactor = JsonFormatter(configured_secrets(settings))
        self._tools = native_conversation_tools()
        for tool in self._tools:
            tool["function"]["strict"] = False
        model = settings.chat_model or DEFAULT_OPENAI_MODEL
        common = {
            "api_key": settings.openai_api_key.get_secret_value(),
            "base_url": OPENAI_ORIGIN,
            "organization": "",
            "project": "",
            "max_retries": 0,
            "timeout": settings.chat_model_timeout_seconds,
        }
        self._http = httpx.AsyncClient(
            transport=async_transport or httpx.AsyncHTTPTransport(retries=0),
            timeout=settings.chat_model_timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            event_hooks={"request": [self._admit], "response": [self._check_response]},
        )
        self._sync_http = httpx.Client(
            transport=sync_transport or httpx.HTTPTransport(retries=0),
            timeout=settings.chat_model_timeout_seconds,
            follow_redirects=False,
            trust_env=False,
        )
        self._client = AsyncOpenAI(**common, http_client=self._http)
        self._sync_client = OpenAI(**common, http_client=self._sync_http)
        # The locked SDK inherits OPENAI_CUSTOM_HEADERS even with explicit auth.
        # Isolate the SDK detail here and verify it through actual HTTP tests.
        self._client._custom_headers = {}
        self._sync_client._custom_headers = {}
        self._model = ChatOpenAI(
            model=model,
            api_key=settings.openai_api_key,
            base_url=OPENAI_ORIGIN,
            root_async_client=self._client,
            async_client=self._client.chat.completions,
            root_client=self._sync_client,
            client=self._sync_client.chat.completions,
            use_responses_api=True,
            use_previous_response_id=False,
            reasoning={"effort": "none"},
            service_tier="default",
            store=False,
            max_tokens=settings.chat_max_output_tokens,
            max_retries=0,
            timeout=settings.chat_model_timeout_seconds,
            streaming=False,
            disable_streaming=True,
            cache=False,
            verbose=False,
            callbacks=[],
        )
        self.provenance = {
            "backend": "openai",
            "model_tag": model,
            "protocol": "native",
            "packages": {
                name: version(name) for name in ("langchain-core", "langchain-openai", "openai")
            },
            "context_tokens": settings.chat_context_tokens,
            "max_output_tokens": settings.chat_max_output_tokens,
            "tools_hash": fingerprint(self._tools),
            "instructions_hash": fingerprint(OPENAI_REPLY_INSTRUCTIONS),
        }

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close()

    async def close(self):
        if not self._closed:
            self._closed = True
            try:
                await self._client.close()
            finally:
                self._sync_client.close()

    def _safe(self, value):
        if isinstance(value, dict):
            return {self._redactor.redact(k): self._safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._safe(v) for v in value]
        return self._redactor.redact(value)

    async def _admit(self, request: httpx.Request):
        if (
            request.url.scheme != "https"
            or request.url.host != "api.openai.com"
            or request.url.port not in {None, 443}
            or request.url.query
            or request.url.path not in {"/v1/responses", "/v1/responses/input_tokens"}
        ):
            raise ConversationModelError("model_unavailable", "Unexpected inference endpoint")
        raw_response = request.headers.get("X-Stainless-Raw-Response")
        request.headers.clear()
        if raw_response == "true":
            # LangChain's with_raw_response path needs this SDK control header.
            request.headers["X-Stainless-Raw-Response"] = "true"
        request.headers.update(
            {
                "Host": "api.openai.com",
                "Content-Length": str(len(request.content)),
                "Authorization": "Bearer " + self._settings.openai_api_key.get_secret_value(),
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )
        payload = _json_object(request.content.decode())
        if len(request.content) > CONTEXT_BYTES:
            raise ConversationModelError("chat_limit_exceeded", "Model context exceeds byte limit")
        if request.url.path.endswith("/input_tokens"):
            return
        if (
            payload.get("model") != self.provenance["model_tag"]
            or payload.get("store") is not False
            or payload.get("max_output_tokens") != self._settings.chat_max_output_tokens
            or payload.get("previous_response_id")
            or payload.get("conversation")
        ):
            raise ValueError("Invalid inference request")
        count_payload = {key: val for key, val in payload.items() if key in COUNT_FIELDS}
        # Reserve counting before sending it. A failed/uncertain reservation is retained.
        if self._budget:
            self._budget.reserve_count(len(request.content))
        started = monotonic()
        with timed_boundary("openai_token_count"):
            count = await self._client.responses.input_tokens.count(**count_payload)
        if self._observer:
            self._observer(
                {
                    "kind": "count",
                    "elapsed_seconds": monotonic() - started,
                    "input_tokens": count.input_tokens,
                    "payload_hash": fingerprint(count_payload),
                }
            )
        input_tokens = count.input_tokens
        if type(input_tokens) is not int or not 0 <= input_tokens <= (
            self._settings.chat_context_tokens - self._settings.chat_max_output_tokens
        ):
            raise ConversationModelError("chat_limit_exceeded", "Model context exceeds token limit")
        if self._budget:
            self._budget.reserve_generation(input_tokens, self._settings.chat_max_output_tokens)
        request.extensions["mlpp_generation_started"] = monotonic()

    async def _check_response(self, response: httpx.Response):
        chunks, size = [], 0
        try:
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > RECORD_BYTES:
                    raise _invalid()
                chunks.append(chunk)
        finally:
            await response.aclose()
        response._content = b"".join(chunks)
        try:
            self._validate_response(response)
        except (ValueError, TypeError, KeyError, AttributeError):
            raise _invalid() from None
        if self._observer and "mlpp_generation_started" in response.request.extensions:
            data = _json_object(response.content.decode()) if response.is_success else {}
            self._observer(
                {
                    "kind": "generation",
                    "elapsed_seconds": monotonic()
                    - response.request.extensions["mlpp_generation_started"],
                    "http_status": response.status_code,
                    "response_model": self._safe(data.get("model")),
                    "usage": {
                        key: value
                        for key, value in (data.get("usage") or {}).items()
                        if key in {"input_tokens", "output_tokens", "total_tokens"}
                        and type(value) is int
                        and value >= 0
                    },
                }
            )

    def _validate_response(self, response):
        if not response.is_success:
            return
        if response.request.url.path.endswith("/input_tokens"):
            count = _json_object(response.content.decode()).get("input_tokens")
            if type(count) is not int or count < 0:
                raise ConversationModelError("chat_limit_exceeded", "Invalid input token count")
            return
        data = _reply_json(response.content.decode(), "provider_response")
        if data.get("status") != "completed" or data.get("error") or data.get("incomplete_details"):
            raise _invalid()
        model = data.get("model")
        if not isinstance(model, str) or not (
            model == self.provenance["model_tag"]
            or model.startswith(self.provenance["model_tag"] + "-")
        ):
            raise _invalid()
        usage = data.get("usage", {})
        for key, maximum in (
            (
                "input_tokens",
                self._settings.chat_context_tokens - self._settings.chat_max_output_tokens,
            ),
            ("output_tokens", self._settings.chat_max_output_tokens),
        ):
            if type(usage.get(key)) is not int or not 0 <= usage[key] <= maximum:
                raise _invalid("provider_response", "invalid_usage")
        output = data.get("output")
        if not isinstance(output, list) or len(output) != 1:
            raise _invalid()
        item = output[0]
        if item.get("status") != "completed":
            raise _invalid()
        if item.get("type") == "function_call":
            if item.get("name") not in {t["function"]["name"] for t in self._tools}:
                raise _invalid()
            _reply_json(item["arguments"], "provider_response")
        elif item.get("type") == "message":
            content = item.get("content")
            if (
                item.get("role") != "assistant"
                or not isinstance(content, list)
                or len(content) != 1
            ):
                raise _invalid()
            if content[0].get("type") != "output_text":
                raise _invalid()
            _reply_json(content[0]["text"], "provider_response")
        else:
            raise _invalid()

    async def generate(self, messages):
        return await self._generate(messages)

    async def generate_snippet(self, messages):
        return await self._generate(messages, snippet=True)

    async def generate_monitoring(self, messages):
        return await self._generate(messages, monitoring=True)

    async def _generate(self, messages, *, snippet=False, monitoring=False):
        if self._closed or get_debug():
            raise ConversationModelError(
                "model_unavailable", "Inference is closed or debug is enabled"
            )
        instructions = (
            MONITORING_INSTRUCTIONS
            if monitoring
            else (snippet_instructions(messages) if snippet else OPENAI_REPLY_INSTRUCTIONS)
        )
        context = [{"role": "system", "content": instructions}, *self._safe(messages)]
        request_tools_hash = None
        try:
            if snippet or monitoring:
                schema = (MonitoringAdvice if monitoring else SnippetCandidate).model_json_schema()
                bound = self._model.bind(
                    tools=[],
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": "result",
                            "schema": schema,
                            "strict": False,
                        }
                    },
                )
            else:
                tools = fact_guided_tools(self._tools, context)
                if tools is not self._tools:
                    request_tools_hash = fingerprint(tools)
                bound = self._model.bind_tools(tools, strict=False, parallel_tool_calls=False)
            with timed_boundary("model_inference"), tracing_context(enabled=False):
                async with asyncio.timeout(self._settings.chat_model_timeout_seconds):
                    result = await bound.ainvoke(context, config={"callbacks": []})
            if not isinstance(result, AIMessage) or result.invalid_tool_calls:
                raise _invalid("reply_schema", "invalid_tool_call")
            usage = {key: result.usage_metadata[key] for key in ("input_tokens", "output_tokens")}
            response_model = self._safe(result.response_metadata.get("model_name"))
            generation_usage = {**usage, "response_model": response_model}
            if request_tools_hash:
                generation_usage["tools_hash"] = request_tools_hash
            content = result.content
            if isinstance(content, list):
                content = "".join(i.get("text", "") for i in content if i.get("type") == "text")
            if snippet or monitoring:
                if result.tool_calls:
                    raise _invalid()
                data = _reply_json(content)
                if snippet:
                    return ModelStep(
                        snippet=SnippetCandidate.model_validate(data), usage=generation_usage
                    )
                advice = MonitoringAdvice.model_validate(self._safe(data))
                measured = _json_object(messages[-1]["content"])
                if not set(advice.observation_ids) <= set(measured["observation_ids"]):
                    raise _invalid()
                return MonitoringStep(
                    advice=advice,
                    usage=usage,
                    provenance={
                        "protocol": "monitoring",
                        "instructions_hash": fingerprint(instructions),
                        "tools_hash": fingerprint([]),
                        "request_format_hash": fingerprint(schema),
                        "response_model": response_model,
                    },
                )
            if result.tool_calls:
                if len(result.tool_calls) != 1 or content:
                    raise _invalid("reply_schema", "invalid_tool_call")
                call = result.tool_calls[0]
                if call["name"] == "finish_conversation":
                    return ModelStep(
                        reply=ModelReply.model_validate(self._safe(call["args"])),
                        usage=generation_usage,
                    )
                return ModelStep(
                    call=ToolCall(name=call["name"], arguments=self._safe(call["args"])),
                    usage=generation_usage,
                )
            return ModelStep(
                reply=ModelReply.model_validate(self._safe(_reply_json(content))),
                usage=generation_usage,
            )
        except ConversationModelError:
            raise
        except (TimeoutError, httpx.TimeoutException, APITimeoutError):
            raise ConversationModelError("chat_timeout", "OpenAI inference timed out") from None
        except ValidationError:
            raise _invalid("reply_schema", "invalid_reply_schema") from None
        except (ValueError, TypeError, KeyError):
            raise _invalid("reply_schema", "invalid_reply_schema") from None
        except Exception as exc:
            # Both LangChain and OpenAI wrap HTTP hook errors. Inspect types only;
            # never forward SDK messages, prompts or credential-bearing bodies.
            cause = exc
            for _ in range(8):
                if isinstance(cause, ReplyValidationError):
                    raise ReplyValidationError(
                        cause.details["validation_stage"], cause.details["validation_reason"]
                    ) from None
                if isinstance(cause, ConversationModelError):
                    raise ConversationModelError(cause.code, str(cause)) from None
                if isinstance(cause, (TimeoutError, httpx.TimeoutException, APITimeoutError)):
                    raise ConversationModelError(
                        "chat_timeout", "OpenAI inference timed out"
                    ) from None
                cause = cause.__cause__
                if cause is None:
                    break
            raise ConversationModelError("model_unavailable", "OpenAI inference failed") from None
