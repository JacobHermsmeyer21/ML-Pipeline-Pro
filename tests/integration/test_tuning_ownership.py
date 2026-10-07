"""Ownership changes at real MongoDB transaction boundaries."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pymongo.asynchronous.collection import AsyncCollection

from ml_pipeline_pro.connections import open_connections
from ml_pipeline_pro.schemas import ExperimentRecord, TrainingConfig
from ml_pipeline_pro.tracking import TrackingStore
from ml_pipeline_pro.training_control import OwnershipLost
from ml_pipeline_pro.tuning_schemas import TrialRecord, TuningRecord
from ml_pipeline_pro.tuning_store import TuningStore
from tests.integration.helpers import integration_settings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("MLPP_RUN_INTEGRATION") != "1", reason="Requires real MongoDB"),
]


@pytest.mark.parametrize(
    "operation",
    [
        "trial_claim",
        "experiment_claim",
        "trial_finish",
        "experiment_finish",
        "final_test",
        "trial_insert",
        "experiment_insert",
        "experiment_heartbeat",
        "trial_stop",
        "experiment_stop",
    ],
)
def test_takeover_between_parent_read_and_child_write_rejects_old_owner(operation, monkeypatch):
    async def run():
        settings = integration_settings(mongodb_database=f"mlpp_ownership_{uuid4().hex}")
        async with open_connections(settings) as connections:
            database = connections.mongo.get_database(settings.mongodb_database)
            tuning, tracking = TuningStore(database), TrackingStore(database)
            await tuning.ensure_indexes()
            await tracking.ensure_indexes()
            try:
                job = await tuning.jobs.insert(
                    TuningRecord(
                        project_id="demo",
                        dataset_id="dataset",
                        model_id="model",
                        submission_key="race",
                        request_hash="0" * 64,
                    )
                )
                await tuning.jobs.claim("demo", job.id, "old", lease_seconds=30, max_attempts=3)
                trial = await tuning.trials.insert(
                    TrialRecord(
                        project_id="demo",
                        tuning_job_id=job.id,
                        number=0,
                        experiment_id="experiment",
                        parameters={},
                        config=TrainingConfig(),
                        worker_token="old",
                    )
                )
                await tuning.trials.claim("demo", trial.id, "old")
                experiment = await tracking.experiments.insert(
                    ExperimentRecord(
                        id="experiment",
                        project_id="demo",
                        dataset_id="dataset",
                        model_id="model",
                        tuning_job_id=job.id,
                        submission_key="race",
                        request_hash="0" * 64,
                        worker_token="old",
                        evaluate_test=False,
                    )
                )
                assert (
                    await tracking.experiments.claim(
                        "demo", experiment.id, "unrelated-task", lease_seconds=30, max_attempts=3
                    )
                    is None
                )
                assert await tracking.experiments.claim(
                    "demo",
                    experiment.id,
                    "old",
                    lease_seconds=30,
                    max_attempts=3,
                    tuning_job_id=job.id,
                )
                if operation == "final_test":
                    assert await tracking.experiments.finish(
                        "demo",
                        experiment.id,
                        "old",
                        values={"status": "succeeded", "metrics": {"validation_f1": 0.8}},
                    )
                before_trial = await tuning.trials.get("demo", trial.id)
                before_experiment = await tracking.experiments.get("demo", experiment.id)
                before_job = await tuning.jobs.get("demo", job.id)
                paused, resume = asyncio.Event(), asyncio.Event()
                original_update = AsyncCollection.update_one
                intercepted = False

                async def pause_after_snapshot_read(collection, query, update, *args, **kwargs):
                    nonlocal intercepted
                    if (
                        not intercepted
                        and collection.full_name == tuning.jobs.collection.full_name
                        and query.get("worker_token") == "old"
                        and "ownership_revision" in update.get("$inc", {})
                    ):
                        intercepted = True
                        # Establish an old-owner snapshot before the replacement commits.
                        owner = await collection.find_one(query, session=kwargs["session"])
                        assert owner is not None
                        paused.set()
                        await asyncio.wait_for(resume.wait(), 5)
                    return await original_update(collection, query, update, *args, **kwargs)

                monkeypatch.setattr(AsyncCollection, "update_one", pause_after_snapshot_read)

                async def mutate(token):
                    if operation == "trial_claim":
                        return await tuning.trials.claim("demo", trial.id, token)
                    if operation == "experiment_claim":
                        return await tracking.experiments.claim(
                            "demo",
                            experiment.id,
                            token,
                            lease_seconds=30,
                            max_attempts=3,
                            tuning_job_id=job.id,
                        )
                    if operation == "trial_finish":
                        return await tuning.trials.finish(
                            "demo", trial.id, token, values={"status": "succeeded"}
                        )
                    if operation == "experiment_finish":
                        return await tracking.experiments.finish(
                            "demo", experiment.id, token, values={"status": "succeeded"}
                        )
                    if operation == "final_test":
                        return await tracking.experiments.finish_tuning_test(
                            "demo",
                            experiment.id,
                            job.id,
                            token,
                            values={"metrics": {"validation_f1": 0.8, "test_f1": 0.9}},
                        )
                    if operation == "trial_insert":
                        return await tuning.trials.insert(
                            trial.model_copy(
                                update={"id": "late-trial", "number": 1, "worker_token": token}
                            )
                        )
                    if operation == "experiment_insert":
                        return await tracking.experiments.insert(
                            experiment.model_copy(
                                update={
                                    "id": "late-experiment",
                                    "submission_key": "late",
                                    "worker_token": token,
                                }
                            )
                        )
                    if operation == "experiment_heartbeat":
                        return await tracking.experiments.heartbeat(
                            "demo", experiment.id, token, 30
                        )
                    if operation == "trial_stop":
                        return await tuning.trials.stop_incomplete(
                            "demo", job.id, "failed", "stop", token
                        )
                    return await tracking.experiments.stop_for_tuning(
                        "demo", job.id, "failed", "stop", token
                    )

                task = asyncio.create_task(mutate("old"))
                try:
                    await asyncio.wait_for(paused.wait(), 5)
                    await tuning.jobs.collection.update_one(
                        {"_id": job.id},
                        {"$set": {"lease_expires_at": datetime.now(UTC) - timedelta(seconds=1)}},
                    )
                    replacement = await tuning.jobs.claim(
                        "demo", job.id, "replacement", lease_seconds=30, max_attempts=3
                    )
                    assert replacement.worker_token == "replacement"
                    resume.set()
                    if operation.endswith("insert"):
                        with pytest.raises(OwnershipLost):
                            await asyncio.wait_for(task, 5)
                    else:
                        assert not await asyncio.wait_for(task, 5)
                finally:
                    resume.set()
                    if not task.done():
                        task.cancel()
                    await asyncio.gather(task, return_exceptions=True)

                assert await tuning.trials.get("demo", trial.id) == before_trial
                assert await tracking.experiments.get("demo", experiment.id) == before_experiment
                assert await tuning.trials.get("demo", "late-trial") is None
                assert await tracking.experiments.get("demo", "late-experiment") is None
                after = await tuning.jobs.get("demo", job.id)
                assert after.ownership_revision == before_job.ownership_revision
                assert after.deadline_at == before_job.deadline_at
                # The parent fences old commits even before replacement child claims.
                if operation in {"trial_finish", "trial_stop"}:
                    assert await tuning.trials.claim("demo", trial.id, "replacement")
                elif operation in {"experiment_finish", "experiment_heartbeat", "experiment_stop"}:
                    assert await tracking.experiments.claim(
                        "demo",
                        experiment.id,
                        "replacement",
                        lease_seconds=30,
                        max_attempts=3,
                        tuning_job_id=job.id,
                    )
                assert await mutate("replacement")
            finally:
                await connections.mongo.drop_database(settings.mongodb_database)

    asyncio.run(run())
