import json
from datetime import date
from decimal import Decimal

import pytest

from ml_pipeline_pro.conversation_model import ConversationModelError
from ml_pipeline_pro.openai_test_budget import OpenAITestBudget

TODAY = date(2026, 10, 20)


def test_separate_authorizations_preserve_old_ledgers_and_refuse_cap_changes(tmp_path):
    from dataclasses import FrozenInstanceError

    from ml_pipeline_pro.openai_test_budget import TestAuthorization

    old, new = tmp_path / "old.json", tmp_path / "new.json"
    with OpenAITestBudget(old, today=TODAY) as budget:
        budget.reserve_generation(0, 100)
    before = old.read_bytes()
    authorization = TestAuthorization(Decimal("0.25"), Decimal("0.23"))
    with pytest.raises(FrozenInstanceError):
        authorization.reservation_limit_usd = Decimal("1.90")
    with OpenAITestBudget(new, today=TODAY, authorization=authorization) as budget:
        budget.reserve_generation(306666, 0)  # $0.23 after rounding up.
        assert budget.reserved == Decimal("0.230000")
        state = new.read_bytes()
        with pytest.raises(ConversationModelError):
            budget.reserve_count(0)
        assert new.read_bytes() == state
    with pytest.raises(ConversationModelError):
        with OpenAITestBudget(new, today=TODAY):
            pass
    assert old.read_bytes() == before
    with OpenAITestBudget(old, today=TODAY) as budget:
        assert budget.reserved == Decimal("0.000450")


@pytest.mark.parametrize(
    "amount", [Decimal("NaN"), Decimal("Infinity"), Decimal("0"), Decimal("-1"), True, "0.25"]
)
def test_authorizations_refuse_invalid_arithmetic(amount):
    from ml_pipeline_pro.openai_test_budget import TestAuthorization

    with pytest.raises(ConversationModelError):
        TestAuthorization(amount, Decimal("0.23"))


def test_reservation_stop_cannot_exceed_authorization():
    from ml_pipeline_pro.openai_test_budget import TestAuthorization

    with pytest.raises(ConversationModelError):
        TestAuthorization(Decimal("0.25"), Decimal("0.26"))


def test_reservations_survive_uncertain_calls_and_process_restarts(tmp_path):
    path = tmp_path / "ledger.json"
    with OpenAITestBudget(path, today=TODAY) as budget:
        budget.reserve_count(12000)
        budget.reserve_generation(7168, 1024)
        before = budget.reserved
        assert before > 0
        assert json.loads(path.read_text())["reservations"][1]["kind"] == "generation"
        with pytest.raises(ConversationModelError):
            with OpenAITestBudget(path, today=TODAY):
                pass
    with OpenAITestBudget(path, today=TODAY) as budget:
        assert budget.reserved == before
        budget.reserve_generation(7168, 1024)
        assert budget.reserved > before


def test_rounding_and_cap_stop_before_spending(tmp_path):
    path = tmp_path / "ledger.json"
    with OpenAITestBudget(path, today=TODAY) as budget:
        assert budget._cost(1, 0) == Decimal("0.000001")
        budget.reserve_generation(0, 400000)  # $1.80 reserved, no actual request.
        before = path.read_bytes()
        with pytest.raises(ConversationModelError):
            budget.reserve_generation(0, 30000)  # Would exceed $1.90.
        assert path.read_bytes() == before and budget.reserved == Decimal("1.800000")
        budget.reserve_generation(100000, 0)  # $1.875 total.
        budget.reserve_generation(33332, 0)  # $1.899999.
        budget.reserve_generation(1, 0)  # Exactly $1.90 after upward rounding.
        assert budget.reserved == Decimal("1.900000")
        with pytest.raises(ConversationModelError):
            budget.reserve_generation(1, 0)


@pytest.mark.parametrize("changes", [{"today": date(2026, 10, 21)}, {"model": "other"}])
def test_unreviewed_model_or_stale_pricing_refuse(tmp_path, changes):
    with pytest.raises(ConversationModelError):
        OpenAITestBudget(tmp_path / "ledger.json", **({"today": TODAY} | changes))


def test_changed_or_corrupt_ledger_fails_closed(tmp_path):
    path = tmp_path / "ledger.json"
    with OpenAITestBudget(path, today=TODAY) as budget:
        budget.reserve_generation(50, 100)
    state = json.loads(path.read_text())
    state["input_per_million_usd"] = "0"
    path.write_text(json.dumps(state))
    with pytest.raises(ConversationModelError):
        with OpenAITestBudget(path, today=TODAY):
            pass


def test_failed_reservation_persistence_cannot_authorize_a_request(tmp_path, monkeypatch):
    import os

    path = tmp_path / "ledger.json"
    with OpenAITestBudget(path, today=TODAY) as budget:
        budget.reserve_generation(50, 100)
        persisted = path.read_bytes()

        def fail(*args):
            raise OSError("fixture disk failure")

        monkeypatch.setattr(os, "replace", fail)
        with pytest.raises(OSError):
            budget.reserve_generation(50, 100)
        assert path.read_bytes() == persisted


@pytest.mark.parametrize("input_tokens,output_tokens", [(-1, 0), (True, 0), (1, -1)])
def test_invalid_arithmetic_inputs_do_not_change_ledger(tmp_path, input_tokens, output_tokens):
    path = tmp_path / "ledger.json"
    with OpenAITestBudget(path, today=TODAY) as budget:
        persisted = path.read_bytes()
        with pytest.raises(ConversationModelError):
            budget.reserve_generation(input_tokens, output_tokens)
        assert path.read_bytes() == persisted
