"""Atomic experiment ownership and durable dispatch metadata."""

from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo import ReturnDocument

from ml_pipeline_pro.ownership import tuning_write
from ml_pipeline_pro.repositories import MongoRepository
from ml_pipeline_pro.schemas import ExperimentRecord
from ml_pipeline_pro.training_control import OwnershipLost


class ExperimentRepository(MongoRepository[ExperimentRecord]):
    async def insert(self, record: ExperimentRecord) -> ExperimentRecord:
        if record.tuning_job_id is None:
            return await super().insert(record)
        if record.worker_token is None:
            raise OwnershipLost()

        async def write(session):
            document = record.model_dump()
            document["_id"] = document.pop("id")
            await self.collection.insert_one(document, session=session)
            return record

        result = await tuning_write(
            self.database, record.project_id, record.tuning_job_id, record.worker_token, write
        )
        if result is None:
            raise OwnershipLost()
        return result

    async def by_submission(self, project_id: str, submission_key: str) -> ExperimentRecord | None:
        document = await self.collection.find_one(
            {"project_id": project_id, "submission_key": submission_key}
        )
        return self._decode(document) if document else None

    async def mark_dispatched(self, project_id: str, experiment_id: str) -> None:
        now = datetime.now(UTC)
        await self.collection.update_one(
            {
                "_id": experiment_id,
                "project_id": project_id,
                "status": "queued",
                "tuning_job_id": None,
            },
            {"$set": {"last_dispatch_at": now, "updated_at": now}},
        )

    async def claim(
        self,
        project_id: str,
        experiment_id: str,
        token: str,
        *,
        lease_seconds: int,
        max_attempts: int,
        tuning_job_id: str | None = None,
    ) -> ExperimentRecord | None:
        now = datetime.now(UTC)
        eligible = {
            "$or": [
                {"status": "queued"},
                {"status": "running", "lease_expires_at": {"$lte": now}},
            ]
        }
        if tuning_job_id is not None:
            eligible["$or"].append({"status": "running", "tuning_job_id": tuning_job_id})
        identity = {
            "_id": experiment_id,
            "project_id": project_id,
            "tuning_job_id": tuning_job_id,
            **eligible,
        }

        async def write(session):
            return await self._claim(identity, token, now, lease_seconds, max_attempts, session)

        if tuning_job_id is not None:
            return await tuning_write(self.database, project_id, tuning_job_id, token, write)
        return await write(None)

    async def _claim(self, identity, token, now, lease_seconds, max_attempts, session):
        await self.collection.update_one(
            {**identity, "attempts": {"$gte": max_attempts}},
            {
                "$set": {
                    "status": "failed",
                    "completed_at": now,
                    "updated_at": now,
                    "error_summary": "Worker recovery attempt limit was exhausted",
                    "worker_token": None,
                    "lease_expires_at": None,
                }
            },
            session=session,
        )
        document = await self.collection.find_one_and_update(
            {**identity, "attempts": {"$lt": max_attempts}},
            {
                "$set": {
                    "status": "running",
                    "worker_token": token,
                    "lease_expires_at": now + timedelta(seconds=lease_seconds),
                    "heartbeat_at": now,
                    "started_at": now,
                    "updated_at": now,
                    "error_summary": None,
                },
                "$inc": {"attempts": 1},
            },
            return_document=ReturnDocument.AFTER,
            session=session,
        )
        return self._decode(document) if document else None

    async def heartbeat(
        self, project_id: str, experiment_id: str, token: str, lease_seconds: int
    ) -> bool:
        now = datetime.now(UTC)
        query = {
            "_id": experiment_id,
            "project_id": project_id,
            "status": "running",
            "worker_token": token,
        }
        update = {
            "$set": {
                "heartbeat_at": now,
                "updated_at": now,
                "lease_expires_at": now + timedelta(seconds=lease_seconds),
            }
        }
        return await self._owned_update(project_id, experiment_id, token, query, update)

    async def _owned_update(self, project_id, experiment_id, token, query, update):
        record = await self.get(project_id, experiment_id)
        if record is None:
            return False

        async def write(session):
            result = await self.collection.update_one(query, update, session=session)
            return result.matched_count == 1

        if record.tuning_job_id is not None:
            return bool(
                await tuning_write(self.database, project_id, record.tuning_job_id, token, write)
            )
        return await write(None)

    async def finish(
        self, project_id: str, experiment_id: str, token: str, *, values: dict[str, Any]
    ) -> bool:
        if values.get("status") not in {"succeeded", "failed", "cancelled"}:
            raise ValueError("Running experiments require a terminal completion status")
        now = datetime.now(UTC)
        return await self._owned_update(
            project_id,
            experiment_id,
            token,
            {
                "_id": experiment_id,
                "project_id": project_id,
                "status": "running",
                "worker_token": token,
            },
            {
                "$set": {
                    **values,
                    "completed_at": now,
                    "updated_at": now,
                    "worker_token": None,
                    "lease_expires_at": None,
                }
            },
        )

    async def pending_recovery(self) -> list[ExperimentRecord]:
        now = datetime.now(UTC)
        cursor = (
            self.collection.find(
                {
                    "tuning_job_id": None,
                    "$or": [
                        {
                            "status": "queued",
                            "$or": [
                                {"last_dispatch_at": None},
                                {"last_dispatch_at": {"$lte": now - timedelta(seconds=60)}},
                            ],
                        },
                        {"status": "running", "lease_expires_at": {"$lte": now}},
                    ],
                }
            )
            .sort("created_at", 1)
            .limit(100)
        )
        return [self._decode(document) async for document in cursor]

    async def finish_tuning_test(
        self, project_id: str, experiment_id: str, job_id: str, token: str, *, values: dict
    ) -> bool:
        async def write(session):
            result = await self.collection.update_one(
                {
                    "_id": experiment_id,
                    "project_id": project_id,
                    "status": "succeeded",
                    "tuning_job_id": job_id,
                    "test_evaluated": {"$ne": True},
                },
                {"$set": {**values, "test_evaluated": True, "updated_at": datetime.now(UTC)}},
                session=session,
            )
            return result.matched_count == 1

        return bool(await tuning_write(self.database, project_id, job_id, token, write))

    async def stop_for_tuning(
        self, project_id: str, job_id: str, status: str, reason: str, token: str | None = None
    ) -> bool:
        if status not in {"failed", "cancelled"}:
            raise ValueError("Interrupted tuning experiments must fail or be cancelled")
        query = {
            "project_id": project_id,
            "tuning_job_id": job_id,
            "status": {"$in": ["queued", "running"]},
        }
        if token is not None:
            query["worker_token"] = token

        async def write(session):
            await self.collection.update_many(
                query,
                {
                    "$set": {
                        "status": status,
                        "error_summary": reason,
                        "completed_at": datetime.now(UTC),
                        "updated_at": datetime.now(UTC),
                        "worker_token": None,
                        "lease_expires_at": None,
                    }
                },
                session=session,
            )
            return True

        return bool(
            await tuning_write(
                self.database, project_id, job_id, token, write, terminal=token is None
            )
        )

    async def filtered_list(
        self, project_id: str, *, limit: int, offset: int, status: str | None, model_id: str | None
    ) -> list[ExperimentRecord]:
        query = {"project_id": project_id}
        if status is not None:
            query["status"] = status
        if model_id is not None:
            query["model_id"] = model_id
        cursor = (
            self.collection.find(query)
            .sort([("created_at", -1), ("_id", -1)])
            .skip(offset)
            .limit(limit)
        )
        return [self._decode(document) async for document in cursor]
