import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.conversation_schemas import RECORD_BYTES, ChatRequest, serialized
from ml_pipeline_pro.conversation_store import ConversationStore, _bounded
from ml_pipeline_pro.errors import ApiError
from ml_pipeline_pro.tool_schemas import ToolCall, ToolContext
from ml_pipeline_pro.tools import validated_proposal


def test_proposals_expand_existing_defaults_without_dispatch_or_missing_budget_defaults():
    call = validated_proposal(
        ToolCall(
            name="create_experiment",
            arguments={
                "dataset_id": "dataset",
                "model_id": "model",
                "config": {"max_runtime_seconds": 10},
            },
        )
    )
    assert call.arguments["config"]["max_runtime_seconds"] == 10
    assert call.arguments["config"]["epochs"] == 30
    with pytest.raises(ValidationError):
        validated_proposal(
            ToolCall(
                name="create_experiment",
                arguments={"dataset_id": "dataset", "model_id": "model", "config": {}},
            )
        )
    for name in ("list_models", "unsupported"):
        with pytest.raises(ValueError):
            validated_proposal(ToolCall(name=name))
    with pytest.raises(ValidationError):
        validated_proposal(
            ToolCall(
                name="cancel_tuning_job",
                arguments={"tuning_job_id": "job", "allow_mutations": True},
            )
        )


def test_record_cap_counts_serialized_utf8_at_and_above_exact_boundary():
    document = {"message": ""}
    remaining = RECORD_BYTES - len(serialized(document))
    document["message"] = "é" * (remaining // 2) + "x" * (remaining % 2)
    assert _bounded(document) is document
    document["message"] += "x"
    with pytest.raises(ApiError) as caught:
        _bounded(document)
    assert caught.value.code == "chat_limit_exceeded"


def test_deadline_and_pagination_validation_precede_database_access():
    database = MagicMock()
    now = datetime(2026, 10, 8, tzinfo=UTC)
    store = ConversationStore(database, Settings(_env_file=None), clock=lambda: now)

    async def run():
        request = ChatRequest(request_id="request", message="hello", expected_revision=0)
        for deadline in (now.replace(tzinfo=None), now + timedelta(seconds=61)):
            with pytest.raises(ValueError):
                await store.reserve(ToolContext(project_id="demo"), request, deadline=deadline)
        for limit, offset in ((0, 0), (101, 0), (True, 0), (1, -1), (1, False)):
            with pytest.raises(ValueError):
                await store.history("demo", "conversation", limit=limit, offset=offset)

    asyncio.run(run())
    database.client.start_session.assert_not_called()
