import asyncio
import os
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from ml_pipeline_pro import main
from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.queue import get_publisher
from ml_pipeline_pro.tracking import get_store
from tests.memory import FakePublisher, MemoryStore


class FakePing:
    def __init__(self) -> None:
        self.error: Exception | None = None
        self.delay = 0.0
        self.calls = 0

    async def ping(self):
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return True

    async def command(self, name: str):
        assert name == "ping"
        return await self.ping()


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for key in tuple(os.environ):
        if key.startswith("MLPP_") and key not in {
            "MLPP_RUN_INTEGRATION",
            "MLPP_RUN_WORKER_INTEGRATION",
        }:
            monkeypatch.delenv(key)


@pytest.fixture
def fake_connections(monkeypatch):
    connections = SimpleNamespace(
        mongo=SimpleNamespace(admin=FakePing()), redis=FakePing(), closed=False
    )

    @asynccontextmanager
    async def open_fake_connections(settings):
        try:
            yield connections
        finally:
            connections.closed = True

    monkeypatch.setattr(main, "open_connections", open_fake_connections)
    return connections


@pytest.fixture
def app(fake_connections):
    return main.create_app(
        Settings(_env_file=None, environment="test", dependency_timeout_seconds=0.05)
    )


@pytest.fixture
def client(app):
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def store(app):
    store = MemoryStore()
    app.dependency_overrides[get_store] = lambda: store
    return store


@pytest.fixture
def publisher(app):
    publisher = FakePublisher()
    app.dependency_overrides[get_publisher] = lambda: publisher
    return publisher


@pytest.fixture
def tracking_client(client, store, publisher):
    client.headers["X-Project-ID"] = "demo"
    return client


@pytest.fixture
def dataset_body():
    return {
        "name": "classification",
        "version": "v1",
        "uri": "classification.csv",
        "feature_columns": ["feature_1", "feature_2"],
    }


@pytest.fixture
def experiment_body(tracking_client, dataset_body):
    dataset = tracking_client.post("/api/v1/datasets", json=dataset_body)
    model = tracking_client.post("/api/v1/models", json={"name": "classifier"})
    assert dataset.status_code == 201
    assert model.status_code == 201
    return {"dataset_id": dataset.json()["id"], "model_id": model.json()["id"]}
