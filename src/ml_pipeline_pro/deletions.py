"""Durable, scoped erasure; filesystem work is outside retryable transactions."""

import asyncio
import hashlib
import json
from contextlib import ExitStack
from datetime import UTC, datetime
from uuid import uuid4

from filelock import Timeout
from pymongo import ASCENDING
from pymongo.errors import PyMongoError

from ml_pipeline_pro.deletion_files import plan_files, remove_entry, storage_identity
from ml_pipeline_pro.deletion_schemas import DeletionCounts, DeletionPreview, DeletionResult
from ml_pipeline_pro.errors import ApiError
from ml_pipeline_pro.lifecycle import Lifecycle, busy, key_digest
from ml_pipeline_pro.storage_control import (
    attempt_directory,
    finish_owned,
    native_lock,
    publication_lock,
)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def result(document):
    return DeletionResult.model_validate(
        {key: document.get(key) for key in DeletionResult.model_fields}
    )


class DeletionStore:
    def __init__(self, database, settings):
        self.database, self.settings = database, settings
        self.lifecycle = Lifecycle(database)
        self.operations = database.deletions
        self.items = database.deletion_items

    async def ensure_indexes(self):
        await self.operations.create_index(
            [("project_id", ASCENDING), ("key_digest", ASCENDING)],
            unique=True,
            name="deletion_submission",
        )
        await self.items.create_index(
            [("project_id", ASCENDING), ("collection", ASCENDING), ("record_id", ASCENDING)],
            name="deletion_record",
        )
        await self.items.create_index(
            [("operation_id", ASCENDING), ("entry_type", ASCENDING), ("done", ASCENDING)],
            name="deletion_progress",
        )
        await self.database.deleted_submissions.create_index(
            [("project_id", ASCENDING), ("collection", ASCENDING), ("key_digest", ASCENDING)],
            unique=True,
            name="deleted_submission",
        )

    async def snapshot(self, project, kind, identity, session):
        db = self.database
        root = await db[kind].find_one({"_id": identity, "project_id": project}, session=session)
        if root is None:
            label = "dataset" if kind == "datasets" else "model"
            raise ApiError(
                404, f"{label}_not_found", f"{label.title()} was not found in this project"
            )

        async def find(collection, query):
            cursor = (
                db[collection]
                .find({"project_id": project, **query}, session=session)
                .sort("_id", 1)
            )
            return [document async for document in cursor]

        field = "dataset_id" if kind == "datasets" else "model_id"
        jobs = await find("tuning_jobs", {field: identity})
        job_ids = [doc["_id"] for doc in jobs]
        experiments = await find(
            "experiments",
            {
                "$or": [
                    {field: identity},
                    {"tuning_job_id": {"$in": job_ids}},
                ]
            },
        )
        experiment_ids = [doc["_id"] for doc in experiments]
        versions = await find(
            "model_versions",
            {
                "$or": [
                    {"experiment_id": {"$in": experiment_ids}},
                    {"model_id": identity} if kind == "models" else {"_id": {"$in": []}},
                ]
            },
        )
        records = {
            kind: [root],
            "experiments": experiments,
            "tuning_jobs": jobs,
            "trials": await find(
                "trials",
                {
                    "$or": [
                        {"tuning_job_id": {"$in": job_ids}},
                        {"experiment_id": {"$in": experiment_ids}},
                    ]
                },
            ),
            "model_versions": versions,
            "monitoring_observations": await find(
                "monitoring_observations",
                {
                    "model_version_id": {"$in": [doc["_id"] for doc in versions]},
                },
            ),
        }
        # Preserve all registered aliases, including legacy cross-project references.
        survivors = [
            doc
            async for doc in db.datasets.find(
                {"$nor": [{"project_id": project, "_id": identity}]} if kind == "datasets" else {},
                session=session,
            )
        ]
        active = sum(
            doc.get("status") in {"queued", "running", "cancel_requested"}
            for doc in [*experiments, *jobs]
        )
        for job in jobs:
            reservation = job.get("reservation")
            if reservation:
                experiment_ids.append(reservation["experiment_id"])
        return records, survivors, sorted(set(experiment_ids)), active

    def file_plan(self, project, records, survivors, experiment_ids):
        return plan_files(
            self.settings, project, records.get("datasets", []), survivors, experiment_ids
        )

    def preview_value(self, kind, identity, snapshot, files):
        records, _, _, active = snapshot
        _, file_counts, signatures = files
        counts = DeletionCounts(**{key: len(docs) for key, docs in records.items()}, **file_counts)
        root = records[kind][0]
        return DeletionPreview(
            kind=kind,
            record_id=identity,
            name=root["name"],
            version=root.get("version"),
            counts=counts,
            active_jobs=active,
            preview_sha256=fingerprint([records, signatures, storage_identity(self.settings)]),
        )

    async def preview(self, project, kind, identity):
        try:
            return await self._preview(project, kind, identity)
        except OSError:
            raise ApiError(
                503, "deletion_storage_unavailable", "Deletion storage is unavailable"
            ) from None

    async def _preview(self, project, kind, identity):
        await self.lifecycle.generation(project)
        async with publication_lock(self.settings, project):

            async def read(session):
                return await self.snapshot(project, kind, identity, session)

            snapshot = await self.lifecycle.transaction(read)
            files = await finish_owned(asyncio.to_thread(self.file_plan, project, *snapshot[:3]))
            return self.preview_value(kind, identity, snapshot, files)

    async def get(self, project, operation_id):
        document = await self.operations.find_one({"_id": operation_id, "project_id": project})
        if document is None:
            raise ApiError(404, "deletion_not_found", "Deletion was not found in this project")
        return result(document)

    async def delete(self, project, kind, identity, request, key):
        await self.ensure_indexes()
        operation = None
        try:
            async with publication_lock(self.settings, project, wait=False):
                saved = await self.operations.find_one(
                    {"project_id": project, "key_digest": key_digest(key)}
                )
                request_hash = fingerprint([kind, identity, request.preview_sha256])
                if saved:
                    if saved["request_hash"] != request_hash:
                        raise ApiError(
                            409, "idempotency_conflict", "Deletion key has different input"
                        )
                    if saved["status"] == "complete":
                        return result(saved)
                    operation = saved
                    if saved["storage_identity"] != storage_identity(self.settings):
                        raise ApiError(409, "unsafe_storage_path", "Cleanup storage roots changed")
                    with ExitStack() as locks:
                        await self.lock_attempts(locks, project, saved["operation_id"])
                        return await self.clean(project, saved)

                await self.lifecycle.generation(project)

                async def read(session):
                    return await self.snapshot(project, kind, identity, session)

                snapshot = await self.lifecycle.transaction(read)
                if snapshot[3]:
                    raise ApiError(
                        409,
                        "deletion_blocked",
                        "Wait for related training and tuning jobs to finish",
                        {"active_jobs": snapshot[3]},
                    )
                with ExitStack() as locks:
                    resources = [("experiments", value) for value in snapshot[2]]
                    resources += [("tuning_jobs", doc["_id"]) for doc in snapshot[0]["tuning_jobs"]]
                    self.acquire_attempts(locks, project, resources)
                    files = await finish_owned(
                        asyncio.to_thread(self.file_plan, project, *snapshot[:3])
                    )
                    preview = self.preview_value(kind, identity, snapshot, files)
                    if preview.preview_sha256 != request.preview_sha256:
                        raise ApiError(
                            409,
                            "deletion_preview_stale",
                            "Dependencies changed; review deletion again",
                        )
                    operation = await self.begin(
                        project, kind, identity, snapshot, files, preview, key, request_hash
                    )
                    return await self.clean(project, operation)
        except (OSError, Timeout) as exc:
            if isinstance(exc, Timeout) and operation is None:
                raise ApiError(
                    409, "deletion_blocked", "A related worker is still using its files"
                ) from None
            raise ApiError(
                503,
                "deletion_cleanup_unavailable",
                "Cleanup is incomplete; retry the same deletion",
                {"operation_id": operation["operation_id"]} if operation else None,
            ) from None
        except PyMongoError:
            raise ApiError(
                503,
                "storage_unavailable",
                "Cleanup metadata is unavailable; retry the same deletion",
                {"operation_id": operation["operation_id"]} if operation else None,
            ) from None

    def acquire_attempts(self, locks, project, resources):
        for collection, identity in sorted(set(resources)):
            directory = attempt_directory(self.settings, project, collection, identity)
            if directory.exists():
                for path in sorted(directory.glob("*.lock")):
                    locks.enter_context(native_lock(path))

    async def lock_attempts(self, locks, project, operation_id):
        entries = [
            doc
            async for doc in self.items.find(
                {
                    "operation_id": operation_id,
                    "entry_type": "record",
                    "collection": {"$in": ["experiments", "tuning_jobs"]},
                }
            )
        ]
        self.acquire_attempts(
            locks, project, [(doc["collection"], doc["record_id"]) for doc in entries]
        )

    async def begin(self, project, kind, identity, snapshot, files, preview, key, request_hash):
        now = datetime.now(UTC)
        now = now.replace(microsecond=now.microsecond // 1000 * 1000)
        operation_id = str(uuid4())
        operation = {
            "_id": operation_id,
            "operation_id": operation_id,
            "project_id": project,
            "kind": kind,
            "record_id": identity,
            "status": "preparing",
            "counts": preview.counts.model_dump(),
            "created_at": now,
            "completed_at": None,
            "key_digest": key_digest(key),
            "request_hash": request_hash,
            "storage_identity": storage_identity(self.settings),
        }
        entries = []
        for collection, documents in snapshot[0].items():
            for doc in documents:
                item = {"collection": collection, "record_id": doc["_id"], "entry_type": "record"}
                if collection in {"experiments", "tuning_jobs"}:
                    item.update(
                        key_digest=key_digest(doc["submission_key"]),
                        request_hash=doc["request_hash"],
                    )
                entries.append(item)
        entries += [{"entry_type": "file", **entry} for entry in files[0]]
        for index, item in enumerate(entries):
            item.update(
                _id=f"{operation_id}:{index}",
                operation_id=operation_id,
                project_id=project,
                done=False,
            )

        async def commit(session):
            await self.lifecycle.touch(project, session)
            current = await self.snapshot(project, kind, identity, session)
            if fingerprint(current[:3]) != fingerprint(snapshot[:3]) or current[3]:
                raise ApiError(
                    409, "deletion_preview_stale", "Dependencies changed; review deletion again"
                )
            await self.operations.insert_one(operation, session=session)
            for offset in range(0, len(entries), 100):
                await self.items.insert_many(entries[offset : offset + 100], session=session)
            await self.lifecycle.gates.update_one(
                {"_id": project},
                {"$set": {"operation_id": operation_id}, "$inc": {"generation": 1}},
                session=session,
            )
            return operation

        return await self.lifecycle.transaction(commit)

    async def clean(self, project, operation):
        operation_id = operation["operation_id"]
        gate = await self.lifecycle.gates.find_one({"_id": project, "operation_id": operation_id})
        if gate is None:
            raise busy(operation_id)
        await self.operations.update_one({"_id": operation_id}, {"$set": {"status": "cleaning"}})
        async for item in self.items.find(
            {"operation_id": operation_id, "entry_type": "file", "done": False}
        ):
            await finish_owned(asyncio.to_thread(remove_entry, self.settings, project, item))
            await self.items.update_one({"_id": item["_id"]}, {"$set": {"done": True}})
        async for item in self.items.find(
            {"operation_id": operation_id, "entry_type": "record", "done": False}
        ):

            async def erase(session, item=item):
                gate = await self.lifecycle.gates.update_one(
                    {"_id": project, "operation_id": operation_id},
                    {"$inc": {"revision": 1}},
                    session=session,
                )
                if gate.matched_count != 1:
                    raise busy(operation_id)
                if item["collection"] in {"experiments", "tuning_jobs"}:
                    receipt = {
                        key: item[key]
                        for key in ("project_id", "collection", "key_digest", "request_hash")
                    }
                    await self.database.deleted_submissions.update_one(
                        {key: receipt[key] for key in ("project_id", "collection", "key_digest")},
                        {"$setOnInsert": receipt},
                        upsert=True,
                        session=session,
                    )
                await self.database[item["collection"]].delete_one(
                    {"_id": item["record_id"], "project_id": project}, session=session
                )
                await self.items.update_one(
                    {"_id": item["_id"]}, {"$set": {"done": True}}, session=session
                )

            await self.lifecycle.transaction(erase)
        completed_at = datetime.now(UTC)
        completed_at = completed_at.replace(microsecond=completed_at.microsecond // 1000 * 1000)

        async def complete(session):
            if await self.items.find_one(
                {"operation_id": operation_id, "done": False}, session=session
            ):
                raise busy(operation_id)
            await self.operations.update_one(
                {"_id": operation_id},
                {
                    "$set": {"status": "complete", "completed_at": completed_at},
                    "$unset": {"storage_identity": ""},
                },
                session=session,
            )
            await self.items.delete_many({"operation_id": operation_id}, session=session)
            await self.lifecycle.gates.update_one(
                {"_id": project, "operation_id": operation_id},
                {"$set": {"operation_id": None}, "$inc": {"generation": 1, "revision": 1}},
                session=session,
            )

        await self.lifecycle.transaction(complete)
        return await self.get(project, operation_id)
