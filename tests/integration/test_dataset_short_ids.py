"""Dataset alias transactions, migration, deletion and immutable column replay."""

import asyncio
import os
from pathlib import Path

import pytest
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import OperationFailure

from ml_pipeline_pro.deletion_schemas import DeletionRequest
from ml_pipeline_pro.deletions import fingerprint
from ml_pipeline_pro.errors import ApiError
from ml_pipeline_pro.schemas import DatasetRecord
from ml_pipeline_pro.short_ids import ShortIds
from tests.integration.test_dataset_columns import environment as column_environment
from tests.integration.test_deletions import dataset, environment
from tests.integration.test_short_ids import exercise, experiment

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("MLPP_RUN_INTEGRATION") != "1", reason="Requires real MongoDB"),
]


def record(name="dataset", **changes):
    return DatasetRecord(
        project_id="demo",
        name=name,
        version="v1",
        uri="classification.csv",
        feature_columns=["feature_1", "feature_2"],
        sha256="0" * 64,
        num_classes=2,
        row_counts={"train": 80, "validation": 20, "test": 20},
        **changes,
    )


def test_concurrent_dataset_allocation_and_idempotent_migration_preserve_experiment_aliases():
    async def run(database, store, settings):
        old_experiment = await store.experiments.insert(experiment())
        old_alias = await database.record_aliases.find_one({"record_id": old_experiment.id})
        records = await asyncio.gather(
            *[store.datasets.insert(record(f"data{i}")) for i in range(12)]
        )
        assert {r.short_id for r in records} == {f"d{i}" for i in range(1, 13)}
        for saved in records:
            assert (await store.datasets.get("demo", saved.short_id)).id == saved.id
            assert await store.datasets.get("other", saved.short_id) is None
        legacy = record("legacy", id="old-dataset").model_dump(exclude={"short_id"})
        legacy["_id"] = legacy.pop("id")
        await database.datasets.insert_one(legacy)
        aliases = ShortIds(database)
        assert await aliases.migrate() == {"experiments": 0, "conversations": 0, "datasets": 1}
        assert (await store.datasets.get("demo", "d13")).id == "old-dataset"
        assert await aliases.migrate() == {"experiments": 0, "conversations": 0, "datasets": 0}
        assert await database.record_aliases.find_one({"record_id": old_experiment.id}) == old_alias

    exercise(run)


def test_dataset_publication_conflict_rolls_back_alias_and_counter(monkeypatch):
    async def run(database, store, settings):
        candidate = record()
        original = AsyncCollection.insert_one
        attempts = []

        async def insert(collection, document, *args, **kwargs):
            if collection.name == "datasets" and document["_id"] == candidate.id and not attempts:
                attempts.append(True)
                raise OperationFailure(
                    "controlled write conflict", 112, {"errorLabels": ["TransientTransactionError"]}
                )
            return await original(collection, document, *args, **kwargs)

        monkeypatch.setattr(AsyncCollection, "insert_one", insert)
        saved = await store.datasets.insert(candidate)
        assert attempts == [True] and saved.short_id == "d1"
        assert await database.record_aliases.count_documents({"kind": "datasets"}) == 1
        assert (await database.record_alias_counters.find_one({"_id": "demo:datasets"}))[
            "value"
        ] == 1

    exercise(run)


def test_dataset_alias_deletion_replays_original_path_and_never_reuses_reference(tmp_path):
    async def run():
        async with environment(tmp_path) as (settings, db, store, deletions):
            saved = await dataset(store, settings)
            assert saved.short_id == "d1"
            preview = await deletions.preview("demo", "datasets", "d1")
            assert preview.record_id == saved.id
            body = DeletionRequest(preview_sha256=preview.preview_sha256)
            deleted = await deletions.delete("demo", "datasets", "d1", body, "alias-delete")
            assert deleted.status == "complete"
            assert await store.datasets.get("demo", "d1") is None
            assert await deletions.delete("demo", "datasets", "d1", body, "alias-delete") == deleted
            operation = await deletions.operations.find_one({"_id": deleted.operation_id})
            assert operation["request_hash"] == fingerprint(["datasets", "d1", body.preview_sha256])
            with pytest.raises(ApiError) as caught:
                await deletions.delete("demo", "datasets", saved.id, body, "alias-delete")
            assert caught.value.code == "idempotency_conflict"
            replacement = await dataset(store, settings)
            assert replacement.short_id == "d2"
            assert await store.datasets.get("demo", "d1") is None
            assert (await store.datasets.get("demo", "d2")).id == replacement.id

    asyncio.run(run())


def test_real_column_save_by_alias_replays_after_parent_deletion(tmp_path):
    content = Path("examples/data/classification.csv").read_bytes()

    async def run():
        async with column_environment(tmp_path) as (client, settings, db, store, deletions):
            response = await client.post(
                "/api/v1/datasets/upload",
                params=[
                    ("name", "alias_columns"),
                    ("version", "v1"),
                    ("feature_columns", "feature_1"),
                    ("feature_columns", "feature_2"),
                ],
                content=content,
                headers={"Content-Type": "text/csv"},
            )
            assert response.status_code == 201, response.text
            parent = response.json()
            body = {
                "version": "v2",
                "drop_columns": ["feature_2"],
                "source_sha256": parent["sha256"],
            }
            preview = await client.post("/api/v1/datasets/d1/columns/preview", json=body)
            assert preview.status_code == 200, preview.text
            body["reviewed_sha256"] = preview.json()["preview_sha256"]
            response = await client.post("/api/v1/datasets/d1/columns", json=body)
            assert response.status_code == 201, response.text
            child = response.json()
            assert child["short_id"] == "d2" and child["selection"]["parent_id"] == parent["id"]
            preview = await deletions.preview("demo", "datasets", "d1")
            await deletions.delete(
                "demo",
                "datasets",
                "d1",
                DeletionRequest(preview_sha256=preview.preview_sha256),
                "parent-delete",
            )
            response = await client.post("/api/v1/datasets/d1/columns", json=body)
            assert response.status_code == 200 and response.json() == child
            assert (await client.get("/api/v1/datasets/d2")).json() == child
            assert (await client.get("/api/v1/datasets/d1")).status_code == 404

    asyncio.run(run())
