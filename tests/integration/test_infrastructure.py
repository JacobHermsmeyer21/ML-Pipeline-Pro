import asyncio
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from ml_pipeline_pro.connections import check_readiness, open_connections
from ml_pipeline_pro.main import create_app
from ml_pipeline_pro.repositories import MongoRepository, Record
from tests.integration.helpers import integration_settings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("MLPP_RUN_INTEGRATION") != "1",
        reason="Set MLPP_RUN_INTEGRATION=1 with MongoDB and Redis running",
    ),
]


class ExampleRecord(Record):
    name: str


def test_real_service_readiness():
    with TestClient(create_app(integration_settings())) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 200, response.text
    assert response.json()["checks"] == {"mongodb": "up", "redis": "up"}


def test_real_repository_scoping_pagination_and_timestamp_round_trip():
    async def exercise():
        settings = integration_settings()
        project_id = f"test_{uuid4().hex}"
        other_project_id = f"test_{uuid4().hex}"
        async with open_connections(settings) as connections:
            assert await check_readiness(connections, settings) == {"mongodb": "up", "redis": "up"}
            repository = MongoRepository(
                connections.mongo.get_database(settings.mongodb_database),
                "foundation_test_records",
                ExampleRecord,
            )
            try:
                first = await repository.insert(ExampleRecord(project_id=project_id, name="first"))
                await repository.insert(ExampleRecord(project_id=project_id, name="second"))
                await repository.insert(ExampleRecord(project_id=other_project_id, name="other"))

                saved = await repository.get(project_id, first.id)
                assert saved is not None
                assert saved.name == "first"
                assert saved.created_at.tzinfo is not None
                assert abs((saved.created_at - first.created_at).total_seconds()) < 0.001
                assert await repository.get(other_project_id, first.id) is None
                page = await repository.list(project_id, limit=1, offset=1)
                assert len(page) == 1
                assert page[0].project_id == project_id
                assert len(await repository.list(project_id)) == 2
                for limit, offset in ((0, 0), (101, 0), (1, -1)):
                    with pytest.raises(ValueError):
                        await repository.list(project_id, limit=limit, offset=offset)
            finally:
                await repository.collection.delete_many(
                    {"project_id": {"$in": [project_id, other_project_id]}}
                )

    asyncio.run(exercise())


def test_real_registration_indexes_and_project_isolation():
    project_id = f"test_{uuid4().hex}"
    settings = integration_settings()
    try:
        with TestClient(create_app(settings), headers={"X-Project-ID": project_id}) as client:
            body = {"name": "classifier"}
            response = client.post("/api/v1/models", json=body)
            assert response.status_code == 201, response.text
            assert client.post("/api/v1/models", json=body).status_code == 409
            assert (
                client.get(
                    f"/api/v1/models/{response.json()['id']}", headers={"X-Project-ID": "other"}
                ).status_code
                == 404
            )
            dataset = client.post(
                "/api/v1/datasets",
                json={
                    "name": "classification",
                    "version": "v1",
                    "uri": "classification.csv",
                    "feature_columns": ["feature_1", "feature_2"],
                },
            )
            assert dataset.status_code == 201, dataset.text
            assert dataset.json()["row_counts"] == {"train": 80, "validation": 20, "test": 20}
    finally:

        async def cleanup():
            async with open_connections(settings) as connections:
                database = connections.mongo.get_database(settings.mongodb_database)
                for name in ("models", "datasets"):
                    await database[name].delete_many({"project_id": project_id})

        asyncio.run(cleanup())
