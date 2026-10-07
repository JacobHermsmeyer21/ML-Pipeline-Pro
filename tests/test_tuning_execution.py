import asyncio
import hashlib
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event

import pytest
from pymongo.errors import AutoReconnect

from ml_pipeline_pro import training
from ml_pipeline_pro.training_control import OwnershipLost, TrainingBudgetExceeded, TrainingError
from ml_pipeline_pro.tuning_execution import execute_tuning
from tests.test_tuning_api import submit_tuning

pytest.importorskip("optuna", reason="Install the training extra for Optuna tests")
pytest.importorskip("torch", reason="Install the training extra for PyTorch tests")


@pytest.fixture
def job_context(tracking_client, experiment_body, tuning_store, store, app, tmp_path):
    app.state.settings.artifact_root = tmp_path / "artifacts"
    return tracking_client, experiment_body, tuning_store, store, app.state.settings


def create(context, *, trials=3, key="tuning-1"):
    client, inputs, _, _, _ = context
    response = submit_tuning(
        client,
        {
            **inputs,
            "config": {"epochs": 5},
            "limits": {"max_trials": trials},
            "search_space": {"learning_rate": {"low": 0.01, "high": 0.05}},
        },
        key,
    )
    assert response.status_code == 202, response.text
    return response.json()["id"]


def run(context, job_id):
    _, _, tuning, tracking, settings = context
    return asyncio.run(execute_tuning(tuning, tracking, "demo", job_id, settings))


def test_real_tuning_runs_five_trials_and_evaluates_only_the_selected_checkpoint(job_context):
    client, _, tuning, store, _ = job_context
    job_id = create(job_context, trials=5)
    assert run(job_context, job_id) == "succeeded"
    job = client.get(f"/api/v1/tuning-jobs/{job_id}").json()
    trials = client.get(f"/api/v1/tuning-jobs/{job_id}/trials").json()["items"]
    assert job["completed_trials"] == job["scheduled_trials"] == 5
    assert job["final_evaluation"] == "succeeded"
    assert job["best_value"] >= 0.9
    assert [trial["number"] for trial in trials] == list(range(5))
    assert all("test_f1" not in trial["metrics"] for trial in trials)
    evaluated = [record for record in store.experiments.records.values() if record.test_evaluated]
    assert len(evaluated) == 1 and evaluated[0].id == job["best_experiment_id"]
    winner = evaluated[0]
    assert winner.metrics["test_f1"] >= 0.9
    version = client.post(
        f"/api/v1/models/{winner.model_id}/versions",
        json={"version": "tuned-v1", "experiment_id": winner.id},
    )
    assert version.status_code == 201, version.text
    assert run(job_context, job_id) == "not_claimed"
    assert len(tuning.trials.records) == 5


def test_trial_failures_are_retained_and_do_not_exceed_the_budget(job_context, monkeypatch):
    def fail(*args, **kwargs):
        raise TrainingError("Deliberate invalid configuration")

    monkeypatch.setattr("ml_pipeline_pro.execution.train_classifier", fail)
    job_id = create(job_context, trials=3)
    assert run(job_context, job_id) == "failed"
    job = job_context[2].jobs.records[job_id]
    assert job.completed_trials == job.failed_trials == job.scheduled_trials == 3
    assert job.best_trial_id is None
    assert all(record.status == "failed" for record in job_context[2].trials.records.values())


def test_invalid_objective_values_fail_trials_instead_of_becoming_best_results(
    job_context, monkeypatch
):
    def invalid(*args, **kwargs):
        return training.TrainingResult({"validation_f1": float("nan")}, [], {})

    monkeypatch.setattr("ml_pipeline_pro.execution.train_classifier", invalid)
    job_id = create(job_context, trials=2)
    assert run(job_context, job_id) == "failed"
    assert job_context[2].jobs.records[job_id].failed_trials == 2
    assert all(record.objective_value is None for record in job_context[2].trials.records.values())


def test_mixed_success_and_failure_selects_only_valid_results(job_context, monkeypatch):
    calls = 0

    def sometimes_fail(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TrainingError("First configuration failed")
        return training.train_classifier(*args, **kwargs)

    monkeypatch.setattr("ml_pipeline_pro.execution.train_classifier", sometimes_fail)
    job_id = create(job_context, trials=3)
    assert run(job_context, job_id) == "succeeded"
    job = job_context[2].jobs.records[job_id]
    assert job.failed_trials == 1 and job.completed_trials == 3
    assert job_context[2].trials.records[job.best_trial_id].status == "succeeded"


def test_cancelled_queued_job_never_allocates_a_trial(job_context):
    job_id = create(job_context)
    job_context[0].post(f"/api/v1/tuning-jobs/{job_id}/cancel")
    assert run(job_context, job_id) == "not_claimed"
    assert job_context[2].trials.records == {}
    assert job_context[3].experiments.records == {}


def test_cancellation_preserves_completed_trials_and_stops_new_allocations(
    job_context, monkeypatch
):
    tuning = job_context[2]
    progress = tuning.jobs.progress

    async def cancel_after_first(project, job_id, token, *, number, values):
        result = await progress(project, job_id, token, number=number, values=values)
        if number == 0:
            await tuning.jobs.request_cancel(project, job_id)
        return result

    monkeypatch.setattr(tuning.jobs, "progress", cancel_after_first)
    job_id = create(job_context, trials=5)
    assert run(job_context, job_id) == "cancelled"
    job = tuning.jobs.records[job_id]
    assert job.completed_trials == job.scheduled_trials == 1
    assert len(tuning.trials.records) == 1
    assert next(iter(tuning.trials.records.values())).status == "succeeded"
    assert not any(record.test_evaluated for record in job_context[3].experiments.records.values())


def test_running_trial_observes_cancellation_between_batches(job_context, monkeypatch):
    started = Event()

    def wait_for_cancel(*args, control, **kwargs):
        started.set()
        while True:
            control.check()
            time.sleep(0.01)

    monkeypatch.setattr("ml_pipeline_pro.execution.train_classifier", wait_for_cancel)
    job_id = create(job_context, trials=5)

    async def exercise():
        task = asyncio.create_task(
            execute_tuning(job_context[2], job_context[3], "demo", job_id, job_context[4])
        )
        assert await asyncio.to_thread(started.wait, 2)
        await job_context[2].jobs.request_cancel("demo", job_id)
        assert await asyncio.wait_for(task, 3) == "cancelled"

    asyncio.run(exercise())
    assert job_context[2].jobs.records[job_id].scheduled_trials == 1
    assert next(iter(job_context[2].trials.records.values())).status == "cancelled"


def test_overall_deadline_interrupts_an_active_trial_and_prevents_more_work(
    job_context, monkeypatch
):
    tuning = job_context[2]
    claim = tuning.jobs.claim

    async def shortened_claim(*args, **kwargs):
        record = await claim(*args, **kwargs)
        saved = tuning.jobs.records[record.id]
        saved.search_deadline_at = datetime.now(UTC) + timedelta(seconds=0.1)
        saved.deadline_at = datetime.now(UTC) + timedelta(seconds=0.2)
        return saved.model_copy(deep=True)

    def slow(*args, control, **kwargs):
        while True:
            control.check()
            time.sleep(0.01)

    monkeypatch.setattr(tuning.jobs, "claim", shortened_claim)
    monkeypatch.setattr("ml_pipeline_pro.execution.train_classifier", slow)
    job_id = create(job_context, trials=5)
    assert run(job_context, job_id) == "failed"
    assert tuning.jobs.records[job_id].scheduled_trials <= 1
    assert tuning.jobs.records[job_id].completed_trials <= 1


def test_recovery_reuses_a_reserved_configuration_before_trial_insertion(job_context, monkeypatch):
    tuning = job_context[2]
    reserve = tuning.jobs.reserve
    interrupted = False

    async def crash_after_reservation(*args, **kwargs):
        nonlocal interrupted
        result = await reserve(*args, **kwargs)
        if not interrupted:
            interrupted = True
            raise AutoReconnect("Simulated worker loss after reservation")
        return result

    monkeypatch.setattr(tuning.jobs, "reserve", crash_after_reservation)
    job_id = create(job_context, trials=2)
    with pytest.raises(AutoReconnect):
        run(job_context, job_id)
    old = tuning.jobs.records[job_id]
    parameters = old.reservation.parameters.copy()
    deadline = old.deadline_at
    old.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert run(job_context, job_id) == "succeeded"
    first = next(record for record in tuning.trials.records.values() if record.number == 0)
    assert first.parameters == parameters
    assert tuning.jobs.records[job_id].deadline_at == deadline
    assert tuning.jobs.records[job_id].scheduled_trials == len(tuning.trials.records) == 2


def test_recovery_does_not_retrain_a_completed_experiment(job_context, monkeypatch):
    tuning = job_context[2]
    finish = tuning.trials.finish
    interrupted = False

    async def crash_before_trial_commit(*args, **kwargs):
        nonlocal interrupted
        if not interrupted:
            interrupted = True
            raise AutoReconnect("Simulated worker loss after training")
        return await finish(*args, **kwargs)

    monkeypatch.setattr(tuning.trials, "finish", crash_before_trial_commit)
    job_id = create(job_context, trials=1)
    with pytest.raises(AutoReconnect):
        run(job_context, job_id)
    experiment = next(iter(job_context[3].experiments.records.values()))
    assert experiment.status == "succeeded"
    tuning.jobs.records[job_id].lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert run(job_context, job_id) == "succeeded"
    assert job_context[3].experiments.records[experiment.id].attempts == 1
    assert len(tuning.trials.records) == 1


def test_recovery_reclaims_an_incomplete_trial_with_the_same_parameters(job_context, monkeypatch):
    interrupted = False

    def crash_once(*args, **kwargs):
        nonlocal interrupted
        if not interrupted:
            interrupted = True
            raise OwnershipLost("Simulated ownership loss")
        return training.train_classifier(*args, **kwargs)

    monkeypatch.setattr("ml_pipeline_pro.execution.train_classifier", crash_once)
    job_id = create(job_context, trials=1)
    assert run(job_context, job_id) == "ownership_lost"
    old = job_context[2].jobs.records[job_id]
    parameters = old.reservation.parameters.copy()
    old.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert run(job_context, job_id) == "succeeded"
    assert next(iter(job_context[2].trials.records.values())).parameters == parameters
    assert next(iter(job_context[3].experiments.records.values())).attempts == 2


def test_replay_after_completed_trial_matches_an_uninterrupted_search(job_context, monkeypatch):
    tuning = job_context[2]
    progress = tuning.jobs.progress
    interrupted = False

    async def crash_after_progress(*args, number, **kwargs):
        nonlocal interrupted
        result = await progress(*args, number=number, **kwargs)
        if number == 0 and not interrupted:
            interrupted = True
            raise AutoReconnect("Simulated loss between trials")
        return result

    monkeypatch.setattr(tuning.jobs, "progress", crash_after_progress)
    resumed_id = create(job_context, trials=3, key="resumed")
    with pytest.raises(AutoReconnect):
        run(job_context, resumed_id)
    tuning.jobs.records[resumed_id].lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert run(job_context, resumed_id) == "succeeded"
    fresh_id = create(job_context, trials=3, key="fresh")
    assert run(job_context, fresh_id) == "succeeded"
    resumed = asyncio.run(tuning.trials.for_job("demo", resumed_id))
    fresh = asyncio.run(tuning.trials.for_job("demo", fresh_id))
    assert [trial.parameters for trial in resumed] == [trial.parameters for trial in fresh]
    assert [trial.objective_value for trial in resumed] == [
        trial.objective_value for trial in fresh
    ]
    assert all(
        job_context[3].experiments.records[trial.experiment_id].attempts == 1 for trial in resumed
    )


def test_final_test_budget_exhaustion_keeps_validation_results_without_promotion(
    job_context, monkeypatch
):
    def exhausted(*args, **kwargs):
        raise TrainingBudgetExceeded("Final evaluation budget exhausted")

    monkeypatch.setattr("ml_pipeline_pro.tuning_execution.evaluate_checkpoint", exhausted)
    job_id = create(job_context, trials=1)
    assert run(job_context, job_id) == "succeeded"
    job = job_context[2].jobs.records[job_id]
    assert job.final_evaluation == "skipped_budget" and job.best_value is not None
    assert not job_context[3].experiments.records[job.best_experiment_id].test_evaluated
    response = job_context[0].post(
        f"/api/v1/models/{job.model_id}/versions",
        json={"version": "v1", "experiment_id": job.best_experiment_id},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "test_evaluation_required"


def test_test_labels_cannot_change_tuning_suggestions_or_selected_weights(
    job_context, tmp_path, dataset_body
):
    client, inputs, tuning, store, settings = job_context
    settings.dataset_root = tmp_path / "data"
    settings.dataset_root.mkdir()
    path = settings.dataset_root / "classification.csv"
    path.write_bytes(Path("examples/data/classification.csv").read_bytes())
    original_id = create(job_context, trials=3, key="original")
    assert run(job_context, original_id) == "succeeded"
    lines = path.read_text().splitlines()
    for index, line in enumerate(lines):
        parts = line.split(",")
        if parts[-1] == "test":
            parts[2] = str(1 - int(parts[2]))
            lines[index] = ",".join(parts)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    registered = client.post("/api/v1/datasets", json={**dataset_body, "version": "changed-test"})
    assert registered.status_code == 201
    inputs["dataset_id"] = registered.json()["id"]
    changed_id = create(job_context, trials=3, key="changed")
    assert run(job_context, changed_id) == "succeeded"
    original = asyncio.run(tuning.trials.for_job("demo", original_id))
    changed = asyncio.run(tuning.trials.for_job("demo", changed_id))
    assert [trial.parameters for trial in original] == [trial.parameters for trial in changed]
    assert [trial.objective_value for trial in original] == [
        trial.objective_value for trial in changed
    ]
    first = store.experiments.records[tuning.jobs.records[original_id].best_experiment_id]
    second = store.experiments.records[tuning.jobs.records[changed_id].best_experiment_id]
    assert first.artifacts[0].sha256 == second.artifacts[0].sha256
    assert first.metrics["test_f1"] != second.metrics["test_f1"]
    manifest = json.loads((settings.artifact_root / second.artifacts[1].uri).read_bytes())
    assert manifest["test_evaluated"] is True
    assert manifest["final_tuning_job_id"] == changed_id
    assert (
        hashlib.sha256((settings.artifact_root / second.artifacts[1].uri).read_bytes()).hexdigest()
        == second.artifacts[1].sha256
    )


def test_exhausted_recovery_stops_pending_trials_without_starting_training(
    job_context, monkeypatch
):
    from ml_pipeline_pro.schemas import ExperimentRecord, TrainingConfig
    from ml_pipeline_pro.tuning_schemas import TrialRecord

    job_id = create(job_context, trials=3)
    tuning, store, settings = job_context[2:]

    async def prepare():
        await tuning.jobs.claim("demo", job_id, "old", lease_seconds=30, max_attempts=3)
        job = tuning.jobs.records[job_id]
        job.attempts = settings.worker_max_attempts
        job.scheduled_trials = 1
        await tuning.trials.insert(
            TrialRecord(
                project_id="demo",
                tuning_job_id=job_id,
                number=0,
                experiment_id="pending",
                parameters={},
                config=TrainingConfig(),
                worker_token="old",
            )
        )
        await store.experiments.insert(
            ExperimentRecord(
                id="pending",
                project_id="demo",
                model_id=job.model_id,
                dataset_id=job.dataset_id,
                tuning_job_id=job_id,
                submission_key="pending",
                request_hash="0" * 64,
                worker_token="old",
            )
        )
        job.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)

    asyncio.run(prepare())

    def must_not_train(*args, **kwargs):
        raise AssertionError("Exhausted jobs must not start training")

    monkeypatch.setattr("ml_pipeline_pro.execution.train_classifier", must_not_train)
    assert run(job_context, job_id) == "not_claimed"
    assert tuning.jobs.records[job_id].status == "failed"
    assert tuning.jobs.records[job_id].failed_trials == 1
    assert next(iter(tuning.trials.records.values())).status == "failed"
    assert store.experiments.records["pending"].status == "failed"


def test_stale_worker_failure_does_not_close_replacement_worker_trials(job_context, monkeypatch):
    tuning = job_context[2]

    async def lose_owner_before_commit(project_id, trial_id, token, *, values):
        trial = tuning.trials.records[trial_id]
        tuning.jobs.records[trial.tuning_job_id].worker_token = "replacement"
        trial.worker_token = "replacement"
        raise RuntimeError("Old worker failed after replacement took ownership")

    monkeypatch.setattr(tuning.trials, "finish", lose_owner_before_commit)
    job_id = create(job_context, trials=1)
    assert run(job_context, job_id) == "ownership_lost"
    assert tuning.jobs.records[job_id].status == "running"
    assert next(iter(tuning.trials.records.values())).status == "running"
    assert next(iter(tuning.trials.records.values())).worker_token == "replacement"


@pytest.mark.parametrize("boundary", ["trial_claim", "experiment_claim", "final_test"])
def test_rejected_child_write_returns_ownership_lost_and_can_be_recovered(
    job_context, monkeypatch, boundary
):
    tuning, tracking, _ = job_context[2:]
    repository, method = {
        "trial_claim": (tuning.trials, "claim"),
        "experiment_claim": (tracking.experiments, "claim"),
        "final_test": (tracking.experiments, "finish_tuning_test"),
    }[boundary]
    original = getattr(repository, method)
    interrupted = False
    job_id = create(job_context, trials=1)

    async def replace_before_write(*args, **kwargs):
        nonlocal interrupted
        if not interrupted:
            interrupted = True
            tuning.jobs.records[job_id].worker_token = "replacement"
        return await original(*args, **kwargs)

    monkeypatch.setattr(repository, method, replace_before_write)
    assert run(job_context, job_id) == "ownership_lost"
    job = tuning.jobs.records[job_id]
    assert job.status == "running" and job.error_summary is None
    assert not any(
        experiment.test_evaluated for experiment in tracking.experiments.records.values()
    )
    deadline = job.deadline_at
    job.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert run(job_context, job_id) == "succeeded"
    recovered = tuning.jobs.records[job_id]
    assert recovered.deadline_at == deadline
    assert recovered.scheduled_trials == recovered.completed_trials == 1
    assert recovered.final_evaluation == "succeeded"
