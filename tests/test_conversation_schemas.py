import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ml_pipeline_pro.conversation_schemas import (
    MESSAGE_BYTES,
    ActionDecision,
    ChatRequest,
    ConversationAction,
    ModelReply,
    ModelStep,
    fingerprint,
    serialized,
)
from ml_pipeline_pro.tool_schemas import CreateExperimentArguments


@pytest.mark.parametrize("text", ["x" * MESSAGE_BYTES, "\U0001f642" * (MESSAGE_BYTES // 4)])
def test_message_utf8_limit_accepts_exact_boundary(text):
    assert ChatRequest(request_id="request-1", message=text, expected_revision=0).message == text


@pytest.mark.parametrize(
    "text", ["x" * (MESSAGE_BYTES + 1), "\U0001f642" * (MESSAGE_BYTES // 4) + "x"]
)
def test_message_utf8_limit_rejects_next_byte(text):
    with pytest.raises(ValidationError, match="UTF-8 byte limit"):
        ChatRequest(request_id="request-1", message=text, expected_revision=0)


@pytest.mark.parametrize("revision", [True, "0", -1, 0.5])
def test_turn_revision_cannot_coerce_or_go_negative(revision):
    with pytest.raises(ValidationError):
        ChatRequest(request_id="request-1", message="List experiments", expected_revision=revision)


@pytest.mark.parametrize(
    "extra", [{"project_id": "foreign"}, {"api_key": "key"}, {"allow_mutations": True}]
)
def test_chat_body_cannot_supply_trusted_execution_context(extra):
    with pytest.raises(ValidationError, match="Extra inputs"):
        ChatRequest(request_id="request-1", message="Train", expected_revision=0, **extra)


@pytest.mark.parametrize("resource", ["../other", "foreign/id", "", "x" * 129])
def test_request_identity_uses_existing_resource_restrictions(resource):
    with pytest.raises(ValidationError):
        ChatRequest(request_id=resource, message="List", expected_revision=0)


def test_fingerprint_uses_expanded_arguments_and_is_stable_across_json_order():
    arguments = CreateExperimentArguments(
        dataset_id="dataset-1", model_id="model-1", config={"max_runtime_seconds": 30}
    ).model_dump(mode="json")
    reordered = json.loads(json.dumps(arguments, sort_keys=True))
    assert fingerprint(arguments) == fingerprint(reordered)
    assert arguments["config"]["epochs"] == 30
    changed = json.loads(json.dumps(arguments))
    changed["config"]["max_runtime_seconds"] = 31
    assert fingerprint(changed) != fingerprint(arguments)
    assert len(fingerprint(arguments)) == 64


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_canonical_json_cannot_fingerprint_non_json_numbers(value):
    with pytest.raises(ValueError):
        fingerprint({"arguments": {"value": value}})


def test_canonical_json_counts_utf8_and_round_trips_aware_dates():
    when = datetime(2026, 10, 8, tzinfo=UTC)
    result = serialized({"message": "\U0001f642", "deadline": when})
    assert b"\xf0\x9f\x99\x82" in result
    assert json.loads(result)["deadline"] == when.isoformat()
    with pytest.raises(TypeError):
        serialized(object())


def test_exact_action_decision_cannot_edit_arguments_or_assert_authentication():
    decision = {"decision": "approve", "arguments_hash": "a" * 64}
    assert ActionDecision(**decision).decision == "approve"
    for extra in ({"arguments": {}}, {"authenticated": True}, {"submission_key": "key"}):
        with pytest.raises(ValidationError, match="Extra inputs"):
            ActionDecision(**decision, **extra)
    with pytest.raises(ValidationError):
        ActionDecision(decision="approve", arguments_hash="changed")


@pytest.mark.parametrize(
    "reply",
    [
        {
            "message": "Complete",
            "facts": [{"record_id": "experiment-1", "field": "status", "value": "succeeded"}],
        },
        {"message": "Confirmed", "approved": True},
        {
            "message": "Metric",
            "facts": [{"record_id": "experiment-1", "field": "metrics..test_f1"}],
        },
    ],
)
def test_model_cannot_supply_verified_fact_values_or_confirmation(reply):
    with pytest.raises(ValidationError):
        ModelReply.model_validate(reply)


def test_model_can_request_a_fact_reference_without_owning_its_value():
    reply = ModelReply(
        message="Inspect the validation result",
        citations=["experiment-1"],
        facts=[{"record_id": "experiment-1", "field": "metrics.validation_f1"}],
    )
    assert reply.facts[0].model_dump() == {
        "record_id": "experiment-1",
        "field": "metrics.validation_f1",
    }


def test_model_step_requires_exactly_one_call_or_final_reply():
    call = {"name": "list_experiments", "arguments": {}}
    reply = {"message": "No history available"}
    assert ModelStep(call=call).call.name == "list_experiments"
    assert ModelStep(reply=reply).reply.message == reply["message"]
    for data in ({}, {"call": call, "reply": reply}, {"calls": [call, call]}):
        with pytest.raises(ValidationError):
            ModelStep.model_validate(data)


def test_public_action_does_not_accept_private_ownership_or_submission_fields():
    action = {
        "action_id": "action-1",
        "conversation_id": "conversation-1",
        "turn_id": "turn-1",
        "revision": 1,
        "status": "pending_confirmation",
        "tool": {"name": "create_experiment", "arguments": {}},
        "arguments_hash": "a" * 64,
        "expires_at": datetime(2026, 10, 8, tzinfo=UTC),
    }
    assert ConversationAction(**action).attempts == []
    for extra in ({"owner_token": "owner"}, {"submission_key": "key"}, {"api_key": "secret"}):
        with pytest.raises(ValidationError, match="Extra inputs"):
            ConversationAction(**action, **extra)
    action["expires_at"] = datetime(2026, 10, 8)
    with pytest.raises(ValidationError, match="timezone"):
        ConversationAction(**action)
