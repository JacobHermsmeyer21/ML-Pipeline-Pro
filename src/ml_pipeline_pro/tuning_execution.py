"""Bounded serial tuning, durable replay, cancellation, and final holdout evaluation."""

import asyncio
import contextlib
import hashlib
import json
import logging
import math
from datetime import UTC, datetime
from importlib.metadata import version
from time import monotonic
from uuid import uuid4

from pymongo.errors import DuplicateKeyError, PyMongoError

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.execution import execute_experiment
from ml_pipeline_pro.schemas import ExperimentRecord
from ml_pipeline_pro.training import evaluate_checkpoint
from ml_pipeline_pro.training_control import (
    OwnershipLost,
    TrainingBudgetExceeded,
    TrainingCancelled,
    TrainingControl,
    TrainingError,
)
from ml_pipeline_pro.tuning_sampler import suggest_trial
from ml_pipeline_pro.tuning_schemas import TrialRecord

logger = logging.getLogger(__name__)


def progress_values(trials) -> dict:
    valid = [
        trial
        for trial in trials
        if trial.status == "succeeded"
        and trial.objective_value is not None
        and math.isfinite(trial.objective_value)
    ]
    valid.sort(key=lambda trial: (-trial.objective_value, trial.number))
    values = {
        "completed_trials": sum(
            trial.status in {"succeeded", "failed", "cancelled"} for trial in trials
        ),
        "failed_trials": sum(trial.status == "failed" for trial in trials),
    }
    if valid:
        best = valid[0]
        values.update(
            best_trial_id=best.id,
            best_experiment_id=best.experiment_id,
            best_config=best.config.model_dump(),
            best_value=best.objective_value,
        )
    return values


def remaining(deadline) -> float:
    return max(0.0, (deadline - datetime.now(UTC)).total_seconds())


async def execute_tuning(tuning, tracking, project_id: str, job_id: str, settings: Settings) -> str:
    token = str(uuid4())
    job = await tuning.jobs.claim(
        project_id,
        job_id,
        token,
        lease_seconds=settings.worker_lease_seconds,
        max_attempts=settings.worker_max_attempts,
    )
    if job is None:
        existing = await tuning.jobs.get(project_id, job_id)
        if existing and existing.status in {"failed", "cancelled"}:
            await _stop_pending(
                tuning,
                tracking,
                project_id,
                job_id,
                existing.status,
                existing.error_summary or "Tuning was cancelled",
            )
            trials = await tuning.trials.for_job(project_id, job_id)
            await tuning.jobs.refresh_terminal_progress(project_id, job_id, progress_values(trials))
        return "not_claimed"
    control = TrainingControl(deadline=monotonic() + remaining(job.search_deadline_at))

    async def watch() -> None:
        last_heartbeat = monotonic()
        try:
            while True:
                await asyncio.sleep(0.25)
                current = await tuning.jobs.get(project_id, job_id)
                if current is None or current.worker_token != token:
                    control.ownership_lost.set()
                    return
                if current.status == "cancel_requested":
                    control.cancelled.set()
                if monotonic() - last_heartbeat >= settings.worker_lease_seconds / 3:
                    if not await tuning.jobs.heartbeat(
                        project_id, job_id, token, settings.worker_lease_seconds
                    ):
                        control.ownership_lost.set()
                        return
                    last_heartbeat = monotonic()
        except PyMongoError:
            control.ownership_lost.set()

    pulse = asyncio.create_task(watch())
    try:
        dataset = await tracking.datasets.get(project_id, job.dataset_id)
        model = await tracking.models.get(project_id, job.model_id)
        if dataset is None or model is None:
            raise TrainingError("The tuning dataset or model is missing from this project")
        if not await tuning.jobs.progress(
            project_id, job_id, token, number=None, values={"sampler_version": version("optuna")}
        ):
            raise OwnershipLost()
        stop_reason = "trial_limit"
        while job.phase == "searching":
            job = await tuning.jobs.get(project_id, job_id)
            _check_owner(job, token, control)
            if job.status == "cancel_requested":
                raise TrainingCancelled("Tuning was cancelled")
            if job.reservation is None:
                if job.scheduled_trials >= job.limits.max_trials:
                    break
                if remaining(job.search_deadline_at) <= 0:
                    stop_reason = "runtime_limit"
                    break
                history = await tuning.trials.for_job(project_id, job_id)
                reservation = suggest_trial(job, history)
                if not await tuning.jobs.reserve(project_id, job_id, token, reservation):
                    continue
                job = await tuning.jobs.get(project_id, job_id)
            reservation = job.reservation
            trial = await tuning.trials.get(project_id, reservation.trial_id)
            if trial is None:
                record = TrialRecord(
                    id=reservation.trial_id,
                    project_id=project_id,
                    tuning_job_id=job_id,
                    number=reservation.number,
                    experiment_id=reservation.experiment_id,
                    parameters=reservation.parameters,
                    config=reservation.config,
                    worker_token=token,
                )
                try:
                    trial = await tuning.trials.insert(record)
                except DuplicateKeyError:
                    trial = await tuning.trials.get(project_id, reservation.trial_id)
            if trial.status in {"queued", "running"}:
                trial = await tuning.trials.claim(project_id, trial.id, token)
                experiment = await tracking.experiments.get(project_id, trial.experiment_id)
                if experiment is None:
                    record = ExperimentRecord(
                        id=trial.experiment_id,
                        project_id=project_id,
                        model_id=job.model_id,
                        dataset_id=job.dataset_id,
                        config=trial.config,
                        submission_key=f"tuning-{job_id}-{trial.number}",
                        request_hash=hashlib.sha256(
                            json.dumps(trial.config.model_dump(), sort_keys=True).encode()
                        ).hexdigest(),
                        tuning_job_id=job_id,
                        tuning_trial_number=trial.number,
                        evaluate_test=False,
                        selection_metric=job.objective_metric,
                        worker_token=token,
                    )
                    try:
                        experiment = await tracking.experiments.insert(record)
                    except DuplicateKeyError:
                        experiment = await tracking.experiments.get(project_id, trial.experiment_id)
                if experiment.status in {"queued", "running"}:
                    result = await execute_experiment(
                        tracking,
                        project_id,
                        experiment.id,
                        settings,
                        control=control,
                        worker_token=token,
                        tuning_job_id=job_id,
                    )
                    if result == "ownership_lost":
                        raise OwnershipLost()
                    experiment = await tracking.experiments.get(project_id, experiment.id)
                if experiment.status not in {"succeeded", "failed", "cancelled"}:
                    raise TrainingError("A tuning trial could not obtain its experiment")
                objective = experiment.metrics.get(job.objective_metric)
                valid = (
                    experiment.status == "succeeded"
                    and objective is not None
                    and math.isfinite(objective)
                )
                trial_status = (
                    "succeeded"
                    if valid
                    else ("cancelled" if experiment.status == "cancelled" else "failed")
                )
                duration = (
                    max(0.0, (experiment.completed_at - experiment.started_at).total_seconds())
                    if experiment.completed_at and experiment.started_at
                    else 0.0
                )
                if not await tuning.trials.finish(
                    project_id,
                    trial.id,
                    token,
                    values={
                        "status": trial_status,
                        "objective_value": objective if valid else None,
                        "metrics": experiment.metrics,
                        "duration_seconds": duration,
                        "started_at": experiment.started_at,
                        "error_summary": None
                        if valid
                        else (
                            experiment.error_summary
                            or "Trial did not produce a finite validation objective"
                        ),
                    },
                ):
                    raise OwnershipLost()
            trials = await tuning.trials.for_job(project_id, job_id)
            if not await tuning.jobs.progress(
                project_id, job_id, token, number=reservation.number, values=progress_values(trials)
            ):
                raise OwnershipLost()
            job = await tuning.jobs.get(project_id, job_id)
        job = await tuning.jobs.get(project_id, job_id)
        _check_owner(job, token, control)
        if job.status == "cancel_requested":
            raise TrainingCancelled("Tuning was cancelled")
        trials = await tuning.trials.for_job(project_id, job_id)
        values = progress_values(trials)
        if "best_trial_id" not in values:
            raise TrainingError("No tuning trial produced a successful validation result")
        if job.phase == "searching":
            if remaining(job.search_deadline_at) <= 0:
                stop_reason = "runtime_limit"
            if not await tuning.jobs.progress(
                project_id,
                job_id,
                token,
                number=None,
                values={
                    **values,
                    "phase": "evaluating",
                    "stop_reason": stop_reason,
                    "final_evaluation": "pending",
                },
            ):
                raise OwnershipLost()
        job = await tuning.jobs.get(project_id, job_id)
        control.deadline = monotonic() + remaining(job.deadline_at)
        best = await tracking.experiments.get(project_id, job.best_experiment_id)
        final_evaluation = "succeeded"
        if not best.test_evaluated:
            try:
                control.check()
                evaluated = await asyncio.to_thread(
                    evaluate_checkpoint, best, dataset, token, settings, control
                )
                _check_owner(await tuning.jobs.get(project_id, job_id), token, control)
                if not await tracking.experiments.finish_tuning_test(
                    project_id,
                    best.id,
                    job_id,
                    values={
                        "metrics": evaluated.metrics,
                        "artifacts": [artifact.model_dump() for artifact in evaluated.artifacts],
                        "dependencies": evaluated.dependencies,
                    },
                ):
                    refreshed = await tracking.experiments.get(project_id, best.id)
                    if not refreshed.test_evaluated:
                        raise TrainingError("Final test evaluation could not be saved")
            except TrainingBudgetExceeded:
                final_evaluation = "skipped_budget"
        succeeded = await tuning.jobs.finish(
            project_id,
            job_id,
            token,
            values={
                **values,
                "status": "succeeded",
                "stop_reason": "runtime_limit"
                if final_evaluation == "skipped_budget"
                else job.stop_reason,
                "final_evaluation": final_evaluation,
                "reservation": None,
                "error_summary": None,
            },
        )
        if not succeeded:
            return "ownership_lost"
        return (await tuning.jobs.get(project_id, job_id)).status
    except OwnershipLost:
        return "ownership_lost"
    except PyMongoError:
        raise
    except TrainingCancelled as exc:
        if not await _stop_pending(
            tuning, tracking, project_id, job_id, "cancelled", str(exc), token
        ):
            return "ownership_lost"
        trials = await tuning.trials.for_job(project_id, job_id)
        finished = await tuning.jobs.finish(
            project_id,
            job_id,
            token,
            values={
                **progress_values(trials),
                "status": "cancelled",
                "stop_reason": "cancelled",
                "reservation": None,
                "error_summary": None,
            },
        )
        return "cancelled" if finished else "ownership_lost"
    except Exception as exc:
        message = (
            str(exc)
            if isinstance(exc, TrainingError)
            else "Tuning failed; inspect worker logs for this job"
        )
        logger.exception("Tuning failed", extra={"correlation_id": job_id})
        if not await _stop_pending(tuning, tracking, project_id, job_id, "failed", message, token):
            return "ownership_lost"
        trials = await tuning.trials.for_job(project_id, job_id)
        finished = await tuning.jobs.finish(
            project_id,
            job_id,
            token,
            values={
                **progress_values(trials),
                "status": "failed",
                "stop_reason": "no_successful_trials"
                if not any(trial.status == "succeeded" for trial in trials)
                else "execution_error",
                "reservation": None,
                "error_summary": message,
            },
        )
        return "failed" if finished else "ownership_lost"
    finally:
        pulse.cancel()
        with contextlib.suppress(asyncio.CancelledError, PyMongoError):
            await pulse


def _check_owner(job, token: str, control: TrainingControl) -> None:
    if job is None or job.worker_token != token or control.ownership_lost.is_set():
        raise OwnershipLost()
    if job.status == "cancel_requested":
        control.cancelled.set()
        raise TrainingCancelled("Tuning was cancelled")


async def _stop_pending(
    tuning,
    tracking,
    project_id: str,
    job_id: str,
    status: str,
    reason: str,
    token: str | None = None,
) -> bool:
    if token is not None:
        current = await tuning.jobs.get(project_id, job_id)
        if current is None or current.worker_token != token:
            return False
    await tuning.trials.stop_incomplete(project_id, job_id, status, reason, token)
    await tracking.experiments.stop_for_tuning(project_id, job_id, status, reason, token)
    return True
