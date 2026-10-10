import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from evaluations.test_conversation_model import (
    BudgetedModel,
    FixtureTransport,
    ObservedCounter,
    check_case,
)
from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.conversation_model import native_conversation_tools
from ml_pipeline_pro.conversation_schemas import ConversationTurn, ModelReply, ModelStep


def model():
    return AsyncMock(
        provenance={},
        generate=AsyncMock(
            return_value=ModelStep(
                reply=ModelReply(message="Fixture"),
                usage={"input_tokens": 42, "output_tokens": 18},
            )
        ),
    )


def test_fiftieth_eval_call_is_admitted_but_fifty_first_is_not_dispatched():
    async def run():
        native = model()
        settings = Settings(_env_file=None)
        budgeted = BudgetedModel(
            native, SimpleNamespace(last_count=42), settings, deadline=time.monotonic() + 600
        )
        budgeted.calls = [{} for _ in range(49)]
        budgeted.reserved_tokens = 49 * settings.chat_context_tokens
        await budgeted.generate([])
        with pytest.raises(AssertionError, match="request budget"):
            await budgeted.generate([])
        native.generate.assert_awaited_once()
        assert budgeted.reserved_tokens == 50 * settings.chat_context_tokens

    asyncio.run(run())


def test_eval_deadline_reserves_full_call_allowance_before_dispatch():
    async def run():
        native = model()
        budgeted = BudgetedModel(
            native,
            SimpleNamespace(last_count=42),
            Settings(_env_file=None),
            deadline=time.monotonic() + 1,
        )
        with pytest.raises(AssertionError, match="deadline"):
            await budgeted.generate([])
        native.generate.assert_not_awaited()
        assert budgeted.reserved_tokens == 0

    asyncio.run(run())


def test_counter_mismatch_consumes_reservation_and_records_actual_usage():
    async def run():
        native = model()
        settings = Settings(_env_file=None)
        budgeted = BudgetedModel(
            native, SimpleNamespace(last_count=43), settings, deadline=time.monotonic() + 600
        )
        with pytest.raises(AssertionError, match="Counter differs"):
            await budgeted.generate([])
        assert budgeted.reserved_tokens == settings.chat_context_tokens
        assert len(budgeted.calls) == 1 and budgeted.calls[0]["usage"]["input_tokens"] == 42
        native.generate.assert_awaited_once()

    asyncio.run(run())


def test_missing_total_tuning_budget_cannot_be_satisfied_by_per_trial_runtime_location():
    turn = ConversationTurn(
        conversation_id="conversation",
        turn_id="turn",
        request_id="missing",
        revision=1,
        status="needs_input",
        user_message="Tune",
        correlation_id="fixture",
        required_inputs=["limits.max_trials", "config.max_runtime_seconds"],
    )
    with pytest.raises(AssertionError):
        check_case("missing_tuning_limits", turn, FixtureTransport())
    turn.required_inputs = ["arguments.limits.max_trials", "arguments.limits.max_runtime_seconds"]
    check_case("missing_tuning_limits", turn, FixtureTransport())


def test_evaluation_rejects_missing_completion_schema_before_counting():
    calls = []
    counter = ObservedCounter(lambda payload: calls.append(payload) or 100)
    payload = {"tools": native_conversation_tools()}
    assert counter(payload) == 100
    assert calls == [payload]
    with pytest.raises(AssertionError):
        counter({"tools": payload["tools"][:-1]})
    assert calls == [payload]
