"""Worker execution independent of the Celery transport."""

import asyncio
import contextlib
import logging
from uuid import uuid4

from pymongo.errors import PyMongoError

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.datasets import DatasetValidationError
from ml_pipeline_pro.training import TrainingError, train_classifier

logger = logging.getLogger(__name__)


async def execute_experiment(store, project_id: str, experiment_id: str, settings: Settings) -> str:
    token = str(uuid4())
    experiment = await store.experiments.claim(
        project_id,
        experiment_id,
        token,
        lease_seconds=settings.worker_lease_seconds,
        max_attempts=settings.worker_max_attempts,
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
        result = await asyncio.to_thread(train_classifier, experiment, dataset, token, settings)
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
            },
        )
        return "succeeded" if finished else "ownership_lost"
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
