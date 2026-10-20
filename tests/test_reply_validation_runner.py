import json
import sys
from contextlib import contextmanager

import pytest

from evaluations import reply_validation_runner as runner


def test_resume_cannot_convert_a_retained_failure_into_three_passes():
    good = {"acceptance_passed": True}
    assert not runner.phase_passed("acceptance", [{"status": "failed"}, good, good])
    assert not runner.phase_passed("acceptance", [good, good])
    assert runner.phase_passed("acceptance", [good, good, good])


@pytest.mark.parametrize("resume", [False, True])
def test_phase_admission_reloads_report_after_ledger_lock(tmp_path, monkeypatch, resume):
    path = tmp_path / "acceptance.json"
    old = {"phase": "acceptance", "attempts": [{"status": "failed"}]}
    latest = {"phase": "acceptance", "attempts": old["attempts"] * 3}
    if resume:
        path.write_text(json.dumps(old))

    @contextmanager
    def acquire(*args, **kwargs):
        # A competing process completes between invocation and lock acquisition.
        path.write_text(json.dumps(latest))
        yield None

    monkeypatch.setattr(runner, "OpenAITestBudget", acquire)
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "LEDGER", tmp_path / "ledger.json")
    monkeypatch.setenv("MLPP_RUN_OPENAI_EVAL", "1")
    monkeypatch.setattr(
        sys, "argv", ["runner", "--phase", "acceptance", *(["--resume"] if resume else [])]
    )
    with pytest.raises(SystemExit) as caught:
        runner.main()
    assert caught.value.code == 2
    assert json.loads(path.read_text()) == latest
