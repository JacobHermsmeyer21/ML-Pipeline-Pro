"""Worker execution independent of the Celery transport."""

import asyncio
import contextlib
import logging
import math
from uuid import uuid4

from pymongo.errors import PyMongoError

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.datasets import DatasetValidationError
from ml_pipeline_pro.storage_control import attempt_lock, finish_owned
from ml_pipeline_pro.training import TrainingError, train_classifier
from ml_pipeline_pro.training_control import OwnershipLost, TrainingCancelled, TrainingControl

logger = logging.getLogger(__name__)


async def execute_experiment(
    store,
    project_id,
    experiment_id,
    settings,
    *,
    control=None,
    worker_token=None,
    tuning_job_id=None,
):
    token = worker_token or str(uuid4())
    with attempt_lock(settings, project_id, "experiments", experiment_id, token):
        return await finish_owned(
            _execute_experiment(
                store,
                project_id,
                experiment_id,
                settings,
                control=control,
                worker_token=token,
                tuning_job_id=tuning_job_id,
            )
        )


async def _execute_experiment(
    store,
    project_id: str,
    experiment_id: str,
    settings: Settings,
    *,
    control: TrainingControl | None = None,
    worker_token: str | None = None,
    tuning_job_id: str | None = None,
) -> str:
    token = worker_token or str(uuid4())
    experiment = await store.experiments.claim(
        project_id,
        experiment_id,
        token,
        lease_seconds=settings.worker_lease_seconds,
        max_attempts=settings.worker_max_attempts,
        tuning_job_id=tuning_job_id,
    )
    if experiment is None:
        return "not_claimed"

    async def heartbeat() -> None:
        while True:
            await asyncio.sleep(settings.worker_lease_seconds / 3)
            if not await store.experiments.heartbeat(
                project_id, experiment_id, token, settings.worker_lease_seconds
            ):
                return

    pulse = asyncio.create_task(heartbeat())
    try:
        dataset = await store.datasets.get(project_id, experiment.dataset_id)
        model = await store.models.get(project_id, experiment.model_id)
        if dataset is None or model is None:
            raise TrainingError("The experiment's dataset or model is missing from this project")
        result = await asyncio.to_thread(
            train_classifier,
            experiment,
            dataset,
            token,
            settings,
            control=control,
            evaluate_test=experiment.evaluate_test,
            objective_metric=experiment.selection_metric,
        )
        if any(not math.isfinite(value) for value in result.metrics.values()):
            raise TrainingError("Training did not produce finite evaluation metrics")
        finished = await store.experiments.finish(
            project_id,
            experiment_id,
            token,
            values={
                "status": "succeeded",
                "metrics": result.metrics,
                "artifacts": [artifact.model_dump() for artifact in result.artifacts],
                "dependencies": result.dependencies,
                "error_summary": None,
                "test_evaluated": "test_f1" in result.metrics,
            },
        )
        return "succeeded" if finished else "ownership_lost"
    except OwnershipLost:
        return "ownership_lost"
    except TrainingCancelled as exc:
        finished = await store.experiments.finish(
            project_id,
            experiment_id,
            token,
            values={"status": "cancelled", "error_summary": str(exc)},
        )
        return "cancelled" if finished else "ownership_lost"
    except PyMongoError:
        # Leave the durable running record for recovery after its lease expires.
        raise
    except Exception as exc:
        message = (
            str(exc)
            if isinstance(exc, (DatasetValidationError, TrainingError))
            else "Training failed; inspect worker logs for this experiment"
        )
        logger.exception("Experiment failed", extra={"correlation_id": experiment_id})
        finished = await store.experiments.finish(
            project_id, experiment_id, token, values={"status": "failed", "error_summary": message}
        )
        return "failed" if finished else "ownership_lost"
    finally:
        pulse.cancel()
        with contextlib.suppress(asyncio.CancelledError, PyMongoError):
            await pulse
