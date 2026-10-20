import asyncio
import hashlib
import os
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

from ml_pipeline_pro.connections import open_connections
from ml_pipeline_pro.schemas import ExperimentRecord
from ml_pipeline_pro.tracking import TrackingStore
from tests.integration.helpers import api_base_url, integration_settings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("MLPP_RUN_INTEGRATION") != "1", reason="Requires MongoDB and Redis"
    ),
]


def cleanup(project_id):
    async def run():
        settings = integration_settings()
        async with open_connections(settings) as connections:
            database = connections.mongo.get_database(settings.mongodb_database)
            for collection in ("experiments", "model_versions", "datasets", "models"):
                await database[collection].delete_many({"project_id": project_id})

    asyncio.run(run())


def test_mongodb_claims_are_atomic_and_recovery_attempts_are_bounded():
    project_id = f"test_{uuid4().hex}"

    async def run():
        settings = integration_settings()
        async with open_connections(settings) as connections:
            store = TrackingStore(connections.mongo.get_database(settings.mongodb_database))
            await store.ensure_indexes()
            record = await store.experiments.insert(
                ExperimentRecord(
                    project_id=project_id,
                    dataset_id="dataset",
                    model_id="model",
                    submission_key="atomic-test",
                    request_hash="0" * 64,
                )
            )
            claims = await asyncio.gather(
                *[
                    store.experiments.claim(
                        project_id, record.id, token, lease_seconds=30, max_attempts=2
                    )
                    for token in ("worker-a", "worker-b")
                ]
            )
            assert sum(claim is not None for claim in claims) == 1
            first = next(claim for claim in claims if claim is not None)
            assert (
                await store.experiments.claim(
                    "other", record.id, "foreign", lease_seconds=30, max_attempts=2
                )
                is None
            )
            assert await store.experiments.heartbeat(project_id, record.id, first.worker_token, 30)
            assert not await store.experiments.heartbeat(project_id, record.id, "wrong-token", 30)
            expired = datetime.now(UTC) - timedelta(seconds=1)
            await store.experiments.collection.update_one(
                {"_id": record.id}, {"$set": {"lease_expires_at": expired}}
            )
            assert record.id in {item.id for item in await store.experiments.pending_recovery()}
            second = await store.experiments.claim(
                project_id, record.id, "replacement", lease_seconds=30, max_attempts=2
            )
            assert second is not None and second.attempts == 2
            assert not await store.experiments.finish(
                project_id, record.id, first.worker_token, values={"status": "succeeded"}
            )
            await store.experiments.collection.update_one(
                {"_id": record.id}, {"$set": {"lease_expires_at": expired}}
            )
            assert (
                await store.experiments.claim(
                    project_id, record.id, "exhausted", lease_seconds=30, max_attempts=2
                )
                is None
            )
            failed = await store.experiments.get(project_id, record.id)
            assert failed.status == "failed"
            assert "limit" in failed.error_summary

    try:
        asyncio.run(run())
    finally:
        cleanup(project_id)


@pytest.mark.skipif(
    os.getenv("MLPP_RUN_WORKER_INTEGRATION") != "1",
    reason="Requires the full Compose stack, including the worker",
)
@pytest.mark.parametrize("architecture", ["mlp", "logistic_regression"])
def test_queued_training_artifact_download_and_model_version_registration(architecture):
    project_id = f"test_{uuid4().hex}"
    try:
        with httpx.Client(
            base_url=api_base_url(), headers={"X-Project-ID": project_id}, timeout=5
        ) as client:
            dataset = client.post(
                "/datasets",
                json={
                    "name": "classification",
                    "version": "v1",
                    "uri": "classification.csv",
                    "feature_columns": ["feature_1", "feature_2"],
                },
            )
            assert dataset.status_code == 201, dataset.text
            model = client.post(
                "/models", json={"name": "classifier", "architecture": architecture}
            )
            assert model.status_code == 201, model.text
            body = {
                "dataset_id": dataset.json()["id"],
                "model_id": model.json()["id"],
                "config": (
                    {"algorithm": architecture, "epochs": 30}
                    if architecture == "logistic_regression"
                    else {"epochs": 10}
                ),
            }
            response = client.post(
                "/experiments", json=body, headers={"Idempotency-Key": "integration-job"}
            )
            assert response.status_code == 202, response.text
            experiment_id = response.json()["id"]
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                current = client.get(f"/experiments/{experiment_id}")
                assert current.status_code == 200, current.text
                record = current.json()
                if record["status"] in {"succeeded", "failed"}:
                    break
                time.sleep(0.25)
            assert record["status"] == "succeeded", record
            assert record["metrics"]["validation_f1"] >= 0.9
            repeated = client.post(
                "/experiments", json=body, headers={"Idempotency-Key": "integration-job"}
            )
            assert repeated.json()["id"] == experiment_id
            assert repeated.json()["attempts"] == 1
            model_artifact = next(
                item for item in record["artifacts"] if item["name"] == "model.pt"
            )
            downloaded = client.get(f"/experiments/{experiment_id}/artifacts/model.pt")
            assert downloaded.status_code == 200, downloaded.text
            assert hashlib.sha256(downloaded.content).hexdigest() == model_artifact["sha256"]
            registered = client.post(
                f"/models/{model.json()['id']}/versions",
                json={"version": "v1", "experiment_id": experiment_id},
            )
            assert registered.status_code == 201, registered.text
    finally:
        cleanup(project_id)
