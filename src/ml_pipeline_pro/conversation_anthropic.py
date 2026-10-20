"""Claude inference through the Anthropic API; the host validates and dispatches proposals."""

import asyncio
import json
from collections import OrderedDict
from importlib.metadata import version
from typing import Any

import anthropic
from pydantic import ValidationError

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.conversation_model import (
    REPLY_INSTRUCTIONS,
    ConversationModelError,
    native_conversation_tools,
)
from ml_pipeline_pro.conversation_schemas import (
    CONTEXT_BYTES,
    ModelReply,
    ModelStep,
    fingerprint,
    serialized,
)
from ml_pipeline_pro.conversation_timing import timed_boundary
from ml_pipeline_pro.logging import JsonFormatter, configured_secrets
from ml_pipeline_pro.monitoring import MONITORING_INSTRUCTIONS
from ml_pipeline_pro.monitoring_schemas import MonitoringAdvice, MonitoringStep
from ml_pipeline_pro.snippet_generation import snippet_instructions
from ml_pipeline_pro.snippet_schemas import SnippetCandidate
from ml_pipeline_pro.tool_schemas import ToolCall

FALLBACK_BETA = "server-side-fallback-2026-07-01"
# In-turn tool calls replayed with their original thinking blocks, bounded per process.
REPLAY_ENTRIES = 256


def _invalid() -> ConversationModelError:
    return ConversationModelError("model_invalid_response", "Claude returned invalid output")


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


def _replayable(content: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """After a mid-output fallback, model-internal blocks before the boundary are not echoed."""
    boundaries = [index for index, block in enumerate(content) if block["type"] == "fallback"]
    if not boundaries:
        return content
    last = boundaries[-1]
    dropped = {"thinking", "redacted_thinking", "tool_use"}
    return [
        block
        for index, block in enumerate(content)
        if block["type"] != "fallback" and (index > last or block["type"] not in dropped)
    ]


class AnthropicConversationModel:
    """No network at construction; one bounded Messages request per step; no tool execution.

    Thinking is adaptive and always on for current Claude models, so an assistant
    tool call is replayed with the exact content Claude produced, including its
    thinking blocks, for the rest of that turn.
    """

    def __init__(self, settings: Settings, *, client: Any | None = None):
        if settings.anthropic_api_key is None or settings.chat_model is None:
            raise ConversationModelError(
                "model_unavailable", "Claude API key and model are required"
            )
        self._settings = settings.model_copy(deep=True)
        self._redactor = JsonFormatter(configured_secrets(settings))
        self._closed = False
        self._client = client or anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key.get_secret_value(),
            timeout=settings.chat_model_timeout_seconds or 600.0,
            max_retries=1,
        )
        self._tools = [
            {
                "name": item["function"]["name"],
                "description": item["function"]["description"],
                "input_schema": item["function"]["parameters"],
            }
            for item in native_conversation_tools()
        ]
        self._replay: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
        self.provenance: dict[str, Any] = {
            "backend": "anthropic",
            "model": settings.chat_model,
            "effort": settings.chat_effort,
            "packages": {"anthropic": version("anthropic")},
            "context_tokens": settings.chat_context_tokens,
            "max_output_tokens": settings.chat_max_output_tokens,
            "tools_hash": fingerprint(self._tools),
            "instructions_hash": fingerprint(REPLY_INSTRUCTIONS),
        }

    async def prepare(self) -> None:
        if self._closed:
            raise ConversationModelError("model_unavailable", "Claude client is closed")

    async def close(self) -> None:
        if not self._closed:
            self._closed = True
            await self._client.close()

    def _redact(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {self._redactor.redact(key): self._redact(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._redact(item) for item in value]
        return self._redactor.redact(value)

    def _convert(
        self, instructions: str, messages: list[dict[str, Any]]
    ) -> tuple[str, list[dict[str, Any]]]:
        """Map host messages to a system prompt plus Anthropic user/assistant turns."""
        system = [instructions]
        converted: list[dict[str, Any]] = []
        call_ids: dict[str, str] = {}
        for message in messages:
            role = message["role"]
            if role == "system":
                system.append(message["content"])
            elif role == "user":
                converted.append({"role": "user", "content": message["content"]})
            elif role == "assistant" and message.get("tool_calls"):
                (call,) = message["tool_calls"]
                original = self._replay.get(fingerprint([converted, call["name"], call["args"]]))
                if original is None:
                    blocks = [
                        {
                            "type": "tool_use",
                            "id": call["id"],
                            "name": call["name"],
                            "input": call["args"],
                        }
                    ]
                else:
                    blocks = original
                tool_use = next(block for block in blocks if block["type"] == "tool_use")
                call_ids[call["id"]] = tool_use["id"]
                converted.append({"role": "assistant", "content": blocks})
            elif role == "assistant":
                converted.append({"role": "assistant", "content": message["content"]})
            elif role == "tool":
                converted.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": call_ids[message["tool_call_id"]],
                                "content": message["content"],
                            }
                        ],
                    }
                )
            else:
                raise ValueError
        if not converted or converted[0]["role"] != "user":
            raise ValueError
        return "\n\n".join(system), converted

    def _remember(self, prefix: list[dict[str, Any]], call: ToolCall, content: list) -> None:
        self._replay[fingerprint([prefix, call.name, call.arguments])] = content
        while len(self._replay) > REPLAY_ENTRIES:
            self._replay.popitem(last=False)

    async def generate(self, messages: list[dict[str, Any]]) -> ModelStep:
        return await self._generate(messages, kind="native")

    async def generate_snippet(self, messages: list[dict[str, Any]]) -> ModelStep:
        return await self._generate(messages, kind="snippet")

    async def generate_monitoring(self, messages: list[dict[str, Any]]) -> MonitoringStep:
        return await self._generate(messages, kind="monitoring")

    async def _generate(self, messages: list[dict[str, Any]], *, kind: str):
        with timed_boundary("model_inference"):
            try:
                return await self._generate_step(messages, kind=kind)
            except ConversationModelError:
                raise
            except (TimeoutError, anthropic.APITimeoutError):
                raise ConversationModelError("chat_timeout", "Claude request timed out") from None
            except (anthropic.AuthenticationError, anthropic.PermissionDeniedError):
                raise ConversationModelError(
                    "model_unavailable", "Claude API key was rejected"
                ) from None
            except anthropic.RateLimitError:
                raise ConversationModelError(
                    "model_unavailable", "Claude API rate limit reached; try again shortly"
                ) from None
            except anthropic.APIStatusError:
                # Status errors can echo prompt content; only fixed text crosses the boundary.
                raise ConversationModelError("model_unavailable", "Claude request failed") from None
            except anthropic.APIConnectionError:
                raise ConversationModelError(
                    "model_unavailable", "Claude API could not be reached"
                ) from None
            except (ValueError, TypeError, KeyError, StopIteration, ValidationError):
                raise _invalid() from None

    async def _generate_step(self, messages: list[dict[str, Any]], *, kind: str):
        if self._closed:
            raise ConversationModelError("model_unavailable", "Claude client is closed")
        instructions = (
            MONITORING_INSTRUCTIONS
            if kind == "monitoring"
            else snippet_instructions(messages)
            if kind == "snippet"
            else REPLY_INSTRUCTIONS
        )
        system, converted = self._convert(instructions, self._redact(messages))
        request: dict[str, Any] = {
            "model": self._settings.chat_model,
            "system": system,
            "messages": converted,
        }
        output_config: dict[str, Any] = {"effort": self._settings.chat_effort}
        if kind == "monitoring":
            schema = MonitoringAdvice.model_json_schema()
            measurements = _json_object(messages[-1]["content"])
            schema["properties"]["observation_ids"]["items"]["enum"] = measurements[
                "observation_ids"
            ]
            output_config["format"] = {
                "type": "json_schema",
                "schema": anthropic.transform_schema(schema),
            }
        elif kind == "snippet":
            output_config["format"] = {
                "type": "json_schema",
                "schema": anthropic.transform_schema(SnippetCandidate),
            }
        else:
            request["tools"] = self._tools
            request["tool_choice"] = {"type": "auto", "disable_parallel_tool_use": True}
        if len(serialized(request)) > CONTEXT_BYTES:
            raise ConversationModelError("chat_limit_exceeded", "Model context exceeds byte limit")
        async with asyncio.timeout(self._settings.chat_model_timeout_seconds):
            with timed_boundary("token_admission"):
                counted = await self._client.beta.messages.count_tokens(
                    **{key: request[key] for key in ("model", "system", "messages")},
                    **({"tools": request["tools"]} if "tools" in request else {}),
                    betas=[FALLBACK_BETA],
                )
            if (
                counted.input_tokens + self._settings.chat_max_output_tokens
                > self._settings.chat_context_tokens
            ):
                raise ConversationModelError(
                    "chat_limit_exceeded", "Model context exceeds token limit"
                )
            response = await self._client.beta.messages.create(
                **request,
                # Thinking and the reply share the admitted output budget.
                max_tokens=self._settings.chat_max_output_tokens,
                thinking={"type": "adaptive"},
                output_config=output_config,
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        if response.stop_reason == "refusal":
            raise ConversationModelError("model_unavailable", "Claude declined this request")
        if response.stop_reason not in {"end_turn", "tool_use"}:
            raise ValueError
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        content = _replayable(
            [
                block.model_dump(mode="json", by_alias=True, exclude_none=True)
                for block in response.content
            ]
        )
        texts = [block["text"] for block in content if block["type"] == "text"]
        calls = [block for block in content if block["type"] == "tool_use"]
        if kind == "monitoring":
            advice = MonitoringAdvice.model_validate(self._redact(_json_object("".join(texts))))
            if calls or not set(advice.observation_ids) <= set(measurements["observation_ids"]):
                raise ValueError
            return MonitoringStep(
                advice=advice,
                usage=usage,
                provenance={
                    "protocol": "monitoring",
                    "instructions_hash": fingerprint(instructions),
                    "tools_hash": fingerprint([]),
                    "request_format_hash": fingerprint(output_config["format"]),
                    "input_context_hash": fingerprint(request),
                },
            )
        if kind == "snippet":
            if calls:
                raise ValueError
            # Raw code is preserved for host validation, as on the local path.
            return ModelStep(
                snippet=SnippetCandidate.model_validate(_json_object("".join(texts))), usage=usage
            )
        if len(calls) > 1:
            raise ValueError
        if calls:
            (call,) = calls
            if call["name"] == "finish_conversation":
                return ModelStep(
                    reply=ModelReply.model_validate(self._redact(call["input"])), usage=usage
                )
            # Argument validation and missing-input guidance belong to the host.
            step = ModelStep(
                call=ToolCall(name=call["name"], arguments=self._redact(call["input"])),
                usage=usage,
            )
            self._remember(converted, step.call, content)
            return step
        return ModelStep(
            reply=ModelReply.model_validate(self._redact(_json_object("".join(texts).strip()))),
            usage=usage,
        )
