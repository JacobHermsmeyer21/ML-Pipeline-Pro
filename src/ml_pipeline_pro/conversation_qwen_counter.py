"""Offline counter for explicitly verified Qwen/Ollama artifact profiles.

Rendering follows Ollama v0.40.2's template/template.go and api/types.go.
Other runtime versions, artifacts and tokenizer files fail closed. No downloads
or HTTP requests occur here. The operator must retain OLLAMA_GO_TEMPLATE=1.
"""

import copy
import hashlib
import json
import math
from decimal import Decimal
from pathlib import Path
from typing import Any

from tokenizers import Tokenizer

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.conversation_model import ConversationModelError
from ml_pipeline_pro.conversation_ollama import OllamaConversationModel
from ml_pipeline_pro.conversation_schemas import CONTEXT_BYTES, serialized

MODEL_TAG = "qwen2.5:7b-instruct-q4_K_M"
PROFILE_IDENTITY = {
    "artifact_digest": "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e",
    "runtime_version": "0.40.2",
    # Adapter provenance fingerprints the template's canonical JSON string.
    "template_hash": "78b33556a364c601b7682ec3deee5536919cd9b1873cc5998a99491c6a2f2ddc",
}
TOKENIZER_SHA256 = "c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539"
TOKENIZER_REVISION = "a09a35458c702b33eeacc393d103063234e8bc28"
TOKENIZER_MAX_BYTES = 16 * 1024 * 1024
JSON_TOOLS_TAG = "mlpp-qwen2.5:7b-instruct-q4_K_M-json-tools-v1"
JSON_TOOLS_IDENTITY = {
    "artifact_digest": "abadc4bf8517d77dcc8db312ca98cd7cb43488243048c41f1b5746e031427779",
    "runtime_version": "0.40.2",
    "template_hash": "0369c7c353e38c76a97e3797fffd1a747f1d72a3e63335257207dbfbf406260a",
}
JSON_TOOLS_14B_TAG = "mlpp-qwen2.5:14b-instruct-q4_K_M-json-tools-v1"
JSON_TOOLS_14B_IDENTITY = {
    "artifact_digest": "301937bac934530eeb283ab7de177df497a1aba4cfc0b87c9286c78062dbe778",
    "runtime_version": "0.40.2",
    "template_hash": "0369c7c353e38c76a97e3797fffd1a747f1d72a3e63335257207dbfbf406260a",
}
PROFILES = {
    MODEL_TAG: PROFILE_IDENTITY,
    JSON_TOOLS_TAG: JSON_TOOLS_IDENTITY,
    JSON_TOOLS_14B_TAG: JSON_TOOLS_14B_IDENTITY,
}

TOOLS_PREFIX = (
    "\n\n# Tools\n\nYou may call one or more functions to assist with the user query."
    "\n\nYou are provided with function signatures within <tools></tools> XML tags:\n<tools>"
)
TOOLS_SUFFIX = (
    "\n</tools>\n\nFor each function call, return a json object with function name and "
    "arguments within <tool_call></tool_call> XML tags:\n<tool_call>\n"
    '{"name": <function-name>, "arguments": <args-json-object>}\n</tool_call>'
)


def _unsupported() -> ConversationModelError:
    return ConversationModelError(
        "model_unavailable", "Verified Qwen counter profile is unavailable"
    )


def _float_text(value: float, *, general: bool = False) -> str:
    if not math.isfinite(value):
        raise ValueError("Nonfinite number")
    if value == 0:
        return "-0" if math.copysign(1, value) < 0 else "0"
    lower, upper = (1e-4, 1e6) if general else (1e-6, 1e21)
    decimal = Decimal(repr(value))
    if lower <= abs(value) < upper:
        text = format(decimal, "f")
        return text.rstrip("0").rstrip(".") if "." in text else text
    mantissa, exponent = format(decimal, "e").split("e")
    if "." in mantissa:
        mantissa = mantissa.rstrip("0").rstrip(".")
    number = int(exponent)
    digits = str(abs(number)).zfill(2) if general else str(abs(number))
    return mantissa + "e" + ("+" if number >= 0 else "-") + digits


def _dynamic(value: Any) -> Any:
    """Go JSON maps sort keys; numbers in interface values decode to float64."""
    if isinstance(value, dict):
        return {key: _dynamic(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_dynamic(item) for item in value]
    if isinstance(value, int) and not isinstance(value, bool):
        if abs(value) > 2**53:
            raise ValueError("Integer exceeds exact profile range")
        return float(value)
    return value


def _go_json(value: Any) -> str:
    if isinstance(value, str):
        return (
            json.dumps(value, ensure_ascii=False)
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("&", "\\u0026")
            .replace("\u2028", "\\u2028")
            .replace("\u2029", "\\u2029")
        )
    if isinstance(value, dict):
        return (
            "{"
            + ",".join(_go_json(key) + ":" + _go_json(item) for key, item in value.items())
            + "}"
        )
    if isinstance(value, list):
        return "[" + ",".join(_go_json(item) for item in value) + "]"
    if isinstance(value, float):
        return _float_text(value)
    return json.dumps(value, separators=(",", ":"), allow_nan=False)


def _go_value(value: Any) -> str:
    if value is None:
        return "<nil>"
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "map[" + " ".join(key + ":" + _go_value(value[key]) for key in sorted(value)) + "]"
    if isinstance(value, list):
        return "[" + " ".join(_go_value(item) for item in value) + "]"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _float_text(float(value), general=True)
    return _go_json(value)


def _property(value: dict[str, Any]) -> dict[str, Any]:
    """Project onto the pinned runtime's typed ToolProperty fields in Go order."""
    result = {}
    for name in ("anyOf", "type", "items", "description", "enum", "properties", "required"):
        item = value.get(name)
        if item is None or (name not in ("items", "properties") and not item):
            continue
        if name == "anyOf":
            item = [_property(child) for child in item]
        elif name == "properties":
            # Nested ToolPropertiesMap preserves its incoming key order.
            item = {key: _property(child) for key, child in item.items()}
        elif name == "type" and isinstance(item, list) and len(item) == 1:
            item = item[0]
        elif name in ("items", "enum"):
            item = _dynamic(item)
        result[name] = item
    return result


def _function(tool: dict[str, Any], *, json_tools: bool) -> str:
    function = tool["function"]
    params = function.get("parameters") or {}
    properties = params.get("properties")
    projected = (
        {key: _property(properties[key]) for key in sorted(properties)}
        if properties is not None
        else {}
    )
    if json_tools:
        parameters = {"type": params.get("type", "")}
        for name in ("$defs", "items"):
            if params.get(name) is not None:
                parameters[name] = _dynamic(params[name])
        if params.get("required"):
            parameters["required"] = params["required"]
        parameters["properties"] = projected if properties is not None else None
        return _go_json(
            {
                "name": function.get("name", ""),
                "description": function.get("description", ""),
                "parameters": parameters,
            }
        )
    parameters = (
        "{"
        + params.get("type", "")
        + " "
        + _go_value(_dynamic(params.get("$defs")))
        + " "
        + _go_value(_dynamic(params.get("items")))
        + " "
        + _go_value(params.get("required") or [])
        + " "
        + _go_json(projected)
        + "}"
    )
    # This runtime's templateToolFunction has no String() method. fmt renders
    # the struct's fields, rather than JSON. Mirror the measured runtime exactly.
    return (
        "{"
        + function.get("name", "")
        + " "
        + function.get("description", "")
        + " "
        + parameters
        + "}"
    )


def render_qwen_request(payload: dict[str, Any]) -> str:
    """Render only bounded text requests with explicit system instructions."""
    if len(serialized(payload)) > CONTEXT_BYTES or payload.get("model") not in PROFILES:
        raise ValueError("Unsupported or oversized request")
    messages = copy.deepcopy(payload["messages"])
    if not messages or messages[0]["role"] != "system":
        raise ValueError("Explicit initial system instructions required")
    if any(message.get("images") or message.get("thinking") for message in messages):
        raise ValueError("Text-only nonthinking profile")
    if payload.get("think") not in (None, False):
        raise ValueError("Thinking is unsupported")
    system = "\n\n".join(
        message.get("content", "") for message in messages if message["role"] == "system"
    )
    collated = []
    for message in messages:
        if collated and collated[-1]["role"] == message["role"] and message["role"] != "tool":
            collated[-1]["content"] = (
                collated[-1].get("content", "") + "\n\n" + message.get("content", "")
            )
        else:
            collated.append(message)
    tools = payload.get("tools") or []
    json_tools = payload["model"] in {JSON_TOOLS_TAG, JSON_TOOLS_14B_TAG}
    output = ""
    if system or tools:
        output = "<|im_start|>system"
        if system:
            output += "\n" + system
        if tools:
            output += (
                TOOLS_PREFIX.replace("one or more functions", "exactly one function per response")
                if json_tools
                else TOOLS_PREFIX
            )
            for tool in tools:
                output += (
                    '\n{"type": "function", "function": '
                    + _function(tool, json_tools=json_tools)
                    + "}"
                )
            output += TOOLS_SUFFIX
        output += "<|im_end|>\n"
    for index, message in enumerate(collated):
        role, content = message["role"], message.get("content", "")
        last = index == len(collated) - 1
        if role == "user":
            output += "<|im_start|>user\n" + content + "<|im_end|>\n"
        elif role == "assistant":
            output += "<|im_start|>assistant\n"
            if content:
                output += content
            elif message.get("tool_calls"):
                output += "<tool_call>\n"
                for call in message["tool_calls"]:
                    function = call["function"]
                    output += (
                        '{"name": "'
                        + function["name"]
                        + '", "arguments": '
                        + _go_json(_dynamic(function["arguments"]))
                        + "}\n"
                    )
                output += "</tool_call>"
            if not last:
                output += "<|im_end|>\n"
        elif role == "tool":
            output += (
                "<|im_start|>user\n<tool_response>\n" + content + "\n</tool_response><|im_end|>\n"
            )
        elif role != "system":
            raise ValueError("Unsupported role")
        if role != "assistant" and last:
            output += "<|im_start|>assistant\n"
    return output


class QwenInputCounter:
    """Load a checksum-pinned tokenizer locally; reject unverified identities."""

    def __init__(self, provenance: dict[str, Any], tokenizer_path: Path):
        identity = PROFILES.get(provenance.get("model_tag"))
        if identity is None or any(provenance.get(key) != value for key, value in identity.items()):
            raise _unsupported()
        try:
            with tokenizer_path.open("rb") as source:
                data = source.read(TOKENIZER_MAX_BYTES + 1)
            if (
                len(data) > TOKENIZER_MAX_BYTES
                or hashlib.sha256(data).hexdigest() != TOKENIZER_SHA256
            ):
                raise _unsupported()
            self.tokenizer = Tokenizer.from_str(data.decode("utf-8"))
            self.tokenizer.no_truncation()
            self.tokenizer.no_padding()
        except (OSError, ValueError) as exc:
            raise _unsupported() from exc
        self.identity = dict(identity)
        self.model_tag = provenance["model_tag"]

    def __call__(self, payload: dict[str, Any]) -> int:
        try:
            if payload.get("model") != self.model_tag:
                raise ValueError("Counter belongs to another artifact profile")
            prompt = render_qwen_request(payload)
            return len(self.tokenizer.encode(prompt, add_special_tokens=False).ids)
        except (KeyError, TypeError, ValueError, UnicodeError) as exc:
            raise _unsupported() from exc


class QwenConversationModel:
    """Inspect and bind the verified counter inside the bounded first model call.

    Construction is offline, including when the tokenizer or model tag is absent.
    This keeps direct API startup and audit reads independent of model setup.
    """

    def __init__(self, settings: Settings, tokenizer_path: Path):
        self.settings = settings.model_copy(deep=True)
        self.tokenizer_path = tokenizer_path
        self.provenance: dict[str, Any] = {"backend": "ollama", "model_tag": settings.chat_model}
        self._native: OllamaConversationModel | None = None
        self._counter: QwenInputCounter | None = None
        self._closed = False

    def _count(self, payload: dict[str, Any]) -> int:
        if self._counter is None:
            raise _unsupported()
        return self._counter(payload)

    async def generate(self, messages: list[dict[str, Any]]):
        return await self._generate(messages, snippet=False)

    async def generate_snippet(self, messages: list[dict[str, Any]]):
        return await self._generate(messages, snippet=True)

    async def generate_monitoring(self, messages: list[dict[str, Any]]):
        return await self._generate(messages, snippet=False, monitoring=True)

    async def _generate(
        self, messages: list[dict[str, Any]], *, snippet: bool, monitoring: bool = False
    ):
        if self._closed or self.settings.chat_model is None:
            raise _unsupported()
        if self._native is None:
            self._native = OllamaConversationModel(self.settings, count_input_tokens=self._count)
        try:
            await self._native.prepare()
            if self._counter is None:
                self._counter = QwenInputCounter(self._native.provenance, self.tokenizer_path)
            if monitoring:
                return await self._native.generate_monitoring(messages)
            if snippet:
                return await self._native.generate_snippet(messages)
            return await self._native.generate(messages)
        finally:
            self.provenance.update(self._native.provenance)

    async def close(self):
        self._closed = True
        if self._native is not None:
            await self._native.close()
