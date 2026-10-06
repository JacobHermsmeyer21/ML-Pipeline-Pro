"""Atomic experiment ownership and durable dispatch metadata."""

from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo import ReturnDocument

from ml_pipeline_pro.repositories import MongoRepository
from ml_pipeline_pro.schemas import ExperimentRecord


class ExperimentRepository(MongoRepository[ExperimentRecord]):
    async def by_submission(self, project_id: str, submission_key: str) -> ExperimentRecord | None:
        document = await self.collection.find_one(
            {"project_id": project_id, "submission_key": submission_key}
        )
        return self._decode(document) if document else None

    async def mark_dispatched(self, project_id: str, experiment_id: str) -> None:
        now = datetime.now(UTC)
        await self.collection.update_one(
            {"_id": experiment_id, "project_id": project_id, "status": "queued"},
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
        identity = {"_id": experiment_id, "project_id": project_id, **eligible}
        if tuning_job_id is not None:
            identity["tuning_job_id"] = tuning_job_id
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
        )
        return self._decode(document) if document else None

    async def heartbeat(
        self, project_id: str, experiment_id: str, token: str, lease_seconds: int
    ) -> bool:
        now = datetime.now(UTC)
        result = await self.collection.update_one(
            {
                "_id": experiment_id,
                "project_id": project_id,
                "status": "running",
                "worker_token": token,
            },
            {
                "$set": {
                    "heartbeat_at": now,
                    "updated_at": now,
                    "lease_expires_at": now + timedelta(seconds=lease_seconds),
                }
            },
        )
        return result.matched_count == 1

    async def finish(
        self, project_id: str, experiment_id: str, token: str, *, values: dict[str, Any]
    ) -> bool:
        if values.get("status") not in {"succeeded", "failed", "cancelled"}:
            raise ValueError("Running experiments require a terminal completion status")
        now = datetime.now(UTC)
        result = await self.collection.update_one(
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
        return result.matched_count == 1

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
        self, project_id: str, experiment_id: str, job_id: str, *, values: dict
    ) -> bool:
        result = await self.collection.update_one(
            {
                "_id": experiment_id,
                "project_id": project_id,
                "status": "succeeded",
                "tuning_job_id": job_id,
                "test_evaluated": {"$ne": True},
            },
            {"$set": {**values, "test_evaluated": True, "updated_at": datetime.now(UTC)}},
        )
        return result.matched_count == 1

    async def stop_for_tuning(
        self, project_id: str, job_id: str, status: str, reason: str, token: str | None = None
    ) -> None:
        if status not in {"failed", "cancelled"}:
            raise ValueError("Interrupted tuning experiments must fail or be cancelled")
        query = {
            "project_id": project_id,
            "tuning_job_id": job_id,
            "status": {"$in": ["queued", "running"]},
        }
        if token is not None:
            query["worker_token"] = token
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
