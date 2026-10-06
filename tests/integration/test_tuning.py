import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pymongo.errors import DuplicateKeyError

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.connections import open_connections
from ml_pipeline_pro.schemas import TrainingConfig
from ml_pipeline_pro.tuning_schemas import TrialRecord, TrialReservation, TuningRecord
from ml_pipeline_pro.tuning_store import TuningStore

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("MLPP_RUN_INTEGRATION") != "1", reason="Requires real MongoDB"),
]


def test_tuning_indexes_claim_deadlines_and_cancellation_fence():
    project_id = f"test_{uuid4().hex}"

    async def run():
        settings = Settings(_env_file=None)
        async with open_connections(settings) as connections:
            store = TuningStore(connections.mongo.get_database(settings.mongodb_database))
            await store.ensure_indexes()
            try:
                job = await store.jobs.insert(
                    TuningRecord(
                        project_id=project_id,
                        dataset_id="dataset",
                        model_id="model",
                        submission_key="unique",
                        request_hash="0" * 64,
                    )
                )
                with pytest.raises(DuplicateKeyError):
                    await store.jobs.insert(job.model_copy(update={"id": str(uuid4())}))
                claimed = await store.jobs.claim(
                    project_id, job.id, "first", lease_seconds=30, max_attempts=3
                )
                assert claimed.status == "running" and claimed.attempts == 1
                assert claimed.deadline_at > claimed.search_deadline_at > claimed.started_at
                assert (
                    await store.jobs.claim(
                        project_id, job.id, "duplicate", lease_seconds=30, max_attempts=3
                    )
                    is None
                )
                reservation = TrialReservation(
                    number=0,
                    trial_id="trial",
                    experiment_id="experiment",
                    parameters={"learning_rate": 0.01},
                    config=TrainingConfig(),
                )
                assert await store.jobs.reserve(project_id, job.id, "first", reservation)
                assert await store.jobs.progress(
                    project_id, job.id, "first", number=0, values={"completed_trials": 1}
                )
                await store.jobs.collection.update_one(
                    {"_id": job.id},
                    {"$set": {"lease_expires_at": datetime.now(UTC) - timedelta(seconds=1)}},
                )
                resumed = await store.jobs.claim(
                    project_id, job.id, "resumed", lease_seconds=30, max_attempts=3
                )
                assert resumed.started_at == claimed.started_at
                assert resumed.deadline_at == claimed.deadline_at
                assert resumed.scheduled_trials == 1
                cancelled = await store.jobs.request_cancel(project_id, job.id)
                assert cancelled.status == "cancel_requested"
                assert not await store.jobs.reserve(
                    project_id, job.id, "resumed", reservation.model_copy(update={"number": 1})
                )
                assert await store.jobs.finish(
                    project_id, job.id, "resumed", values={"status": "succeeded"}
                )
                assert (await store.jobs.get(project_id, job.id)).status == "cancelled"
                trial = await store.trials.insert(
                    TrialRecord(
                        project_id=project_id,
                        tuning_job_id=job.id,
                        number=0,
                        experiment_id="experiment",
                        parameters={},
                        config=TrainingConfig(),
                    )
                )
                with pytest.raises(DuplicateKeyError):
                    await store.trials.insert(trial.model_copy(update={"id": str(uuid4())}))
            finally:
                await store.jobs.collection.delete_many({"project_id": project_id})
                await store.trials.collection.delete_many({"project_id": project_id})

    asyncio.run(run())
