import asyncio
import json
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from pymongo.errors import ConnectionFailure

from evaluations.test_snippet_model import EvaluatedModel
from ml_pipeline_pro.conversation_model import ConversationModelError, native_conversation_tools
from ml_pipeline_pro.conversation_schemas import ChatRequest, ModelStep, fingerprint
from ml_pipeline_pro.conversation_service import ConversationService
from ml_pipeline_pro.errors import ApiError
from ml_pipeline_pro.snippet_generation import SNIPPET_INSTRUCTIONS
from ml_pipeline_pro.snippet_schemas import SnippetCandidate
from tests.conversation_memory import MemoryConversations
from tests.test_conversation_ollama import Runtime, chat_response, settings
from tests.test_conversation_service import (
    CONTEXT,
    KEY,
    RecordsTransport,
    ScriptedModel,
    call,
    config,
    run,
)
from tests.test_snippet_validation import example, request


class Generator(ScriptedModel):
    def __init__(self, candidate=None, *, profile="list_experiments", inputs=None):
        value = request(profile)
        super().__init__(
            call(
                "generate_pipeline_snippet",
                profile=profile,
                inputs=value.inputs if inputs is None else inputs,
            )
        )
        self.generate_snippet = AsyncMock(
            return_value=candidate
            or ModelStep(
                snippet=SnippetCandidate(code=example(value)),
                usage={"input_tokens": 42, "output_tokens": 100},
            )
        )
        self.provenance.update(
            artifact_digest="a" * 64,
            runtime_version="fixture-runtime",
            instructions_hash="conversation-instructions",
        )


@pytest.mark.parametrize(
    "profile", ["list_experiments", "compare_experiments", "create_experiment", "create_tuning_job"]
)
def test_profile_is_saved_review_required_with_observed_provenance_and_no_domain_call(profile):
    model = Generator(profile=profile)
    result, store, transport = run(model)
    assert result.status == "completed" and result.pending_action is None
    assert result.snippet.status == "validated" and result.snippet.review_required is True
    assert result.snippet.code == example(request(profile))
    assert result.snippet.provenance["instructions_hash"] == fingerprint(SNIPPET_INSTRUCTIONS)
    assert result.snippet.provenance["safe_input_hash"] == fingerprint(
        request(profile).model_dump()
    )
    assert result.snippet.provenance["input_tokens"] == 42
    assert result.snippet.provenance["output_tokens"] == 100
    assert result.snippet.provenance["artifact_digest"] == "a" * 64
    assert result.snippet.provenance["duration_seconds"] >= 0
    assert transport.calls == [] and result.tool_results == []
    assert all(item.pending_action is None for item in store.turns.values())
    model.generate_snippet.assert_awaited_once()


@pytest.mark.parametrize(
    "inputs, locations",
    [
        (
            {},
            {
                "inputs.dataset_id",
                "inputs.model_id",
                "inputs.config.max_runtime_seconds",
                "inputs.objective_metric",
                "inputs.limits.max_trials",
                "inputs.limits.max_runtime_seconds",
            },
        ),
        (
            {"dataset_id": "dataset", "model_id": "model", "config": {}, "limits": {}},
            {
                "inputs.config.max_runtime_seconds",
                "inputs.objective_metric",
                "inputs.limits.max_trials",
                "inputs.limits.max_runtime_seconds",
            },
        ),
    ],
)
def test_missing_inputs_clarify_without_generation_or_dispatch(inputs, locations):
    model = Generator(profile="create_tuning_job", inputs=inputs)
    result, _, transport = run(model)
    assert result.status == "needs_input" and set(result.required_inputs) == locations
    assert result.snippet is None and result.pending_action is None
    model.generate_snippet.assert_not_awaited()
    assert transport.calls == []


@pytest.mark.parametrize(
    "code, issue",
    [
        ("import subprocess\nsubprocess.run(['echo', 'unsafe'])", "snippet_grammar_or_api_invalid"),
        (example() + f"# {KEY}", "snippet_secret_rejected"),
        ("x" * 8193, "snippet_size_invalid"),
    ],
)
def test_rejected_output_saves_fixed_issue_and_never_raw_code_or_secrets(code, issue):
    model = Generator(ModelStep(snippet=SnippetCandidate(code=code)))
    result, _, transport = run(model)
    assert result.status == "completed" and result.snippet.status == "rejected"
    assert result.snippet.validation_issues == [issue] and result.snippet.code is None
    assert KEY not in json.dumps(result.model_dump(mode="json"))
    assert transport.calls == [] and result.pending_action is None


def test_no_new_model_budget_is_granted_to_generation():
    model = Generator()
    result, _, _ = run(model, settings=config(chat_max_model_calls=1))
    assert result.status == "failed" and result.error["code"] == "chat_limit_exceeded"
    assert result.snippet.status == "rejected"
    model.generate_snippet.assert_not_awaited()


def test_original_turn_deadline_is_preserved_before_generation():
    async def scenario():
        store, model = MemoryConversations(), Generator()
        started = datetime.now(UTC)
        ticks = iter([started, started, started + timedelta(seconds=61)])
        service = ConversationService(
            config(), store, model, RecordsTransport({}), clock=lambda: next(ticks)
        )
        with pytest.raises(ApiError) as caught:
            await service.chat(
                CONTEXT,
                ChatRequest(request_id="deadline", message="Generate Python", expected_revision=0),
            )
        assert caught.value.code == "chat_timeout"
        model.generate_snippet.assert_not_awaited()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "output",
    [
        ModelStep(snippet=SnippetCandidate(code=example()), usage={"output_tokens": 1025}),
        ModelStep(snippet=SnippetCandidate(code=example()), usage={"input_tokens": True}),
        ConversationModelError("model_unavailable", "fixed error"),
    ],
)
def test_invalid_usage_or_unavailable_generator_records_failure_without_code(output):
    model = Generator()
    if isinstance(output, Exception):
        model.generate_snippet.side_effect = output
    else:
        model.generate_snippet.return_value = output
    result, _, transport = run(model)
    assert result.status == "failed" and result.snippet.code is None
    assert result.snippet.status == "rejected" and transport.calls == []


def test_saved_draft_replays_with_original_provenance_after_restart():
    async def scenario():
        store, model = MemoryConversations(), Generator()
        body = ChatRequest(request_id="replay", message="Generate Python", expected_revision=0)
        first = await ConversationService(config(), store, model, RecordsTransport({})).chat(
            CONTEXT, body
        )
        replay = await ConversationService(config(), store, None, RecordsTransport({})).chat(
            CONTEXT, body
        )
        assert replay == first and replay.snippet.provenance == first.snippet.provenance
        model.generate_snippet.assert_awaited_once()
        assert len(model.messages) == 1

    asyncio.run(scenario())


def test_storage_failure_returns_safe_boundary_error_without_claiming_a_saved_draft():
    store = MemoryConversations()
    store.finish = AsyncMock(side_effect=ConnectionFailure("private-connection-details"))
    with pytest.raises(ApiError) as caught:
        run(Generator(), store=store)
    assert caught.value.code == "storage_unavailable"
    assert "private-connection-details" not in str(caught.value)


def test_sdk_generation_counts_exact_tool_free_payload_and_closes_credential_isolated_clients(
    monkeypatch,
):
    monkeypatch.setenv("OLLAMA_API_KEY", "inherited-secret")
    runtime = Runtime(
        chat_response(message={"role": "assistant", "content": json.dumps({"code": example()})})
    )

    async def scenario():
        async with runtime.model() as model:
            step = await model.generate_snippet([{"role": "user", "content": "Generate a listing"}])
            assert step.snippet.code == example() and step.usage == {
                "input_tokens": 42,
                "output_tokens": 18,
            }
        assert model._http.is_closed and model._model._client._client.is_closed

    asyncio.run(scenario())
    payload = json.loads(runtime.requests[-1].content)
    assert payload == runtime.token_requests[0]
    assert payload.get("tools", []) == []
    assert payload["messages"][0]["content"] == SNIPPET_INSTRUCTIONS
    assert all("authorization" not in item.headers for item in runtime.requests)


@pytest.mark.parametrize(
    "content",
    [
        '{"code":"pass","code":"print(1)"}',
        '{"code":"pass","review_required":false}',
        "```python\npass\n```",
    ],
)
def test_sdk_rejects_duplicate_keys_extra_authority_and_markdown(content):
    runtime = Runtime(chat_response(message={"role": "assistant", "content": content}))

    async def scenario():
        async with runtime.model() as model:
            with pytest.raises(ConversationModelError) as caught:
                await model.generate_snippet([])
            assert caught.value.code == "model_invalid_response"

    asyncio.run(scenario())


def test_snippet_token_admission_reserves_output_before_dispatch():
    runtime = Runtime()
    runtime.tokens = 7681

    async def scenario():
        async with runtime.model(settings(chat_max_output_tokens=512)) as model:
            with pytest.raises(ConversationModelError) as caught:
                await model.generate_snippet([])
            assert caught.value.code == "chat_limit_exceeded"

    asyncio.run(scenario())
    assert len(runtime.requests) == 3 and runtime.token_requests[0].get("tools", []) == []


def test_host_catalog_keeps_generation_out_of_public_domain_dispatch():
    functions = {item["function"]["name"] for item in native_conversation_tools()}
    assert "generate_pipeline_snippet" in functions
    from ml_pipeline_pro.tools import tool_catalog

    assert "generate_pipeline_snippet" not in {item.name for item in tool_catalog()}


def test_sdk_receives_nested_profile_contracts_and_multiline_generation_example():
    runtime = Runtime(
        chat_response(message={"role": "assistant", "content": json.dumps({"code": example()})})
    )

    async def scenario():
        async with runtime.model() as model:
            await model.generate([])

    # Inspect native binding with a normal completion response.
    runtime.reply = chat_response()
    asyncio.run(scenario())
    functions = {
        item["function"]["name"]: item["function"] for item in runtime.token_requests[0]["tools"]
    }
    schema = functions["generate_pipeline_snippet"]["parameters"]
    assert "CreateTuningArguments" in schema["$defs"]
    assert "objective_metric" in schema["$defs"]["CreateTuningArguments"]["required"]
    assert "NESTED" in schema["properties"]["inputs"]["description"]
    assert "never dotted property names" in schema["properties"]["inputs"]["description"]
    assert "with' after a semicolon" in SNIPPET_INSTRUCTIONS


def test_routing_model_cannot_bypass_host_request_with_direct_code():
    model = ScriptedModel(ModelStep(snippet=SnippetCandidate(code=example())))
    result, _, transport = run(model)
    assert result.status == "failed" and result.error["code"] == "model_invalid_response"
    assert result.snippet is None and result.pending_action is None and transport.calls == []


def test_unsupported_profile_rejects_before_generation_or_domain_dispatch():
    model = Generator()
    model.steps = [call("generate_pipeline_snippet", profile="deploy_shell", inputs={})]
    result, _, transport = run(model)
    assert result.status == "failed" and result.error["code"] == "model_invalid_response"
    assert result.snippet is None and transport.calls == [] and result.pending_action is None
    model.generate_snippet.assert_not_awaited()


def test_seventh_live_generation_is_admitted_and_eighth_never_reaches_model():
    async def scenario():
        native = Generator()
        native._redact = lambda value: value  # Credential-free scripted fixture only.
        observed = {}
        candidate = native.generate_snippet.return_value

        async def generate(messages):
            observed["last_count"] = 42  # Simulate the hook for this invocation.
            return candidate

        native.generate_snippet.side_effect = generate
        model = EvaluatedModel(native, observed, config(), time.monotonic() + 120)
        model.generation_calls = 6
        await model.generate_snippet([])
        with pytest.raises(AssertionError, match="Seven-generation limit"):
            await model.generate_snippet([])
        native.generate_snippet.assert_awaited_once()
        assert len(model.calls) == 1 and model.generation_calls == 7

    asyncio.run(scenario())


def test_live_suite_reserves_full_call_time_before_generation():
    async def scenario():
        native = Generator()
        model = EvaluatedModel(native, {"last_count": 42}, config(), time.monotonic() + 1)
        with pytest.raises(AssertionError, match="Suite deadline"):
            await model.generate_snippet([])
        native.generate_snippet.assert_not_awaited()
        assert model.calls == [] and model.generation_calls == 0

    asyncio.run(scenario())
