import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import httpx
import pytest
from pymongo.errors import ConnectionFailure

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.conversation_actions import ConversationActions, outcome_status
from ml_pipeline_pro.conversation_schemas import ActionAttempt, ActionDecision, ConversationAction
from ml_pipeline_pro.conversation_store import ActionClaim
from ml_pipeline_pro.errors import ApiError, ErrorDetail
from ml_pipeline_pro.schemas import ModelRecord
from ml_pipeline_pro.tool_schemas import ToolCall, ToolContext, ToolFailure, ToolSuccess
from ml_pipeline_pro.tool_transport import HttpToolTransport, ToolResponse
from ml_pipeline_pro.tools import validated_proposal


@pytest.mark.parametrize(
    "status,code,expected",
    [
        (400, "validation_error", "failed"),
        (403, "denied", "failed"),
        (409, "conflict", "failed"),
        (503, "queue_unavailable", "unknown"),
        (202, "tool_invalid_response", "unknown"),
        (None, "tool_timeout", "unknown"),
    ],
)
def test_uncertainty_classification_preserves_accepted_submission_possibility(
    status, code, expected
):
    assert (
        outcome_status(
            ToolFailure(
                correlation_id="test",
                http_status=status,
                error=ErrorDetail(code=code, message="safe", correlation_id="test"),
            )
        )
        == expected
    )


def fixture():
    settings = Settings(_env_file=None, chat_enabled=True)
    tool = validated_proposal(
        ToolCall(
            name="create_experiment",
            arguments={
                "dataset_id": "dataset",
                "model_id": "model",
                "config": {"max_runtime_seconds": 10},
            },
        )
    )
    action = ConversationAction(
        action_id="action",
        conversation_id="conversation",
        turn_id="turn",
        revision=1,
        status="running",
        tool=tool,
        arguments_hash="a" * 64,
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    action.attempts = [
        ActionAttempt(
            number=1,
            correlation_id="host",
            status="running",
            deadline=datetime.now(UTC) + timedelta(seconds=30),
        )
    ]
    return settings, action


def test_decision_dispatch_binds_private_key_and_records_malformed_response_as_unknown():
    async def run():
        settings, action = fixture()
        store = AsyncMock()
        store.decide.return_value = ActionClaim(
            action, "owner", "original-key", action.attempts[0].deadline
        )
        store.finish_action.return_value = action
        requests = []

        def endpoint(request):
            if request.method == "GET":
                return httpx.Response(
                    200,
                    json=ModelRecord(id="model", project_id="demo", name="mlp").model_dump(
                        mode="json"
                    ),
                )
            requests.append(request)
            return httpx.Response(202, json={"not": "a valid experiment"})

        async with HttpToolTransport(
            "http://localhost",
            transport=httpx.MockTransport(endpoint),
            max_response_bytes=128 * 1024,
        ) as transport:
            service = ConversationActions(settings, store, transport)
            await service.decide(
                ToolContext(project_id="demo", api_key="private-key"),
                "conversation",
                "action",
                ActionDecision(decision="approve", arguments_hash="a" * 64),
            )
        assert len(requests) == 1
        assert requests[0].headers["Idempotency-Key"] == "original-key"
        assert requests[0].headers["X-API-Key"] == "private-key"
        assert store.finish_action.call_args.kwargs["status"] == "unknown"
        assert store.finish_action.call_args.args[2].error.code == "tool_invalid_response"

    asyncio.run(run())


def test_storage_loss_after_dispatch_does_not_retry_or_report_submission_failed():
    async def run():
        settings, action = fixture()
        store = AsyncMock()
        store.decide.return_value = ActionClaim(
            action, "owner", "original-key", action.attempts[0].deadline
        )
        store.finish_action.side_effect = ConnectionFailure("private storage error")
        requests = []

        def endpoint(request):
            if request.method == "GET":
                return httpx.Response(
                    200,
                    json=ModelRecord(id="model", project_id="demo", name="mlp").model_dump(
                        mode="json"
                    ),
                )
            requests.append(request)
            return httpx.Response(202, json={"not": "valid audit evidence"})

        async with HttpToolTransport(
            "http://localhost",
            transport=httpx.MockTransport(endpoint),
            max_response_bytes=128 * 1024,
        ) as transport:
            with pytest.raises(ApiError) as caught:
                await ConversationActions(settings, store, transport).decide(
                    ToolContext(project_id="demo"),
                    "conversation",
                    "action",
                    ActionDecision(decision="approve", arguments_hash="a" * 64),
                )
        assert (
            caught.value.code == "storage_unavailable"
            and caught.value.details["action_id"] == "action"
        )
        assert len(requests) == 1
        assert store.finish_action.call_args.kwargs["status"] == "unknown"

    asyncio.run(run())


def test_slow_optional_refresh_preserves_accepted_id_before_dispatch_deadline():
    async def run():
        settings, action = fixture()
        settings.chat_action_timeout_seconds = 0.1
        settings.dependency_timeout_seconds = 0.01
        deadline = datetime.now(UTC) + timedelta(seconds=0.1)
        store, transport = AsyncMock(), AsyncMock()
        store.decide.return_value = ActionClaim(action, "owner", "original-key", deadline)
        store.action.return_value = action.model_copy(update={"status": "unknown"})

        async def endpoint(method, path, **kwargs):
            if path == "/api/v1/models/model":
                return ToolResponse(
                    200,
                    ModelRecord(id="model", project_id="demo", name="mlp").model_dump(mode="json"),
                    "host",
                )
            if method == "GET":
                await asyncio.sleep(1)
            return ToolResponse(
                503,
                {
                    "error": {
                        "code": "queue_unavailable",
                        "message": "Accepted",
                        "correlation_id": "host",
                        "details": {"experiment_id": "accepted"},
                    }
                },
                "host",
            )

        transport.request.side_effect = endpoint
        await ConversationActions(settings, store, transport).decide(
            ToolContext(project_id="demo"),
            "conversation",
            "action",
            ActionDecision(decision="approve", arguments_hash="a" * 64),
        )
        store.finish_action.assert_awaited_once()
        outcome = store.finish_action.call_args.args[2]
        assert outcome.error.details["experiment_id"] == "accepted"
        assert store.finish_action.call_args.kwargs["status"] == "unknown"

    asyncio.run(run())


def test_oversized_audit_retains_known_accepted_id_in_explicit_unknown_result(monkeypatch):
    async def run():
        settings, action = fixture()
        store = AsyncMock()
        store.decide.return_value = ActionClaim(
            action, "owner", "original-key", action.attempts[0].deadline
        )
        store.finish_action.side_effect = [
            ApiError(422, "chat_limit_exceeded", "Audit too large"),
            action,
        ]
        outcome = ToolSuccess(
            tool_name="create_experiment",
            correlation_id="host",
            http_status=202,
            data={"id": "accepted", "status": "queued"},
            evidence=[],
        )
        monkeypatch.setattr(
            "ml_pipeline_pro.conversation_actions.ToolDispatcher.execute",
            AsyncMock(return_value=outcome),
        )
        await ConversationActions(settings, store, AsyncMock()).decide(
            ToolContext(project_id="demo"),
            "conversation",
            "action",
            ActionDecision(decision="approve", arguments_hash="a" * 64),
        )
        saved = store.finish_action.call_args.args[2]
        assert store.finish_action.call_args.kwargs["status"] == "unknown"
        assert saved.error.details == {"evidence_not_saved": True, "experiment_id": "accepted"}

    asyncio.run(run())


def test_replay_and_rejection_never_dispatch_and_storage_loss_reports_saved_identity():
    async def run():
        settings, action = fixture()
        store, transport = AsyncMock(), AsyncMock()
        store.decide.return_value = ActionClaim(action)
        service = ConversationActions(settings, store, transport)
        decision = ActionDecision(decision="approve", arguments_hash="a" * 64)
        assert (
            await service.decide(ToolContext(project_id="demo"), "conversation", "action", decision)
            == action
        )
        transport.request.assert_not_called()
        store.decide.side_effect = ConnectionFailure("private connection string")
        with pytest.raises(ApiError) as caught:
            await service.decide(ToolContext(project_id="demo"), "conversation", "action", decision)
        assert caught.value.code == "storage_unavailable"
        assert caught.value.details == {"conversation_id": "conversation", "action_id": "action"}
        assert "private" not in str(caught.value)
        service.settings.chat_enabled = False
        with pytest.raises(ApiError) as caught:
            await service.decide(ToolContext(project_id="demo"), "conversation", "action", decision)
        assert caught.value.code == "chat_unavailable"

    asyncio.run(run())
