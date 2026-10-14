"""Real MongoDB insert arbitration, bounded windows and selected query index."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from ml_pipeline_pro.connections import open_connections
from ml_pipeline_pro.errors import ApiError
from ml_pipeline_pro.monitoring import MonitoringStore, summarize
from ml_pipeline_pro.monitoring_schemas import ObservationCreate
from tests.integration.helpers import integration_settings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("MLPP_RUN_INTEGRATION") != "1", reason="Requires real MongoDB"),
]


def test_real_immutable_concurrent_samples_window_pagination_and_index():
    async def run():
        settings = integration_settings()
        project = "monitor_" + uuid4().hex
        async with open_connections(settings) as connections:
            database = connections.mongo.get_database(settings.mongodb_database)
            store = MonitoringStore(database)
            await store.ensure_indexes()
            collection = store.observations.collection
            try:
                now = datetime.now(UTC)
                body = ObservationCreate(
                    sample_id="same",
                    model_version_id="version",
                    observed_at=now - timedelta(seconds=1),
                    latency_ms=150,
                    fault="seeded_latency",
                )
                inserted = await asyncio.gather(*[store.insert(project, body) for _ in range(8)])
                assert len({value.id for value in inserted}) == 1
                assert all(value == inserted[0] for value in inserted)
                assert await store.insert(project, body) == inserted[0]
                assert await collection.count_documents({"project_id": project}) == 1
                old = body.model_copy(
                    update={"sample_id": "older", "observed_at": now - timedelta(days=2)}
                )
                old_saved = await store.insert(project, old, now=now - timedelta(days=2))
                assert await store.insert(project, old) == old_saved
                with pytest.raises(ApiError) as caught:
                    await store.insert(project, body.model_copy(update={"latency_ms": 2}))
                assert caught.value.code == "observation_conflict"
                assert await store.observations.get("foreign", inserted[0].id) is None
                for index in range(101):
                    await store.insert(project, body.model_copy(update={"sample_id": f"s-{index}"}))
                await store.insert(
                    project,
                    body.model_copy(
                        update={"sample_id": "stale", "observed_at": now - timedelta(hours=2)}
                    ),
                )
                records = await store.window(project, "version", 300, now)
                assert len(records) == 101
                summary = summarize(records, "version", 300, now)
                assert summary.partial and summary.sample_count == 100
                assert summary.seeded_count == 100 and summary.labeled_accuracy is None
                assert await store.window(project, "unknown", 300, now) == []
                assert len(await store.observations.list(project, limit=1, offset=1)) == 1
                plan = await database.command(
                    {
                        "explain": {
                            "find": collection.name,
                            "filter": {
                                "project_id": project,
                                "model_version_id": "version",
                                "observed_at": {"$gte": now - timedelta(seconds=300), "$lte": now},
                            },
                            "sort": {"observed_at": -1, "_id": -1},
                            "limit": 101,
                        },
                        "verbosity": "executionStats",
                    }
                )
                assert "monitoring_project_version_observed" in str(plan["queryPlanner"])
                assert plan["executionStats"]["nReturned"] == 101
                assert plan["executionStats"]["totalDocsExamined"] <= 101
            finally:
                await collection.delete_many({"project_id": project})

    asyncio.run(run())


def test_real_monitoring_http_reference_access_replay_and_missing_states():
    from fastapi.testclient import TestClient

    from ml_pipeline_pro.main import create_monitoring_app
    from ml_pipeline_pro.schemas import ArtifactReference, ModelVersionRecord
    from ml_pipeline_pro.tracking import TrackingStore

    settings = integration_settings(project_api_keys={"demo": "monitoring-fixture-key"})
    version_id = str(uuid4())

    async def records(insert):
        async with open_connections(settings) as connections:
            database = connections.mongo.get_database(settings.mongodb_database)
            tracking = TrackingStore(database)
            if insert:
                await tracking.versions.insert(
                    ModelVersionRecord(
                        id=version_id,
                        project_id="demo",
                        model_id="fixture",
                        version="v1",
                        experiment_id="fixture",
                        dependencies={},
                        artifact=ArtifactReference(
                            name="model.pt",
                            uri="demo/fixture/token/model.pt",
                            sha256="a" * 64,
                            size_bytes=10,
                        ),
                    )
                )
            else:
                await tracking.versions.collection.delete_one(
                    {"_id": version_id, "project_id": "demo"}
                )
                await database.monitoring_observations.delete_many({"model_version_id": version_id})

    asyncio.run(records(True))
    try:
        with TestClient(create_monitoring_app(settings)) as client:
            headers = {
                "X-Project-ID": "demo",
                "X-API-Key": "monitoring-fixture-key",
                "X-Correlation-ID": "monitoring-http",
            }
            prefix = "/api/v1/monitoring/model-versions/" + version_id
            empty = client.get(prefix + "/summary", headers=headers)
            assert empty.status_code == 200 and empty.json()["issue"] == "unknown"
            assert client.post(prefix + "/diagnosis", headers=headers).status_code == 409
            body = {
                "sample_id": "http_" + uuid4().hex,
                "model_version_id": version_id,
                "observed_at": datetime.now(UTC).isoformat(),
                "latency_ms": 150,
                "fault": "seeded_latency",
            }
            first = client.post("/api/v1/monitoring/observations", headers=headers, json=body)
            assert first.status_code == 201
            assert first.headers["X-Correlation-ID"] == "monitoring-http"
            replay = client.post("/api/v1/monitoring/observations", headers=headers, json=body)
            assert replay.json() == first.json()
            assert (
                client.post(
                    "/api/v1/monitoring/observations",
                    headers=headers,
                    json={**body, "latency_ms": 151},
                ).status_code
                == 409
            )
            assert client.post(prefix + "/diagnosis", headers=headers).status_code == 503
            assert (
                client.get(prefix + "/summary", headers={"X-Project-ID": "foreign"}).status_code
                == 403
            )
            assert (
                client.post(
                    "/api/v1/monitoring/observations",
                    headers=headers,
                    json={**body, "model_version_id": "foreign-version"},
                ).status_code
                == 404
            )
            summary = client.get(prefix + "/summary", headers=headers).json()
            assert summary["labeled_accuracy"] is None and summary["max_latency_ms"] == 150
    finally:
        asyncio.run(records(False))
