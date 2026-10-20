"""Real MongoDB cascade, transaction ordering, receipts and interrupted cleanup."""

import asyncio
import hashlib
import json
import os
import signal
import subprocess
import sys
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from ml_pipeline_pro.connections import open_connections
from ml_pipeline_pro.deletion_schemas import DeletionRequest
from ml_pipeline_pro.deletions import DeletionStore
from ml_pipeline_pro.errors import ApiError
from ml_pipeline_pro.lifecycle import Lifecycle, registration_generation
from ml_pipeline_pro.schemas import DatasetRecord, ExperimentRecord, ModelRecord
from ml_pipeline_pro.storage_control import attempt_lock
from ml_pipeline_pro.tracking import TrackingStore
from ml_pipeline_pro.tuning_schemas import TuningRecord
from ml_pipeline_pro.tuning_store import TuningStore
from tests.integration.helpers import integration_settings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("MLPP_RUN_INTEGRATION") != "1", reason="Requires real MongoDB and Redis"
    ),
]


@asynccontextmanager
async def environment(tmp_path):
    name = f"mlpp_deletion_test_{uuid4().hex}"
    settings = integration_settings(
        mongodb_database=name, dataset_root=tmp_path / "data", artifact_root=tmp_path / "artifacts"
    )
    settings.dataset_root.mkdir(parents=True)
    async with open_connections(settings) as connections:
        database = connections.mongo.get_database(name)
        store, deletions = TrackingStore(database), DeletionStore(database, settings)
        await store.ensure_indexes()
        await deletions.ensure_indexes()
        try:
            yield settings, database, store, deletions
        finally:
            assert name.startswith("mlpp_deletion_test_")
            await connections.mongo.drop_database(name)


async def dataset(store, settings, *, name="data", uri=None):
    uri = uri or f"uploads/demo/{name}.csv"
    path = settings.dataset_root / uri
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"verified dataset bytes")
    return await store.datasets.insert(
        DatasetRecord(
            project_id="demo",
            name=name,
            version="v1",
            uri=uri,
            feature_columns=["feature"],
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            num_classes=2,
            row_counts={"train": 2, "validation": 2, "test": 2},
        )
    )


async def experiment(store, data, model, *, status="succeeded", key="original"):
    return await store.experiments.insert(
        ExperimentRecord(
            project_id="demo",
            dataset_id=data.id,
            model_id=model.id,
            status=status,
            submission_key=key,
            request_hash="a" * 64,
            lease_expires_at=datetime.now(UTC) - timedelta(seconds=5),
        )
    )


@pytest.mark.parametrize("kind", ["datasets", "models"])
def test_permanent_cascade_preserves_survivors_chats_and_replays_receipt(tmp_path, kind):
    async def run():
        async with environment(tmp_path) as (settings, db, store, deletions):
            data = await dataset(store, settings)
            shared = await dataset(store, settings, name="shared", uri=data.uri)
            model = await store.models.insert(ModelRecord(project_id="demo", name="classifier"))
            other = await store.models.insert(ModelRecord(project_id="demo", name="survivor"))
            run = await experiment(store, data, model)
            survivor = await experiment(store, shared, other, key="survives")
            artifact = settings.artifact_root / f"demo/{run.id}/old-attempt/model.pt"
            artifact.parent.mkdir(parents=True)
            artifact.write_bytes(b"checkpoint")
            await db.model_versions.insert_one(
                {
                    "_id": "version",
                    "project_id": "demo",
                    "model_id": model.id,
                    "experiment_id": run.id,
                }
            )
            await db.monitoring_observations.insert_one(
                {"_id": "sample", "project_id": "demo", "model_version_id": "version"}
            )
            await db.conversation_turns.insert_one(
                {
                    "_id": "chat",
                    "project_id": "demo",
                    "snippet": {"code": "saved draft"},
                    "evidence": [run.id],
                }
            )
            root = data if kind == "datasets" else model
            preview = await deletions.preview("demo", kind, root.id)
            assert preview.counts.experiments == 1 and preview.counts.files == 1
            request = DeletionRequest(preview_sha256=preview.preview_sha256)
            erased = await deletions.delete("demo", kind, root.id, request, "delete")
            assert erased.status == "complete"
            assert (await deletions.delete("demo", kind, root.id, request, "delete")) == erased
            assert await db[kind].find_one({"_id": root.id}) is None
            assert await db.experiments.find_one({"_id": run.id}) is None
            assert await db.experiments.find_one({"_id": survivor.id}) is not None
            assert await db.model_versions.count_documents({}) == 0
            assert await db.monitoring_observations.count_documents({}) == 0
            assert await db.conversation_turns.find_one({"_id": "chat"}) is not None
            assert await db.datasets.find_one({"_id": shared.id}) is not None
            assert (settings.dataset_root / data.uri).exists()
            assert not artifact.parent.parent.exists()
            assert await db.deletion_items.count_documents({}) == 0
            receipt = await db.deletions.find_one({"_id": erased.operation_id})
            assert "storage_identity" not in receipt and "name" not in receipt
            with pytest.raises(ApiError) as caught:
                await store.lifecycle.check_submission("demo", "experiments", "original", "a" * 64)
            assert caught.value.code == "submission_deleted" and caught.value.status_code == 410
            with pytest.raises(ApiError) as caught:
                await store.lifecycle.check_submission("demo", "experiments", "original", "b" * 64)
            assert caught.value.code == "idempotency_conflict"
            assert await store.lifecycle.generation("demo") == 2
            replacement = root.model_copy(update={"id": str(uuid4())})
            assert (await getattr(store, kind).insert(replacement)).id != root.id

    asyncio.run(run())


@pytest.mark.parametrize(
    "collection,status",
    [
        ("experiments", "queued"),
        ("experiments", "running"),
        ("tuning_jobs", "queued"),
        ("tuning_jobs", "running"),
        ("tuning_jobs", "cancel_requested"),
    ],
)
def test_every_active_status_blocks_before_domain_mutation(tmp_path, collection, status):
    async def run():
        async with environment(tmp_path) as (settings, db, store, deletions):
            data = await dataset(store, settings)
            model = await store.models.insert(ModelRecord(project_id="demo", name="classifier"))
            await db[collection].insert_one(
                {
                    "_id": "active",
                    "project_id": "demo",
                    "dataset_id": data.id,
                    "model_id": model.id,
                    "status": status,
                    "lease_expires_at": datetime.now(UTC) - timedelta(days=1),
                }
            )
            preview = await deletions.preview("demo", "datasets", data.id)
            assert preview.active_jobs == 1
            with pytest.raises(ApiError) as caught:
                await deletions.delete(
                    "demo",
                    "datasets",
                    data.id,
                    DeletionRequest(preview_sha256=preview.preview_sha256),
                    "blocked",
                )
            assert caught.value.code == "deletion_blocked"
            assert await db.datasets.count_documents({}) == 1
            assert await db.deletions.count_documents({}) == 0
            assert (settings.dataset_root / data.uri).exists()

    asyncio.run(run())


def test_interrupted_file_cleanup_keeps_gate_and_can_resume_without_a_live_root(
    tmp_path, monkeypatch
):
    async def run():
        async with environment(tmp_path) as (settings, db, store, deletions):
            data = await dataset(store, settings)
            preview = await deletions.preview("demo", "datasets", data.id)
            request = DeletionRequest(preview_sha256=preview.preview_sha256)
            from ml_pipeline_pro import deletions as module

            original = module.remove_entry

            def fail(*args):
                original(*args)
                raise OSError("lost cleanup acknowledgement")

            monkeypatch.setattr(module, "remove_entry", fail)
            with pytest.raises(ApiError) as caught:
                await deletions.delete("demo", "datasets", data.id, request, "resume")
            assert caught.value.code == "deletion_cleanup_unavailable"
            operation_id = caught.value.details["operation_id"]
            assert (await deletions.get("demo", operation_id)).status == "cleaning"
            assert not (settings.dataset_root / data.uri).exists()
            with pytest.raises(ApiError) as caught:
                await store.models.insert(ModelRecord(project_id="demo", name="blocked"))
            assert caught.value.code == "deletion_in_progress"
            with pytest.raises(ApiError):
                await store.datasets.get("demo", data.id)
            monkeypatch.setattr(module, "remove_entry", original)
            # Simulate a crash after domain removal but before operation completion.
            await db.datasets.delete_one({"_id": data.id})
            assert (
                await deletions.delete("demo", "datasets", data.id, request, "resume")
            ).status == "complete"
            assert await store.lifecycle.generation("demo") == 2

    asyncio.run(run())


def test_live_stale_attempt_blocks_erasure_after_terminal_status(tmp_path):
    async def run_test():
        async with environment(tmp_path) as (settings, db, store, deletions):
            data = await dataset(store, settings)
            model = await store.models.insert(ModelRecord(project_id="demo", name="classifier"))
            run = await experiment(store, data, model)
            preview = await deletions.preview("demo", "models", model.id)
            with attempt_lock(settings, "demo", "experiments", run.id, "old-worker"):
                with pytest.raises(ApiError) as caught:
                    await deletions.delete(
                        "demo",
                        "models",
                        model.id,
                        DeletionRequest(preview_sha256=preview.preview_sha256),
                        "stale-worker",
                    )
            assert caught.value.code == "deletion_blocked"
            assert await db.models.find_one({"_id": model.id}) is not None
            assert await db.deletions.count_documents({}) == 0

    asyncio.run(run_test())


def test_preview_staleness_generation_fence_and_foreign_scope(tmp_path):
    async def run():
        async with environment(tmp_path) as (settings, db, store, deletions):
            data = await dataset(store, settings)
            preview = await deletions.preview("demo", "datasets", data.id)
            model = await store.models.insert(ModelRecord(project_id="demo", name="classifier"))
            run = await experiment(store, data, model)
            with pytest.raises(ApiError) as caught:
                await deletions.delete(
                    "demo",
                    "datasets",
                    data.id,
                    DeletionRequest(preview_sha256=preview.preview_sha256),
                    "stale",
                )
            assert caught.value.code == "deletion_preview_stale"
            with pytest.raises(ApiError) as caught:
                await deletions.preview("foreign", "datasets", data.id)
            assert caught.value.status_code == 404
            current = await deletions.preview("demo", "datasets", data.id)
            generation = await store.lifecycle.generation("demo")
            await deletions.delete(
                "demo",
                "datasets",
                data.id,
                DeletionRequest(preview_sha256=current.preview_sha256),
                "current",
            )
            token = registration_generation.set(("demo", generation))
            try:
                with pytest.raises(ApiError) as caught:
                    await store.datasets.insert(data.model_copy(update={"id": str(uuid4())}))
                assert caught.value.code == "deletion_in_progress"
            finally:
                registration_generation.reset(token)
            assert await db.experiments.find_one({"_id": run.id}) is None

    asyncio.run(run())


def test_cascade_crosses_pagination_and_erases_tuning_history_without_foreign_records(tmp_path):
    async def run():
        async with environment(tmp_path) as (settings, db, store, deletions):
            data = await dataset(store, settings)
            model = await store.models.insert(ModelRecord(project_id="demo", name="classifier"))
            await db.tuning_jobs.insert_one(
                {
                    "_id": "search",
                    "project_id": "demo",
                    "model_id": model.id,
                    "dataset_id": data.id,
                    "status": "succeeded",
                    "submission_key": "search-key",
                    "request_hash": "b" * 64,
                    "reservation": {"experiment_id": "reserved-child"},
                }
            )
            records = []
            for index in range(125):
                record = ExperimentRecord(
                    id=f"child-{index}",
                    project_id="demo",
                    model_id=model.id,
                    dataset_id=data.id,
                    tuning_job_id="search",
                    status="succeeded",
                    submission_key=f"child-key-{index}",
                    request_hash="a" * 64,
                ).model_dump()
                record["_id"] = record.pop("id")
                records.append(record)
            await db.experiments.insert_many(records)
            await db.trials.insert_many(
                [
                    {
                        "_id": f"trial-{index}",
                        "project_id": "demo",
                        "tuning_job_id": "search",
                        "experiment_id": f"child-{index}",
                    }
                    for index in range(125)
                ]
            )
            await db.experiments.insert_one(
                {"_id": "foreign", "project_id": "foreign", "model_id": model.id}
            )
            await db.trials.insert_one(
                {"_id": "foreign-trial", "project_id": "foreign", "tuning_job_id": "search"}
            )
            reserved = settings.artifact_root / "demo/reserved-child/token/model.pt"
            reserved.parent.mkdir(parents=True)
            reserved.write_bytes(b"reserved but not yet recorded")
            preview = await deletions.preview("demo", "models", model.id)
            assert preview.counts.experiments == 125 and preview.counts.trials == 125
            erased = await deletions.delete(
                "demo",
                "models",
                model.id,
                DeletionRequest(preview_sha256=preview.preview_sha256),
                "large-cascade",
            )
            assert erased.status == "complete" and not reserved.exists()
            assert await db.experiments.count_documents({"project_id": "demo"}) == 0
            assert await db.trials.count_documents({"project_id": "demo"}) == 0
            assert await db.tuning_jobs.count_documents({}) == 0
            assert await db.experiments.find_one({"_id": "foreign"}) is not None
            assert await db.trials.find_one({"_id": "foreign-trial"}) is not None
            assert await db.datasets.find_one({"_id": data.id}) is not None
            with pytest.raises(ApiError) as caught:
                await store.lifecycle.check_submission(
                    "demo", "tuning_jobs", "search-key", "b" * 64
                )
            assert caught.value.code == "submission_deleted"

    asyncio.run(run())


@pytest.mark.parametrize("collection", ["experiments", "tuning_jobs"])
def test_admission_first_conflicts_with_deletion_capture(tmp_path, monkeypatch, collection):
    async def run():
        async with environment(tmp_path) as (settings, db, store, deletions):
            data = await dataset(store, settings)
            model = await store.models.insert(ModelRecord(project_id="demo", name="classifier"))
            preview = await deletions.preview("demo", "models", model.id)
            repository = store.experiments if collection == "experiments" else TuningStore(db).jobs
            record_type = ExperimentRecord if collection == "experiments" else TuningRecord
            record = record_type(
                project_id="demo",
                dataset_id=data.id,
                model_id=model.id,
                submission_key="race",
                request_hash="c" * 64,
            )
            entered, release = asyncio.Event(), asyncio.Event()
            original = Lifecycle.touch
            admission = None

            async def pause(self, *args, **kwargs):
                value = await original(self, *args, **kwargs)
                if asyncio.current_task() is admission:
                    entered.set()
                    await release.wait()
                return value

            monkeypatch.setattr(Lifecycle, "touch", pause)
            admission = asyncio.create_task(
                repository.admit(record, [("datasets", data.id), ("models", model.id)])
            )
            await asyncio.wait_for(entered.wait(), 5)
            deletion = asyncio.create_task(
                deletions.delete(
                    "demo",
                    "models",
                    model.id,
                    DeletionRequest(preview_sha256=preview.preview_sha256),
                    "racing",
                )
            )
            await asyncio.sleep(0.05)
            release.set()
            assert (await admission).id == record.id
            with pytest.raises(ApiError) as caught:
                await deletion
            assert caught.value.code in {"deletion_blocked", "deletion_preview_stale"}
            assert await db.models.find_one({"_id": model.id}) is not None
            assert await db[collection].find_one({"_id": record.id}) is not None
            assert await db.deletions.count_documents({}) == 0

    asyncio.run(run())


@pytest.mark.parametrize(
    "collection", ["experiments", "tuning_jobs", "model_versions", "monitoring_observations"]
)
def test_deletion_first_fences_all_new_reference_writes(tmp_path, monkeypatch, collection):
    async def run():
        async with environment(tmp_path) as (settings, db, store, deletions):
            data = await dataset(store, settings)
            model = await store.models.insert(ModelRecord(project_id="demo", name="classifier"))
            preview = await deletions.preview("demo", "models", model.id)
            entered, release = asyncio.Event(), asyncio.Event()
            original = DeletionStore.clean

            async def pause(self, *args):
                entered.set()
                await release.wait()
                return await original(self, *args)

            monkeypatch.setattr(DeletionStore, "clean", pause)
            deletion = asyncio.create_task(
                deletions.delete(
                    "demo",
                    "models",
                    model.id,
                    DeletionRequest(preview_sha256=preview.preview_sha256),
                    "deletion-first",
                )
            )
            await asyncio.wait_for(entered.wait(), 5)
            record = ExperimentRecord(
                project_id="demo",
                dataset_id=data.id,
                model_id=model.id,
                submission_key="must-not-exist",
                request_hash="e" * 64,
            )
            try:
                with pytest.raises(ApiError) as caught:
                    await Lifecycle(db).insert(collection, record, [("models", model.id)])
                assert caught.value.code == "deletion_in_progress"
                assert await db[collection].count_documents({}) == 0
            finally:
                release.set()
                assert (await deletion).status == "complete"

    asyncio.run(run())


@pytest.mark.parametrize(
    "phase", ["before_cleanup", "after_file", "after_metadata", "after_complete"]
)
def test_process_death_at_every_durable_cleanup_boundary_resumes(tmp_path, phase):
    async def run():
        async with environment(tmp_path) as (settings, db, store, deletions):
            data = await dataset(store, settings)
            preview = await deletions.preview("demo", "datasets", data.id)
            marker = tmp_path / "deletion-process.json"
            process = await asyncio.to_thread(
                subprocess.Popen,
                [
                    sys.executable,
                    "-m",
                    "tests.integration.deletion_crash_process",
                    "--database",
                    settings.mongodb_database,
                    "--dataset-root",
                    str(settings.dataset_root),
                    "--artifact-root",
                    str(settings.artifact_root),
                    "--record-id",
                    data.id,
                    "--preview-sha256",
                    preview.preview_sha256,
                    "--marker",
                    str(marker),
                    "--phase",
                    phase,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            child = None
            try:

                async def wait_phase():
                    nonlocal child
                    while True:
                        if marker.exists():
                            try:
                                saved = json.loads(marker.read_text(encoding="utf-8"))
                                child = saved["pid"]
                                if saved["phase"] == phase:
                                    return
                            except json.JSONDecodeError:
                                pass
                        if process.poll() is not None:
                            output, error = process.communicate()
                            raise AssertionError(output + error)
                        await asyncio.sleep(0.05)

                await asyncio.wait_for(wait_phase(), 20)
                os.kill(child, getattr(signal, "SIGKILL", signal.SIGTERM))
                await asyncio.to_thread(process.wait, 10)
                saved = await db.deletions.find_one({"project_id": "demo"})
                assert saved is not None
                status = (await deletions.get("demo", saved["_id"])).status
                assert status == (
                    "complete"
                    if phase == "after_complete"
                    else "preparing"
                    if phase == "before_cleanup"
                    else "cleaning"
                )
                resumed = await deletions.delete(
                    "demo",
                    "datasets",
                    data.id,
                    DeletionRequest(preview_sha256=preview.preview_sha256),
                    "crash-test",
                )
                assert resumed.status == "complete"
                assert await db.datasets.count_documents({}) == 0
                assert not (settings.dataset_root / data.uri).exists()
                assert await db.deletion_items.count_documents({}) == 0
                assert await store.lifecycle.generation("demo") == 2
            finally:
                if process.poll() is None:
                    if child is not None:
                        os.kill(child, getattr(signal, "SIGKILL", signal.SIGTERM))
                    else:
                        process.terminate()
                await asyncio.to_thread(process.communicate, timeout=10)

    asyncio.run(run())
