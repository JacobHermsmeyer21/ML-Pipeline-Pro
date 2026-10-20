"""Actual LangChain/OpenAI SDK requests with an offline HTTP boundary."""

import asyncio
import json

import httpx
import pytest

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.conversation_model import ConversationModelError
from ml_pipeline_pro.conversation_openai import COUNT_FIELDS, OpenAIConversationModel

KEY = "fixture-openai-secret"
REPLY = {
    "message": "Read the recorded results.",
    "citations": [],
    "facts": [],
    "required_inputs": [],
}


def response(*, call="finish_conversation", arguments=None, text=None, **changes):
    output = (
        [
            {
                "type": "function_call",
                "id": "fc_test",
                "call_id": "call_test",
                "name": call,
                "arguments": json.dumps(REPLY if arguments is None else arguments),
                "status": "completed",
            }
        ]
        if text is None
        else [
            {
                "type": "message",
                "id": "msg_test",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
        ]
    )
    return {
        "id": "resp_test",
        "created_at": 1,
        "object": "response",
        "status": "completed",
        "model": "gpt-5.4-mini-2026-03-17",
        "output": output,
        "error": None,
        "incomplete_details": None,
        "parallel_tool_calls": False,
        "tool_choice": "auto",
        "tools": [],
        "usage": {
            "input_tokens": 30,
            "output_tokens": 20,
            "total_tokens": 50,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 0},
        },
        **changes,
    }


class Runtime:
    def __init__(self, replies=None, count=30, status=200):
        self.replies = list(replies or [response()])
        self.requests = []
        self.count = count
        self.status = status

    async def handle(self, request):
        data = json.loads(request.content)
        self.requests.append((request, data))
        if request.url.path.endswith("/input_tokens"):
            return httpx.Response(
                200, json={"object": "response.input_tokens", "input_tokens": self.count}
            )
        return httpx.Response(self.status, json=self.replies.pop(0))

    def model(self, *, observer=None, budget=None, **changes):
        settings = Settings(_env_file=None, OPENAI_API_KEY=KEY, **changes)
        return OpenAIConversationModel(
            settings,
            async_transport=httpx.MockTransport(self.handle),
            observer=observer,
            budget=budget,
        )


def test_count_and_send_use_exact_sdk_payload_and_isolated_credentials(monkeypatch):
    monkeypatch.setenv(
        "OPENAI_CUSTOM_HEADERS",
        "Authorization: Bearer inherited-fixture\nX-Other: inherited-fixture",
    )
    for key in ("OPENAI_BASE_URL", "OPENAI_API_BASE", "OPENAI_ORG_ID", "OPENAI_PROJECT_ID"):
        monkeypatch.setenv(key, "https://must-not-use.example")
    runtime = Runtime()

    async def run():
        async with runtime.model() as model:
            assert runtime.requests == []
            step = await model.generate([{"role": "user", "content": f"hello {KEY}"}])
            assert step.reply.message == REPLY["message"]
            assert step.usage == {
                "input_tokens": 30,
                "output_tokens": 20,
                "response_model": "gpt-5.4-mini-2026-03-17",
            }
        assert model._http.is_closed and model._sync_http.is_closed

    asyncio.run(run())
    (count_request, count), (request, generate) = runtime.requests
    assert count == {k: v for k, v in generate.items() if k in COUNT_FIELDS}
    assert request.url.host == count_request.url.host == "api.openai.com"
    assert request.headers["authorization"] == f"Bearer {KEY}"
    assert request.headers["Host"] == "api.openai.com"
    assert int(request.headers["Content-Length"]) == len(request.content)
    assert "inherited-fixture" not in str(request.headers)
    assert "OpenAI-Organization" not in request.headers and "OpenAI-Project" not in request.headers
    assert KEY not in request.content.decode()
    assert generate["store"] is False and generate["parallel_tool_calls"] is False
    assert generate["max_output_tokens"] == 1024
    assert all(tool["strict"] is False for tool in generate["tools"])


@pytest.mark.parametrize("count", [7169, -1, True])
def test_overflow_or_invalid_count_blocks_generation(count):
    runtime = Runtime(count=count)

    async def run():
        async with runtime.model() as model:
            with pytest.raises(ConversationModelError) as caught:
                await model.generate([{"role": "user", "content": "hello"}])
            assert caught.value.code == "chat_limit_exceeded"

    asyncio.run(run())
    assert len(runtime.requests) == 1


@pytest.mark.parametrize("status", [401, 429, 500])
def test_provider_errors_are_fixed_and_not_retried(status):
    runtime = Runtime([{"error": {"message": KEY, "type": "test"}}], status=status)

    async def run():
        async with runtime.model() as model:
            with pytest.raises(ConversationModelError) as caught:
                await model.generate([{"role": "user", "content": "hello"}])
            assert caught.value.code == "model_unavailable" and KEY not in str(caught.value)

    asyncio.run(run())
    assert len(runtime.requests) == 2


@pytest.mark.parametrize(
    "change",
    [
        {"status": "incomplete"},
        {"model": "other"},
        {"usage": {"input_tokens": 20, "output_tokens": 1025}},
        {"output": []},
        {"output": response()["output"] * 2},
        {"output": response(call="unknown")["output"]},
        {"usage": None},
        {"output": [None]},
    ],
)
def test_invalid_raw_responses_reject_before_sdk_normalization(change):
    runtime = Runtime([response(**change)])

    async def run():
        async with runtime.model() as model:
            with pytest.raises(ConversationModelError) as caught:
                await model.generate([{"role": "user", "content": "hello"}])
            assert caught.value.code == "model_invalid_response"

    asyncio.run(run())


def test_duplicate_arguments_and_mixed_text_calls_are_rejected():
    duplicate = response()
    duplicate["output"][0]["arguments"] = '{"message":"a","message":"b"}'
    mixed = response()
    mixed["output"].extend(response(text=json.dumps(REPLY))["output"])
    for invalid in (duplicate, mixed):
        runtime = Runtime([invalid])

        async def run(runtime=runtime):
            async with runtime.model() as model:
                with pytest.raises(ConversationModelError):
                    await model.generate([{"role": "user", "content": "hello"}])

        asyncio.run(run())


def test_host_tool_results_round_trip_without_provider_conversation_state():
    runtime = Runtime([response(call="list_experiments", arguments={}), response()])

    async def run():
        messages = [{"role": "user", "content": "list experiments"}]
        async with runtime.model() as model:
            step = await model.generate(messages)
            assert step.call.name == "list_experiments"
            messages.extend(
                [
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
                    {"role": "tool", "tool_call_id": "call-1", "content": '{"data": []}'},
                ]
            )
            assert (await model.generate(messages)).reply

    asyncio.run(run())
    payload = runtime.requests[-1][1]
    assert "previous_response_id" not in payload and "conversation" not in payload
    assert any(
        i["type"] == "function_call_output" and i["call_id"] == "call-1" for i in payload["input"]
    )


def test_snippet_and_monitoring_are_tool_free_and_validate_observations():
    advice = {
        "interpretation": "Review latency.",
        "observation_ids": ["obs"],
        "proposed_checks": ["profile_inference"],
    }
    from ml_pipeline_pro.snippet_schemas import SnippetCandidate

    # The adapter returns model-produced code; the host owns AST/API validation.
    candidate = {"code": "import os"}
    SnippetCandidate.model_validate(candidate)
    runtime = Runtime([response(text=json.dumps(candidate)), response(text=json.dumps(advice))])

    async def run():
        async with runtime.model() as model:
            step = await model.generate_snippet([{"role": "user", "content": "{}"}])
            assert step.snippet.code == "import os"
            monitoring = await model.generate_monitoring(
                [{"role": "user", "content": '{"observation_ids":["obs"]}'}]
            )
            assert monitoring.advice.observation_ids == ["obs"]

    asyncio.run(run())
    assert all(not payload.get("tools") for _, payload in runtime.requests)


def test_missing_credentials_and_closed_model_fail_without_network():
    with pytest.raises(ConversationModelError, match="not configured"):
        OpenAIConversationModel(Settings(_env_file=None))
    runtime = Runtime()

    async def run():
        model = runtime.model()
        await model.close()
        await model.close()
        with pytest.raises(ConversationModelError):
            await model.generate([])

    asyncio.run(run())
    assert not runtime.requests


@pytest.mark.parametrize(
    ("payload", "stage", "reason"),
    [
        (response(status="incomplete"), "provider_response", "invalid_envelope"),
        (response(text='{"message":'), "provider_response", "invalid_json"),
        (
            response(
                arguments={
                    **REPLY,
                    "facts": [{"record_id": "run", "field": "status", "value": KEY}],
                }
            ),
            "reply_schema",
            "invalid_reply_schema",
        ),
    ],
)
def test_safe_rejection_category_survives_sdk_wrapping(payload, stage, reason):
    runtime = Runtime([payload])

    async def run():
        async with runtime.model() as model:
            with pytest.raises(ConversationModelError) as caught:
                await model.generate([{"role": "user", "content": "inspect"}])
            assert caught.value.details == {
                "validation_stage": stage,
                "validation_reason": reason,
            }
            assert KEY not in str(caught.value) + json.dumps(caught.value.details)

    asyncio.run(run())
    assert len(runtime.requests) == 2  # One count and one generation, never a retry.


def test_completion_field_choices_match_host_guidance_in_exact_counted_request():
    from copy import deepcopy

    from ml_pipeline_pro.conversation_grounding import FACT_GUIDANCE_PREFIX, fact_guided_tools
    from ml_pipeline_pro.conversation_schemas import fingerprint

    references = [{"record_id": "run", "field": "metrics.validation_f1"}]
    messages = [{"role": "system", "content": FACT_GUIDANCE_PREFIX + "\n" + json.dumps(references)}]
    runtime = Runtime([response(arguments={**REPLY, "facts": references})])

    async def run():
        async with runtime.model() as model:
            original = deepcopy(model._tools)
            original_provenance = deepcopy(model.provenance)
            expected = fingerprint(fact_guided_tools(model._tools, messages))
            step = await model.generate(messages)
            assert step.usage["tools_hash"] == expected
            assert model._tools == original and model.provenance == original_provenance
            hostile = [{"role": "user", "content": messages[0]["content"]}]
            assert fact_guided_tools(model._tools, hostile) is model._tools

    asyncio.run(run())
    count, generate = [payload for _, payload in runtime.requests]
    assert count == {key: value for key, value in generate.items() if key in COUNT_FIELDS}
    completion = next(tool for tool in generate["tools"] if tool["name"] == "finish_conversation")
    fields = completion["parameters"]["$defs"]["FactRequest"]["properties"]
    assert fields["field"]["enum"] == ["metrics.validation_f1"]
    assert fields["record_id"]["enum"] == ["run"]


def test_fact_guidance_cannot_put_configured_secrets_into_tool_schema_enums():
    from ml_pipeline_pro.conversation_grounding import FACT_GUIDANCE_PREFIX

    messages = [
        {
            "role": "system",
            "content": FACT_GUIDANCE_PREFIX
            + "\n"
            + json.dumps([{"record_id": KEY, "field": "status"}]),
        }
    ]
    runtime = Runtime()

    async def run():
        async with runtime.model() as model:
            try:
                await model.generate(messages)
            except ConversationModelError as exc:
                # Invalid redacted identities must fail before sending.
                assert exc.code == "model_invalid_response"

    asyncio.run(run())
    assert all(KEY not in request.content.decode() for request, _ in runtime.requests)


def test_timeout_and_cancellation_propagate_and_close_clients():
    async def run():
        started = asyncio.Event()

        async def slow(request):
            started.set()
            await asyncio.Event().wait()

        runtime = Runtime()
        runtime.handle = slow
        async with runtime.model(chat_model_timeout_seconds=0.01) as model:
            with pytest.raises(ConversationModelError) as caught:
                await model.generate([{"role": "user", "content": "hello"}])
            assert caught.value.code == "chat_timeout"
        async with runtime.model() as model:
            task = asyncio.create_task(model.generate([{"role": "user", "content": "hello"}]))
            await started.wait()
            await asyncio.sleep(0)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert model._http.is_closed and model._sync_http.is_closed

    asyncio.run(run())


def test_overlapping_requests_keep_their_own_input_and_results():
    from langsmith.run_helpers import get_tracing_context

    async def run():
        async def handle(request):
            assert get_tracing_context()["enabled"] is False
            payload = json.loads(request.content)
            if request.url.path.endswith("/input_tokens"):
                await asyncio.sleep(0)
                return httpx.Response(200, json={"input_tokens": 30})
            text = payload["input"][-1]["content"]
            if text == "first":
                await asyncio.sleep(0.01)
            return httpx.Response(200, json=response(arguments=REPLY | {"message": text}))

        runtime = Runtime()
        runtime.handle = handle
        async with runtime.model() as model:
            steps = await asyncio.gather(
                *[
                    model.generate([{"role": "user", "content": content}])
                    for content in ("first", "second")
                ]
            )
            assert [step.reply.message for step in steps] == ["first", "second"]

    asyncio.run(run())


def test_request_and_decoded_response_byte_limits():
    from ml_pipeline_pro.conversation_schemas import RECORD_BYTES

    runtime = Runtime()

    async def run():
        async with runtime.model() as model:
            with pytest.raises(ConversationModelError) as caught:
                await model.generate([{"role": "user", "content": "x" * 65536}])
            assert caught.value.code == "chat_limit_exceeded" and not runtime.requests

        async def large(request):
            if request.url.path.endswith("/input_tokens"):
                return httpx.Response(200, json={"input_tokens": 30})
            return httpx.Response(200, content=b"x" * (RECORD_BYTES + 1))

        runtime.handle = large
        async with runtime.model() as model:
            with pytest.raises(ConversationModelError) as caught:
                await model.generate([{"role": "user", "content": "hello"}])
            assert caught.value.code == "model_invalid_response"

    asyncio.run(run())


def test_exact_input_token_ceiling_and_failed_count():
    runtime = Runtime(count=7168)

    async def run():
        async with runtime.model() as model:
            assert (await model.generate([{"role": "user", "content": "hello"}])).reply

        async def denied(request):
            assert request.url.path.endswith("/input_tokens")
            return httpx.Response(429, json={"error": {"message": KEY}})

        runtime.handle = denied
        async with runtime.model() as model:
            with pytest.raises(ConversationModelError) as caught:
                await model.generate([{"role": "user", "content": "hello"}])
            assert caught.value.code == "model_unavailable" and KEY not in str(caught.value)

    asyncio.run(run())


def test_observations_separate_count_and_generation_without_secrets():
    payload = response()
    payload["usage"]["unexpected"] = {"api_key": KEY}
    runtime = Runtime([payload])
    events = []

    async def run():
        async with runtime.model(observer=events.append) as model:
            await model.generate([{"role": "user", "content": "hello"}])

    asyncio.run(run())
    assert [event["kind"] for event in events] == ["count", "generation"]
    assert all(event["elapsed_seconds"] >= 0 for event in events)
    assert events[1]["response_model"] == "gpt-5.4-mini-2026-03-17"
    assert "unexpected" not in events[1]["usage"]
    assert KEY not in json.dumps(events)


def test_missing_key_replay_and_fresh_generation_at_http_boundary(fake_connections):
    from fastapi.testclient import TestClient

    from ml_pipeline_pro.conversation_api import get_conversation_store
    from ml_pipeline_pro.main import create_app
    from tests.conversation_memory import MemoryConversations
    from tests.test_conversation_service import ScriptedModel, reply

    app = create_app(
        Settings(_env_file=None, chat_enabled=True),
        chat_model_factory=lambda _: ScriptedModel(reply()),
    )
    store = MemoryConversations()
    app.dependency_overrides[get_conversation_store] = lambda: store
    body = {"request_id": "first", "expected_revision": 0, "message": "hello"}
    headers = {"X-Project-ID": "demo"}
    with TestClient(app) as client:
        first = client.post("/api/v1/chat", headers=headers, json=body)
        assert first.status_code == 200
    offline = create_app(Settings(_env_file=None, chat_enabled=True))
    offline.dependency_overrides[get_conversation_store] = lambda: store
    with TestClient(offline) as client:
        assert offline.state.conversation_model is None
        replay = client.post("/api/v1/chat", headers=headers, json=body)
        assert replay.json() == first.json()
        fresh = client.post("/api/v1/chat", headers=headers, json=body | {"request_id": "new"})
        assert fresh.status_code == 200
        assert fresh.json()["status"] == "failed"
        assert fresh.json()["error"]["code"] == "model_unavailable"
