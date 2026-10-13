import asyncio
import json

import httpx
import pytest

from ml_pipeline_pro.conversation_guidance import (
    GUIDED_NAMES,
    current_evidence_ids,
    draft_request,
    explicit_missing_inputs,
    guided_schema,
    inspection_target,
)
from ml_pipeline_pro.conversation_model import ConversationModelError, native_conversation_tools
from ml_pipeline_pro.conversation_schemas import CONTEXT_BYTES, ChatRequest
from ml_pipeline_pro.conversation_service import ConversationService
from tests.conversation_memory import MemoryConversations
from tests.test_conversation_ollama import REPLY, Runtime, chat_response, settings
from tests.test_conversation_service import CONTEXT, RecordsTransport, ScriptedModel, config, reply


@pytest.mark.parametrize(
    "envelope",
    [
        {"reply": {**REPLY, "required_inputs": []}},
        {"call": {"name": "get_experiment", "arguments": {"experiment_id": "selected"}}},
        {"call": {"name": "create_experiment", "arguments": {}}},
    ],
)
def test_guided_actual_sdk_sends_one_schema_step_without_native_bindings(envelope):
    async def scenario():
        runtime = Runtime(
            chat_response(
                message={"role": "assistant", "content": json.dumps(envelope)},
                prompt_eval_count=80,
                eval_count=20,
            )
        )
        async with runtime.model(settings(chat_protocol="guided")) as model:
            result = await model.generate([{"role": "user", "content": "Guide me"}])
            if "reply" in envelope:
                assert result.reply.model_dump() == envelope["reply"]
            else:
                assert result.call.model_dump() == envelope["call"]
            payload = json.loads(runtime.requests[-1].content)
            assert payload["tools"] == [] and payload["format"] == guided_schema()
            assert result.usage == {"input_tokens": 80, "output_tokens": 20}
            assert model.provenance["protocol"] == "guided"

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "envelope",
    [
        {},
        {"reply": REPLY, "call": {"name": "get_model", "arguments": {}}},
        {"reply": REPLY, "usage": {"output_tokens": 0}},
        {"call": {"name": "execute_python", "arguments": {}}},
        {"snippet": {"code": "print('unexpected')"}},
    ],
)
def test_guided_rejects_invalid_envelopes_without_output_repair(envelope):
    async def scenario():
        runtime = Runtime(
            chat_response(message={"role": "assistant", "content": json.dumps(envelope)})
        )
        async with runtime.model(settings(chat_protocol="guided")) as model:
            with pytest.raises(ConversationModelError) as caught:
                await model.generate([{"role": "user", "content": "Guide me"}])
            assert caught.value.code == "model_invalid_response"

    asyncio.run(scenario())


def test_guided_admission_counts_transmitted_format_schema_bytes():
    async def scenario():
        runtime = Runtime(
            chat_response(message={"role": "assistant", "content": json.dumps({"reply": REPLY})})
        )
        async with runtime.model(settings(chat_protocol="guided")) as model:
            oversized = httpx.Request(
                "POST",
                "http://127.0.0.1:11434/api/chat",
                json={"messages": [], "tools": [], "format": {"description": "x" * CONTEXT_BYTES}},
            )
            with pytest.raises(ConversationModelError) as caught:
                await model._admit_chat_request(oversized)
            assert caught.value.code == "chat_limit_exceeded"
        assert all(item.url.path != "/api/chat" for item in runtime.requests)

    asyncio.run(scenario())


def test_guided_preserves_historical_data_without_replaying_old_user_instructions():
    async def scenario():
        model = ScriptedModel(
            reply(message="Historical interpretation"), reply(message="Ask inputs")
        )
        service = ConversationService(
            config(chat_protocol="guided"), MemoryConversations(), model, RecordsTransport({})
        )
        first = await service.chat(
            CONTEXT,
            ChatRequest(request_id="first", message="Old budget instruction", expected_revision=0),
        )
        await service.chat(
            CONTEXT,
            ChatRequest(
                request_id="second",
                conversation_id=first.conversation_id,
                expected_revision=1,
                message="Current missing budget",
            ),
        )
        messages = model.messages[-1]
        assert [item["content"] for item in messages if item["role"] == "user"] == [
            "Current missing budget"
        ]
        historical = [
            json.loads(item["content"]) for item in messages if item["role"] == "assistant"
        ]
        assert historical[0]["historical"] is True
        assert historical[0]["interpretation"] == "Historical interpretation"

    asyncio.run(scenario())


def test_guided_names_are_existing_tools_and_do_not_expand_action_permissions():
    assert GUIDED_NAMES <= {item["function"]["name"] for item in native_conversation_tools()}
    assert "cancel_tuning_job" not in GUIDED_NAMES


def test_guided_sdk_schema_uses_only_current_successful_evidence_and_counts_actual_payload():
    async def scenario():
        runtime = Runtime(
            chat_response(message={"role": "assistant", "content": json.dumps({"reply": REPLY})})
        )
        async with runtime.model(settings(chat_protocol="guided")) as model:
            await model.generate(
                [
                    {
                        "role": "assistant",
                        "content": json.dumps(
                            {
                                "historical": True,
                                "evidence": [{"record_id": "old"}],
                            }
                        ),
                    },
                    {"role": "user", "content": "Explain current results"},
                    {
                        "role": "tool",
                        "tool_call_id": "failed",
                        "content": json.dumps(
                            {
                                "status": "error",
                                "evidence": [{"record_id": "foreign", "role": "record"}],
                            }
                        ),
                    },
                    {
                        "role": "tool",
                        "tool_call_id": "current",
                        "content": json.dumps(
                            {
                                "status": "succeeded",
                                "data": {"id": "current"},
                                "evidence": [
                                    {"record_id": "current", "role": "record"},
                                    {"record_id": "parent", "role": "source"},
                                ],
                            }
                        ),
                    },
                ]
            )
            payload = json.loads(runtime.requests[-1].content)
            schema = payload["format"]
            assert schema == guided_schema(("current", "parent"), fact_ids=("current",))
            assert schema["$defs"]["FactRequest"]["properties"]["record_id"]["enum"] == ["current"]
            assert runtime.token_requests[-1] == payload

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "message, expected",
    [
        (
            "Prepare training dataset chosen, model selected, but runtime is missing.",
            ("config.max_runtime_seconds",),
        ),
        (
            "Prepare training dataset chosen, runtime is missing, model selected.",
            ("config.max_runtime_seconds",),
        ),
        (
            "Prepare training dataset chosen, model selected; "
            "I have not provided a runtime budget.",
            ("config.max_runtime_seconds",),
        ),
        (
            "Prepare training; I have not selected a dataset or model. Runtime 15 seconds.",
            ("dataset_id", "model_id"),
        ),
        (
            "Tune my model. Ask for trial count and total runtime; I have supplied neither.",
            ("limits.max_runtime_seconds", "limits.max_trials"),
        ),
        (
            "Generate a tuning snippet. I have no dataset/model, runtime, objective, "
            "trial count or total budget.",
            (
                "inputs.config.max_runtime_seconds",
                "inputs.dataset_id",
                "inputs.limits.max_runtime_seconds",
                "inputs.limits.max_trials",
                "inputs.model_id",
                "inputs.objective_metric",
            ),
        ),
        ("Inspect experiment current. Runtime is missing in this old log.", ()),
    ],
)
def test_guided_explicit_absence_checks_current_fields_without_guessing_values(message, expected):
    messages = [
        {"role": "assistant", "content": "Old runtime is 100 seconds"},
        {"role": "user", "content": message},
    ]
    assert explicit_missing_inputs(messages) == expected
    schema = guided_schema(missing_inputs=expected)
    if expected:
        assert len(schema["oneOf"]) == 1
        assert schema["oneOf"][0]["properties"]["reply"]["properties"]["required_inputs"][
            "const"
        ] == list(expected)


@pytest.mark.parametrize(
    "message,target",
    [
        (
            "Inspect run-456 and explain validation results.",
            ("get_experiment", "experiment_id", "run-456"),
        ),
        ("Inspect model classifier-456.", ("get_model", "model_id", "classifier-456")),
        ("Inspect dataset data-456.", ("get_dataset", "dataset_id", "data-456")),
        ("Inspect model", None),
        ("Inspect all models", None),
        ("Inspect the model selected", None),
        ("Compare two experiments", None),
    ],
)
def test_guided_inspection_requires_the_explicit_lookup_before_interpretation(message, target):
    messages = [{"role": "user", "content": message}]
    assert inspection_target(messages) == target
    assert inspection_target([*messages, {"role": "tool", "content": "{}"}]) is None


@pytest.mark.parametrize(
    "message,envelope",
    [
        ("Inspect model selected.", {"reply": REPLY}),
        (
            "Inspect selected.",
            {"call": {"name": "get_experiment", "arguments": {"experiment_id": "other"}}},
        ),
        (
            "Prepare training, runtime is missing.",
            {"call": {"name": "create_experiment", "arguments": {}}},
        ),
        ("Prepare training, runtime is missing.", {"reply": REPLY}),
        (
            "Generate Python comparing two experiments.",
            {"call": {"name": "compare_experiments", "arguments": {}}},
        ),
    ],
)
def test_guided_rejects_guard_violations_even_when_provider_ignores_format(message, envelope):
    async def scenario():
        runtime = Runtime(
            chat_response(message={"role": "assistant", "content": json.dumps(envelope)})
        )
        async with runtime.model(settings(chat_protocol="guided")) as model:
            with pytest.raises(ConversationModelError) as caught:
                await model.generate([{"role": "user", "content": message}])
            assert caught.value.code == "model_invalid_response"

    asyncio.run(scenario())


def test_guided_draft_schema_excludes_reads_and_domain_actions():
    assert draft_request([{"role": "user", "content": "Generate Python for training."}])
    schema = guided_schema(draft=True)
    calls = schema["oneOf"][0]["properties"]["call"]["oneOf"]
    assert [item["properties"]["name"]["const"] for item in calls] == ["generate_pipeline_snippet"]


def test_guided_fact_ids_include_fetched_comparison_winner_but_exclude_relationships():
    messages = [
        {
            "role": "tool",
            "content": json.dumps(
                {
                    "status": "succeeded",
                    "data": {"experiments": [{"id": "winner"}, {"id": "other"}]},
                    "evidence": [
                        {"record_id": "winner", "role": "winner"},
                        {"record_id": "other", "role": "record"},
                        {"record_id": "relationship", "role": "winner"},
                    ],
                }
            ),
        }
    ]
    assert current_evidence_ids(messages, facts_only=True) == ("other", "winner")
    assert current_evidence_ids(messages) == ("other", "relationship", "winner")
