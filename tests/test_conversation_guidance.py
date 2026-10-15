import asyncio
import json
from copy import deepcopy

import httpx
import pytest

from ml_pipeline_pro.conversation_guidance import (
    GUIDED_NAMES,
    current_budgets,
    current_evidence_ids,
    draft_request,
    explicit_missing_inputs,
    guided_schema,
    inspection_target,
    requested_facts,
)
from ml_pipeline_pro.conversation_model import ConversationModelError, native_conversation_tools
from ml_pipeline_pro.conversation_schemas import CONTEXT_BYTES, ChatRequest
from ml_pipeline_pro.conversation_service import ConversationService
from tests.conversation_memory import MemoryConversations
from tests.test_conversation_ollama import REPLY, Runtime, chat_response, settings
from tests.test_conversation_service import (
    CONTEXT,
    RecordsTransport,
    ScriptedModel,
    config,
    experiment,
    reply,
)


def inspection_messages(field="metrics.validation_f1"):
    return [
        {
            "role": "user",
            "content": f"Inspect experiment selected. Return a verified {field} fact.",
        },
        {
            "role": "tool",
            "name": "get_experiment",
            "tool_call_id": "lookup",
            "content": json.dumps(
                {
                    "status": "succeeded",
                    "data": {
                        "id": "selected",
                        "project_id": "demo",
                        "status": "failed",
                        "metrics": {"validation_f1": 0.0, "validation_accuracy": 0.5},
                    },
                    "evidence": [
                        {
                            "kind": "experiment",
                            "role": "record",
                            "record_id": "selected",
                            "project_id": "demo",
                        }
                    ],
                }
            ),
        },
    ]


@pytest.mark.parametrize(
    "field", ["status", "metrics.validation_f1", "metrics.validation_accuracy"]
)
def test_requested_inspection_scalar_references_are_required_in_actual_sdk_format(field):
    async def scenario():
        messages = inspection_messages(field)
        facts = [{"record_id": "selected", "field": field}]
        assert requested_facts(messages) == facts
        runtime = Runtime(
            chat_response(
                message={
                    "role": "assistant",
                    "content": json.dumps({"reply": {**REPLY, "facts": facts}}),
                }
            )
        )
        async with runtime.model(settings(chat_protocol="guided")) as model:
            step = await model.generate(messages)
            assert [fact.model_dump() for fact in step.reply.facts] == facts
        payload = json.loads(runtime.requests[-1].content)
        assert payload["format"] == guided_schema(
            ("selected",), fact_ids=("selected",), required_facts=facts
        )
        assert runtime.token_requests[-1] == payload

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "change",
    [
        "failed",
        "foreign",
        "relationship",
        "wrong_id",
        "wrong_kind",
        "wrong_tool",
        "absent",
        "null",
        "object",
        "history",
        "embedded",
        "negation",
        "draft",
        "missing",
    ],
)
def test_requested_facts_do_not_borrow_unavailable_or_unrequested_evidence(change):
    messages = inspection_messages()
    result = json.loads(messages[-1]["content"])
    if change == "failed":
        result["status"] = "error"
    elif change == "foreign":
        result["evidence"][0]["project_id"] = "foreign"
    elif change == "relationship":
        result["evidence"][0]["role"] = "source"
    elif change == "wrong_id":
        result["data"]["id"] = "other"
    elif change == "wrong_kind":
        result["evidence"][0]["kind"] = "model"
    elif change == "wrong_tool":
        messages[-1]["name"] = "get_model"
    elif change == "absent":
        del result["data"]["metrics"]
    elif change in {"null", "object"}:
        result["data"]["metrics"]["validation_f1"] = None if change == "null" else {}
    elif change == "history":
        messages.insert(0, {"role": "assistant", "content": messages[0]["content"]})
        messages[1]["content"] = "Inspect experiment selected. Explain results."
    elif change == "embedded":
        result["data"]["name"] = messages[0]["content"]
        messages[0]["content"] = "Inspect experiment selected. Explain results."
    elif change == "negation":
        messages[0]["content"] = (
            "Inspect experiment selected. Do not return a verified metrics.validation_f1 fact."
        )
    elif change == "draft":
        messages[0]["content"] = "Generate Python. Return a verified metrics.validation_f1 fact."
    elif change == "missing":
        messages[0]["content"] += " Prepare training, runtime is missing."
    messages[-1]["content"] = json.dumps(result)
    assert requested_facts(messages) == []


@pytest.mark.parametrize("separator", [". Return", " and return"])
def test_actual_status_phrase_and_current_request_precedence(separator):
    messages = inspection_messages("status")
    messages[0]["content"] = f"Inspect selected{separator} its actual status as a verified fact."
    assert requested_facts(messages) == [{"record_id": "selected", "field": "status"}]
    historical = deepcopy(messages)
    historical[0]["role"] = "assistant"
    assert requested_facts([*historical, {"role": "user", "content": "Explain results"}]) == []


def test_requested_facts_require_a_current_lookup_and_do_not_reuse_an_older_metric():
    messages = inspection_messages()
    assert requested_facts(messages[:1]) == []
    latest = deepcopy(messages[-1])
    result = json.loads(latest["content"])
    del result["data"]["metrics"]["validation_f1"]
    latest["content"] = json.dumps(result)
    assert requested_facts([*messages, latest]) == []


@pytest.mark.parametrize(
    "facts",
    [
        None,
        [],
        [{"record_id": "selected", "field": "status"}],
        [{"record_id": "other", "field": "metrics.validation_f1"}],
    ],
)
def test_provider_cannot_omit_or_replace_required_fact_reference(facts):
    async def scenario():
        candidate = {**REPLY}
        candidate.pop("facts", None)
        if facts is not None:
            candidate["facts"] = facts
        runtime = Runtime(
            chat_response(
                message={
                    "role": "assistant",
                    "content": json.dumps({"reply": candidate}),
                }
            )
        )
        async with runtime.model(settings(chat_protocol="guided")) as model:
            with pytest.raises(ConversationModelError) as caught:
                await model.generate(inspection_messages())
            assert caught.value.code == "model_invalid_response"
        assert sum(request.url.path == "/api/chat" for request in runtime.requests) == 1

    asyncio.run(scenario())


def test_requested_fact_constraint_does_not_change_native_mode():
    async def scenario():
        runtime = Runtime(
            chat_response(message={"role": "assistant", "content": json.dumps(REPLY)})
        )
        async with runtime.model(settings(chat_protocol="native")) as model:
            step = await model.generate(inspection_messages())
            assert step.reply.facts == []

    asyncio.run(scenario())


@pytest.mark.parametrize("omit", [False, True])
def test_guided_host_preserves_verified_value_or_saves_omission_failure_without_retry(omit):
    async def scenario():
        responses = [
            {"call": {"name": "get_experiment", "arguments": {"experiment_id": "run-selected"}}},
            {
                "reply": {
                    **REPLY,
                    "facts": [] if omit else [{"record_id": "run-selected", "field": "status"}],
                }
            },
        ]

        async def respond(_):
            return httpx.Response(
                200,
                json=chat_response(
                    message={"role": "assistant", "content": json.dumps(responses.pop(0))}
                ),
            )

        runtime = Runtime(overrides={"/api/chat": respond})
        store = MemoryConversations()
        record = {**experiment(), "id": "run-selected"}
        transport = RecordsTransport({"/api/v1/experiments/run-selected": record})
        request = ChatRequest(
            request_id="inspection",
            expected_revision=0,
            message="Inspect experiment run-selected. Return a verified status fact.",
        )
        async with runtime.model(settings(chat_protocol="guided")) as model:
            service = ConversationService(config(chat_protocol="guided"), store, model, transport)
            result = await service.chat(CONTEXT, request)
            replay = await service.chat(CONTEXT, request)
        assert result == replay and not responses
        assert len(transport.calls) == 1 and result.pending_action is None
        if omit:
            assert result.status == "failed" and not result.facts
            assert result.error["code"] == "model_invalid_response"
        else:
            assert result.status == "completed"
            assert result.facts[0].value == "queued"

    asyncio.run(scenario())


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


@pytest.mark.parametrize(
    "message,expected",
    [
        (
            "Propose tuning. Per-trial runtime is 10 seconds, "
            "maximum 2 trials and 40 seconds total.",
            {
                "config.max_runtime_seconds": 10,
                "limits.max_trials": 2,
                "limits.max_runtime_seconds": 40,
            },
        ),
        ("Prepare training runtime 15 seconds.", {"config.max_runtime_seconds": 15}),
        (
            "Propose tuning total runtime 60 seconds, 3 trials.",
            {"limits.max_runtime_seconds": 60, "limits.max_trials": 3},
        ),
        ("Prepare training runtime 10 seconds or runtime 15 seconds.", {}),
        ("Propose tuning 2.5 trials and 10.5 seconds total.", {}),
        ("Propose tuning -2 trials and -40 seconds total.", {}),
        (
            "Propose tuning per-trial runtime is 10 seconds, total  runtime 40 seconds.",
            {"config.max_runtime_seconds": 10, "limits.max_runtime_seconds": 40},
        ),
        ("Inspect current. A historical runtime 100 seconds.", {}),
    ],
)
def test_current_budget_constraints_never_borrow_history_or_choose_conflicting_values(
    message, expected
):
    messages = [
        {"role": "assistant", "content": "Old training runtime 600 seconds"},
        {"role": "user", "content": message},
    ]
    assert current_budgets(messages) == expected
    schema = guided_schema(budgets=expected)
    if "config.max_runtime_seconds" in expected:
        assert (
            schema["$defs"]["ToolTrainingConfig"]["properties"]["max_runtime_seconds"]["const"]
            == expected["config.max_runtime_seconds"]
        )
    assert (
        "const"
        not in guided_schema()["$defs"]["ToolTrainingConfig"]["properties"]["max_runtime_seconds"]
    )


def test_provider_ignored_current_per_trial_budget_is_rejected_without_repair():
    async def run():
        envelope = {
            "call": {
                "name": "create_tuning_job",
                "arguments": {
                    "dataset_id": "dataset",
                    "model_id": "model",
                    "config": {"max_runtime_seconds": 40},
                    "objective_metric": "validation_f1",
                    "limits": {"max_trials": 2, "max_runtime_seconds": 40},
                },
            }
        }
        runtime = Runtime(
            chat_response(message={"role": "assistant", "content": json.dumps(envelope)})
        )
        async with runtime.model(settings(chat_protocol="guided")) as model:
            with pytest.raises(ConversationModelError) as caught:
                await model.generate(
                    [
                        {
                            "role": "user",
                            "content": "Propose tuning. Per-trial runtime is 10 seconds, "
                            "2 trials, 40 seconds total.",
                        }
                    ]
                )
            assert caught.value.code == "model_invalid_response"

    asyncio.run(run())
