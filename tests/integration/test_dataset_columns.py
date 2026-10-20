"""Real transactions, publication ownership and deletion around column versions."""

import asyncio
import hashlib
import json
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import Response
from pymongo.errors import AutoReconnect

from ml_pipeline_pro import column_api
from ml_pipeline_pro.column_schemas import ColumnSave
from ml_pipeline_pro.connections import open_connections
from ml_pipeline_pro.deletion_schemas import DeletionRequest
from ml_pipeline_pro.deletions import DeletionStore
from ml_pipeline_pro.errors import ApiError
from ml_pipeline_pro.main import create_model_app
from ml_pipeline_pro.preparation_files import read_preparation
from ml_pipeline_pro.schemas import DatasetRecord
from ml_pipeline_pro.tracking import TrackingStore, get_store
from tests.integration.helpers import integration_settings
from tests.test_dataset_preparation import raw_csv

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("MLPP_RUN_INTEGRATION") != "1", reason="Requires real MongoDB/Redis"
    ),
]


@asynccontextmanager
async def environment(tmp_path):
    name = "mlpp_columns_" + uuid4().hex
    settings = integration_settings(
        mongodb_database=name,
        dataset_root=tmp_path,
        artifact_root=tmp_path / "artifacts",
        dataset_upload_enabled=True,
    )
    async with open_connections(settings) as connections:
        db = connections.mongo.get_database(name)
        store, deletions = TrackingStore(db), DeletionStore(db, settings)
        await store.ensure_indexes()
        await deletions.ensure_indexes()
        app = create_model_app(settings)
        app.dependency_overrides[get_store] = lambda: store
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"X-Project-ID": "demo"},
            timeout=90,
        ) as client:
            try:
                yield client, settings, db, store, deletions
            finally:
                assert name.startswith("mlpp_columns_")
                await connections.mongo.drop_database(name)


async def parent(client, *, prepared=True):
    if not prepared:
        response = await client.post(
            "/api/v1/datasets/upload",
            params={
                "name": "numeric",
                "version": "v1",
                "feature_columns": ["feature_1", "feature_2"],
            },
            content=await asyncio.to_thread(Path("examples/data/classification.csv").read_bytes),
            headers={"Content-Type": "text/csv"},
        )
    else:
        config = {"name": "raw", "version": "v1", "target_column": "Outcome"}

        async def upload(endpoint):
            return await client.post(
                "/api/v1/datasets/" + endpoint,
                files={
                    "file": ("original.csv", raw_csv(), "text/csv"),
                    "settings": (None, json.dumps(config)),
                },
            )

        preview = await upload("preview")
        assert preview.status_code == 200, preview.text
        config["reviewed_sha256"] = preview.json()["preview_sha256"]
        response = await upload("prepare")
    assert response.status_code == 201, response.text
    return response.json()


async def reviewed(client, data, *, prepared=True):
    body = {
        "version": "v2",
        "drop_columns": ["Category" if prepared else "feature_1"],
        "source_sha256": data["sha256"],
    }
    response = await client.post(f"/api/v1/datasets/{data['id']}/columns/preview", json=body)
    assert response.status_code == 200, response.text
    return {**body, "reviewed_sha256": response.json()["preview_sha256"]}


async def erase(deletions, identity):
    preview = await deletions.preview("demo", "datasets", identity)
    return await deletions.delete(
        "demo",
        "datasets",
        identity,
        DeletionRequest(preview_sha256=preview.preview_sha256),
        uuid4().hex,
    )


@pytest.mark.parametrize("erase_parent", [True, False])
def test_deleting_either_version_keeps_survivor_files_and_parentless_replay(tmp_path, erase_parent):
    async def run():
        async with environment(tmp_path) as (client, settings, db, store, deletions):
            data = await parent(client)
            body = await reviewed(client, data)
            path = f"/api/v1/datasets/{data['id']}/columns"
            saved = await client.post(path, json=body)
            assert saved.status_code == 201, saved.text
            child = saved.json()
            victim, survivor = (data, child) if erase_parent else (child, data)
            assert (await erase(deletions, victim["id"])).status == "complete"
            assert await store.datasets.get("demo", victim["id"]) is None
            record = DatasetRecord.model_validate(survivor)
            assert hashlib.sha256((tmp_path / record.uri).read_bytes()).hexdigest() == record.sha256
            assert read_preparation(record, settings) is not None
            if erase_parent:
                replay = await client.post(path, json=body)
                assert replay.status_code == 200 and replay.json() == child
            assert await db.datasets.count_documents({"project_id": "demo"}) == 1

    asyncio.run(run())


def test_real_concurrent_save_and_lost_ack_replay(tmp_path, monkeypatch):
    async def run():
        async with environment(tmp_path) as (client, settings, db, store, deletions):
            data = await parent(client, prepared=False)
            body = await reviewed(client, data, prepared=False)
            path = f"/api/v1/datasets/{data['id']}/columns"
            responses = await asyncio.gather(*[client.post(path, json=body) for _ in range(2)])
            assert sorted(item.status_code for item in responses) == [200, 201]
            assert responses[0].json() == responses[1].json()
            body = {**body, "version": "v3"}
            preview = await client.post(
                path + "/preview",
                json={key: value for key, value in body.items() if key != "reviewed_sha256"},
            )
            body["reviewed_sha256"] = preview.json()["preview_sha256"]
            admit = store.datasets.admit

            async def lose_ack(*args, **kwargs):
                await admit(*args, **kwargs)
                raise AutoReconnect("lost acknowledgement after real commit")

            monkeypatch.setattr(store.datasets, "admit", lose_ack)
            unknown = await client.post(path, json=body)
            assert unknown.status_code == 503
            monkeypatch.setattr(store.datasets, "admit", admit)
            replay = await client.post(path, json=body)
            assert replay.status_code == 200, replay.text
            assert await db.datasets.count_documents({}) == 3
            assert not list(tmp_path.rglob("staging_*"))

    asyncio.run(run())


def test_publication_first_blocks_parent_deletion_then_shared_source_survives(
    tmp_path, monkeypatch
):
    async def run():
        async with environment(tmp_path) as (client, settings, db, store, deletions):
            data = await parent(client)
            body = await reviewed(client, data)
            deletion_preview = await deletions.preview("demo", "datasets", data["id"])
            entered, release = asyncio.Event(), asyncio.Event()
            admit = store.datasets.admit

            async def pause(*args, **kwargs):
                entered.set()
                await release.wait()
                return await admit(*args, **kwargs)

            monkeypatch.setattr(store.datasets, "admit", pause)
            saving = asyncio.create_task(
                client.post(f"/api/v1/datasets/{data['id']}/columns", json=body)
            )
            await asyncio.wait_for(entered.wait(), 10)
            try:
                with pytest.raises(ApiError) as caught:
                    await deletions.delete(
                        "demo",
                        "datasets",
                        data["id"],
                        DeletionRequest(preview_sha256=deletion_preview.preview_sha256),
                        "blocked-publication",
                    )
                assert caught.value.code == "deletion_blocked"
            finally:
                release.set()
            response = await saving
            assert response.status_code == 201, response.text
            assert (await erase(deletions, data["id"])).status == "complete"
            assert read_preparation(DatasetRecord.model_validate(response.json()), settings)

    asyncio.run(run())


def test_deletion_first_rejects_late_child(tmp_path):
    async def run():
        async with environment(tmp_path) as (client, settings, db, store, deletions):
            data = await parent(client)
            body = await reviewed(client, data)
            assert (await erase(deletions, data["id"])).status == "complete"
            late = await client.post(f"/api/v1/datasets/{data['id']}/columns", json=body)
            assert late.status_code == 404 and await db.datasets.count_documents({}) == 0

    asyncio.run(run())


def test_cancelled_request_keeps_publication_owned_until_thread_finishes(tmp_path, monkeypatch):
    async def run():
        async with environment(tmp_path) as (client, settings, db, store, deletions):
            data = await parent(client)
            body = await reviewed(client, data)
            deletion_preview = await deletions.preview("demo", "datasets", data["id"])
            entered, release = threading.Event(), threading.Event()
            publish = column_api._publish

            def pause(*args, **kwargs):
                entered.set()
                assert release.wait(15), "Timed out waiting for publication test release"
                return publish(*args, **kwargs)

            monkeypatch.setattr(column_api, "_publish", pause)
            saving = asyncio.create_task(
                column_api.save_columns(
                    dataset_id=data["id"],
                    body=ColumnSave.model_validate(body),
                    request=SimpleNamespace(
                        app=SimpleNamespace(state=SimpleNamespace(settings=settings))
                    ),
                    project="demo",
                    store=store,
                    response=Response(),
                )
            )
            assert await asyncio.to_thread(entered.wait, 10)
            try:
                saving.cancel()
                await asyncio.sleep(0)
                assert not saving.done()
                with pytest.raises(ApiError) as caught:
                    await deletions.delete(
                        "demo",
                        "datasets",
                        data["id"],
                        DeletionRequest(preview_sha256=deletion_preview.preview_sha256),
                        "cancelled-publication",
                    )
                assert caught.value.code == "deletion_blocked"
            finally:
                release.set()
            with pytest.raises(asyncio.CancelledError):
                await saving
            replay = await client.post(f"/api/v1/datasets/{data['id']}/columns", json=body)
            assert replay.status_code == 200, replay.text
            assert await db.datasets.count_documents({}) == 2
            assert not list(tmp_path.rglob("staging_*"))

    asyncio.run(run())
