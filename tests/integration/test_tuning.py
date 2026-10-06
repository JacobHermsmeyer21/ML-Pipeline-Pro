import asyncio
import hashlib
import os
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from pymongo.errors import AutoReconnect, DuplicateKeyError

from ml_pipeline_pro.connections import open_connections
from ml_pipeline_pro.datasets import load_dataset
from ml_pipeline_pro.schemas import DatasetCreate, DatasetRecord, ModelRecord, TrainingConfig
from ml_pipeline_pro.tracking import TrackingStore
from ml_pipeline_pro.tuning_execution import execute_tuning
from ml_pipeline_pro.tuning_schemas import TrialRecord, TrialReservation, TuningRecord
from ml_pipeline_pro.tuning_store import TuningStore
from tests.integration.helpers import api_base_url, integration_settings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("MLPP_RUN_INTEGRATION") != "1", reason="Requires real MongoDB"),
]


def test_tuning_indexes_claim_deadlines_and_cancellation_fence():
    project_id = f"test_{uuid4().hex}"

    async def run():
        settings = integration_settings(mongodb_database=f"mlpp_tuning_{uuid4().hex}")
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
                await connections.mongo.drop_database(settings.mongodb_database)

    asyncio.run(run())


def test_real_tuning_recovery_preserves_completed_training_and_original_deadline(tmp_path):
    async def run():
        settings = integration_settings(
            mongodb_database=f"mlpp_tuning_{uuid4().hex}", artifact_root=tmp_path
        )
        async with open_connections(settings) as connections:
            database = connections.mongo.get_database(settings.mongodb_database)
            tuning = TuningStore(database)
            tracking = TrackingStore(database)
            await tuning.ensure_indexes()
            await tracking.ensure_indexes()
            try:
                definition = DatasetCreate(
                    name="classification",
                    version="v1",
                    uri="classification.csv",
                    feature_columns=["feature_1", "feature_2"],
                )
                loaded = load_dataset(definition, settings)
                dataset = await tracking.datasets.insert(
                    DatasetRecord(
                        **definition.model_dump(exclude={"expected_sha256"}),
                        project_id="demo",
                        sha256=loaded.sha256,
                        num_classes=loaded.num_classes,
                        row_counts=loaded.row_counts,
                    )
                )
                model = await tracking.models.insert(
                    ModelRecord(project_id="demo", name="classifier")
                )
                job = await tuning.jobs.insert(
                    TuningRecord(
                        project_id="demo",
                        dataset_id=dataset.id,
                        model_id=model.id,
                        submission_key="recovery",
                        request_hash="0" * 64,
                        config=TrainingConfig(epochs=5),
                        limits={"max_trials": 2},
                        search_space={"learning_rate": {"low": 0.01, "high": 0.05}},
                    )
                )
                finish = tuning.trials.finish
                interrupted = False

                async def crash_after_training(*args, **kwargs):
                    nonlocal interrupted
                    if not interrupted:
                        interrupted = True
                        raise AutoReconnect("Simulated storage outage after training completed")
                    return await finish(*args, **kwargs)

                tuning.trials.finish = crash_after_training
                with pytest.raises(AutoReconnect):
                    await execute_tuning(tuning, tracking, "demo", job.id, settings)
                before = await tuning.jobs.get("demo", job.id)
                experiment_id = before.reservation.experiment_id
                assert (await tracking.experiments.get("demo", experiment_id)).status == "succeeded"
                assert experiment_id not in {
                    record.id for record in await tracking.experiments.pending_recovery()
                }
                await tuning.jobs.collection.update_one(
                    {"_id": job.id},
                    {"$set": {"lease_expires_at": datetime.now(UTC) - timedelta(seconds=1)}},
                )
                assert (
                    await execute_tuning(tuning, tracking, "demo", job.id, settings) == "succeeded"
                )
                after = await tuning.jobs.get("demo", job.id)
                trials = await tuning.trials.for_job("demo", job.id)
                assert after.deadline_at == before.deadline_at
                assert after.completed_trials == after.scheduled_trials == len(trials) == 2
                assert (await tracking.experiments.get("demo", experiment_id)).attempts == 1
                assert after.final_evaluation == "succeeded"
                assert all("test_f1" not in trial.metrics for trial in trials)
            finally:
                await connections.mongo.drop_database(settings.mongodb_database)

    asyncio.run(run())


def cleanup_project(project_id):
    async def run():
        settings = integration_settings()
        async with open_connections(settings) as connections:
            database = connections.mongo.get_database(settings.mongodb_database)
            for name in (
                "tuning_jobs",
                "trials",
                "experiments",
                "model_versions",
                "datasets",
                "models",
            ):
                await database[name].delete_many({"project_id": project_id})

    asyncio.run(run())


def register_inputs(client):
    dataset = client.post(
        "/datasets",
        json={
            "name": "classification",
            "version": "v1",
            "uri": "classification.csv",
            "feature_columns": ["feature_1", "feature_2"],
        },
    )
    model = client.post("/models", json={"name": "classifier"})
    assert dataset.status_code == model.status_code == 201
    return {"dataset_id": dataset.json()["id"], "model_id": model.json()["id"]}


@pytest.mark.skipif(
    os.getenv("MLPP_RUN_WORKER_INTEGRATION") != "1", reason="Requires the full queued worker stack"
)
def test_queued_tuning_validation_only_trials_and_final_model_registration():
    project = f"test_{uuid4().hex}"
    try:
        with httpx.Client(
            base_url=api_base_url(), headers={"X-Project-ID": project}, timeout=5
        ) as client:
            inputs = register_inputs(client)
            body = {
                **inputs,
                "config": {"epochs": 5},
                "limits": {"max_trials": 3, "max_runtime_seconds": 60},
                "search_space": {"learning_rate": {"low": 0.01, "high": 0.05}},
            }
            response = client.post(
                "/tuning-jobs", json=body, headers={"Idempotency-Key": "tune-integration"}
            )
            assert response.status_code == 202, response.text
            job_id = response.json()["id"]
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                result = client.get(f"/tuning-jobs/{job_id}")
                assert result.status_code == 200, result.text
                job = result.json()
                if job["status"] in {"succeeded", "failed", "cancelled"}:
                    break
                time.sleep(0.25)
            assert job["status"] == "succeeded", job
            assert job["completed_trials"] == job["scheduled_trials"] == 3
            assert job["final_evaluation"] == "succeeded"
            trials = client.get(f"/tuning-jobs/{job_id}/trials").json()["items"]
            assert len(trials) == 3
            assert all("test_f1" not in trial["metrics"] for trial in trials)
            experiments = [
                client.get(f"/experiments/{trial['experiment_id']}").json() for trial in trials
            ]
            assert sum(experiment["test_evaluated"] for experiment in experiments) == 1
            repeated = client.post(
                "/tuning-jobs", json=body, headers={"Idempotency-Key": "tune-integration"}
            )
            assert repeated.json()["id"] == job_id
            winner = client.get(f"/experiments/{job['best_experiment_id']}").json()
            downloaded = client.get(f"/experiments/{winner['id']}/artifacts/model.pt")
            assert downloaded.status_code == 200
            artifact = next(item for item in winner["artifacts"] if item["name"] == "model.pt")
            assert hashlib.sha256(downloaded.content).hexdigest() == artifact["sha256"]
            version = client.post(
                f"/models/{inputs['model_id']}/versions",
                json={"version": "tuned-v1", "experiment_id": winner["id"]},
            )
            assert version.status_code == 201, version.text
    finally:
        cleanup_project(project)


@pytest.mark.skipif(
    os.getenv("MLPP_RUN_WORKER_INTEGRATION") != "1", reason="Requires the full queued worker stack"
)
def test_queued_worker_cancels_an_active_tuning_trial_without_scheduling_more():
    project = f"test_{uuid4().hex}"
    try:
        with httpx.Client(
            base_url=api_base_url(), headers={"X-Project-ID": project}, timeout=5
        ) as client:
            inputs = register_inputs(client)
            body = {
                **inputs,
                "config": {"epochs": 500, "max_runtime_seconds": 60},
                "limits": {"max_trials": 50, "max_runtime_seconds": 60},
                "search_space": {
                    "batch_size": {"choices": [1]},
                    "hidden_units": {"low": 512, "high": 512, "step": 1},
                },
            }
            response = client.post(
                "/tuning-jobs", json=body, headers={"Idempotency-Key": "cancel-integration"}
            )
            assert response.status_code == 202, response.text
            job_id = response.json()["id"]
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                job = client.get(f"/tuning-jobs/{job_id}").json()
                if job["status"] == "running" and job["scheduled_trials"] >= 1:
                    break
                time.sleep(0.05)
            assert job["status"] == "running", job
            count = job["scheduled_trials"]
            cancelled = client.post(f"/tuning-jobs/{job_id}/cancel")
            assert cancelled.status_code == 202, cancelled.text
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                job = client.get(f"/tuning-jobs/{job_id}").json()
                if job["status"] == "cancelled":
                    break
                time.sleep(0.1)
            assert job["status"] == "cancelled", job
            assert job["scheduled_trials"] == count
            trials = client.get(f"/tuning-jobs/{job_id}/trials").json()["items"]
            assert all(trial["status"] in {"succeeded", "failed", "cancelled"} for trial in trials)
    finally:
        cleanup_project(project)
