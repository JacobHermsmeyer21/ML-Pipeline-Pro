import asyncio
import functools
import json
from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from anthropic.types.beta import BetaMessage

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.conversation_anthropic import AnthropicConversationModel
from ml_pipeline_pro.conversation_api import conversation_clients
from ml_pipeline_pro.conversation_model import REPLY_INSTRUCTIONS, ConversationModelError
from ml_pipeline_pro.logging import configured_secrets


def sync(test):
    """Run an async scenario the way the other conversation tests do."""

    @functools.wraps(test)
    def run(*args, **kwargs):
        return asyncio.run(test(*args, **kwargs))

    return run


KEY = "sk-ant-test-key-that-must-never-leak-0123456789"


def settings(**overrides):
    values = {
        "environment": "test",
        "chat_enabled": True,
        "chat_backend": "anthropic",
        "anthropic_api_key": KEY,
        "chat_context_tokens": 16384,
        **overrides,
    }
    return Settings(_env_file=None, **values)


def message(content, stop_reason="end_turn"):
    return BetaMessage.model_validate(
        {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": "claude-opus-5-5",
            "content": content,
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {"input_tokens": 120, "output_tokens": 30},
        }
    )


class FakeMessages:
    def __init__(self, responses, input_tokens=500):
        self.responses = list(responses)
        self.input_tokens = input_tokens
        self.created = []
        self.counted = []

    async def count_tokens(self, **request):
        self.counted.append(request)
        return SimpleNamespace(input_tokens=self.input_tokens)

    async def create(self, **request):
        self.created.append(request)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeClient:
    def __init__(self, responses, **kwargs):
        self.beta = SimpleNamespace(messages=FakeMessages(responses, **kwargs))
        self.closed = False

    async def close(self):
        self.closed = True


def adapter(responses, **kwargs):
    client = FakeClient(responses, **kwargs)
    return AnthropicConversationModel(settings(), client=client), client.beta.messages


THINKING = {"type": "thinking", "thinking": "", "signature": "sig-1"}
CALL = {"type": "tool_use", "id": "toolu_1", "name": "get_dataset", "input": {"dataset_id": "ds_1"}}
CONTEXT = [
    {"role": "system", "content": "host rules"},
    {"role": "user", "content": "Inspect dataset ds_1"},
]


@sync
async def test_tool_call_uses_auto_choice_adaptive_thinking_and_fallbacks():
    model, api = adapter([message([THINKING, CALL], "tool_use")])
    step = await model.generate(CONTEXT)
    assert step.call.name == "get_dataset" and step.call.arguments == {"dataset_id": "ds_1"}
    (request,) = api.created
    assert request["model"] == "claude-opus-5-5"
    assert request["system"].startswith(REPLY_INSTRUCTIONS) and "host rules" in request["system"]
    assert request["messages"] == [{"role": "user", "content": "Inspect dataset ds_1"}]
    assert request["tool_choice"] == {"type": "auto", "disable_parallel_tool_use": True}
    assert request["thinking"] == {"type": "adaptive"}
    assert request["output_config"] == {"effort": "medium"}
    assert request["fallbacks"] == "default"
    assert request["betas"] == ["server-side-fallback-2026-07-01"]
    assert {tool["name"] for tool in request["tools"]} >= {"get_dataset", "finish_conversation"}


@sync
async def test_finish_conversation_becomes_a_reply():
    reply = {
        "message": "It has 80 training rows.",
        "citations": [],
        "facts": [],
        "required_inputs": [],
    }
    finish = {"type": "tool_use", "id": "toolu_2", "name": "finish_conversation", "input": reply}
    model, _ = adapter([message([finish], "tool_use")])
    step = await model.generate(CONTEXT)
    assert step.reply.message == "It has 80 training rows."


@sync
async def test_tool_continuation_replays_claudes_exact_blocks_and_ids():
    reply = {"message": "Done.", "citations": [], "facts": [], "required_inputs": []}
    finish = {"type": "tool_use", "id": "toolu_2", "name": "finish_conversation", "input": reply}
    model, api = adapter([message([THINKING, CALL], "tool_use"), message([finish], "tool_use")])
    step = await model.generate(CONTEXT)
    continued = [
        *CONTEXT,
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "name": step.call.name,
                    "args": step.call.arguments,
                    "id": "call-1",
                    "type": "tool_call",
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call-1", "name": "get_dataset", "content": '{"ok":true}'},
    ]
    await model.generate(continued)
    messages = api.created[1]["messages"]
    assert messages[1] == {"role": "assistant", "content": [THINKING, CALL]}
    assert messages[2]["content"][0] == {
        "type": "tool_result",
        "tool_use_id": "toolu_1",
        "content": '{"ok":true}',
    }


@sync
async def test_mid_output_fallback_drops_declined_internal_blocks_from_replay():
    declined = {"type": "thinking", "thinking": "", "signature": "declined"}
    boundary = {
        "type": "fallback",
        "from": {"model": "claude-opus-5-5"},
        "to": {"model": "claude-opus-4-8"},
        "trigger": {"type": "refusal", "category": None},
    }
    model, api = adapter(
        [message([declined, boundary, THINKING, CALL], "tool_use"), message([], "end_turn")]
    )
    step = await model.generate(CONTEXT)
    continued = [
        *CONTEXT,
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "name": step.call.name,
                    "args": step.call.arguments,
                    "id": "call-1",
                    "type": "tool_call",
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call-1", "name": "get_dataset", "content": "{}"},
    ]
    with pytest.raises(ConversationModelError):
        await model.generate(continued)
    assert api.created[1]["messages"][1]["content"] == [THINKING, CALL]


@sync
async def test_snippet_uses_structured_output_and_returns_raw_code():
    model, api = adapter([message([{"type": "text", "text": json.dumps({"code": "print(1)"})}])])
    step = await model.generate_snippet([{"role": "user", "content": "{}"}])
    assert step.snippet.code == "print(1)"
    request = api.created[0]
    assert request["output_config"]["format"]["type"] == "json_schema"
    assert "tools" not in request


@sync
async def test_monitoring_ids_are_limited_to_measured_observations():
    advice = {
        "interpretation": "Latency rose.",
        "observation_ids": ["obs_9"],
        "proposed_checks": ["profile_inference"],
    }
    measured = json.dumps({"observation_ids": ["obs_1"]})
    model, api = adapter([message([{"type": "text", "text": json.dumps(advice)}])])
    with pytest.raises(ConversationModelError) as error:
        await model.generate_monitoring([{"role": "user", "content": measured}])
    assert error.value.code == "model_invalid_response"
    schema = api.created[0]["output_config"]["format"]["schema"]
    assert schema["properties"]["observation_ids"]["items"]["enum"] == ["obs_1"]


@sync
async def test_refusal_is_a_fixed_unavailable_error():
    model, _ = adapter([message([], "refusal")])
    with pytest.raises(ConversationModelError) as error:
        await model.generate(CONTEXT)
    assert (error.value.code, str(error.value)) == (
        "model_unavailable",
        "Claude declined this request",
    )


@sync
async def test_token_budget_is_checked_before_any_generation():
    model, api = adapter([], input_tokens=16000)
    with pytest.raises(ConversationModelError) as error:
        await model.generate(CONTEXT)
    assert error.value.code == "chat_limit_exceeded"
    assert api.counted and not api.created


@pytest.mark.parametrize(
    ("raised", "code"),
    [
        (
            anthropic.AuthenticationError(
                f"bad key {KEY}",
                response=httpx2.Response(
                    401, request=httpx2.Request("POST", "https://api.anthropic.com")
                ),
                body=None,
            ),
            "model_unavailable",
        ),
        (
            anthropic.APITimeoutError(request=httpx2.Request("POST", "https://api.anthropic.com")),
            "chat_timeout",
        ),
        (
            anthropic.APIConnectionError(
                request=httpx2.Request("POST", "https://api.anthropic.com")
            ),
            "model_unavailable",
        ),
    ],
)
@sync
async def test_api_errors_map_to_fixed_codes_without_leaking_details(raised, code):
    model, _ = adapter([raised])
    with pytest.raises(ConversationModelError) as error:
        await model.generate(CONTEXT)
    assert error.value.code == code
    assert KEY not in str(error.value) and error.value.__cause__ is None


@sync
async def test_configured_secrets_are_redacted_before_sending():
    model, api = adapter([message([{"type": "text", "text": "{}"}])])
    with pytest.raises(ConversationModelError):
        await model.generate([{"role": "user", "content": f"my key is {KEY}"}])
    assert KEY not in json.dumps(api.created[0]["messages"])
    assert KEY in configured_secrets(settings())


def test_claude_backend_defaults_and_validation():
    assert settings().chat_model == "claude-opus-5-5"
    assert settings(chat_model="claude-haiku-5-5").chat_model == "claude-haiku-5-5"
    for invalid in ({"chat_model": "qwen2.5:7b"}, {"chat_protocol": "guided"}):
        with pytest.raises(ValueError):
            settings(**invalid)
    with pytest.raises(ValueError):
        Settings(_env_file=None, environment="test", chat_model="claude-opus-5-5")


@sync
async def test_clients_build_claude_only_when_a_key_is_configured():
    async with conversation_clients(settings()) as (model, _):
        assert isinstance(model, AnthropicConversationModel)
        assert model.provenance["backend"] == "anthropic" and KEY not in json.dumps(
            model.provenance
        )
    async with conversation_clients(settings(anthropic_api_key=None)) as (model, _):
        assert model is None


@sync
async def test_generation_never_exceeds_the_admitted_output_budget():
    client = FakeClient([message([CALL], "tool_use")])
    model = AnthropicConversationModel(settings(chat_max_output_tokens=4096), client=client)
    await model.generate(CONTEXT)
    # The admission check reserves chat_max_output_tokens; the request must not allow more.
    assert client.beta.messages.created[0]["max_tokens"] == 4096
