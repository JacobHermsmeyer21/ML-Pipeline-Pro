"""Tuning-owned MongoDB collections and atomic worker control."""

import asyncio
from datetime import UTC, datetime, timedelta

from fastapi import Request
from pymongo import ASCENDING, DESCENDING, ReturnDocument

from ml_pipeline_pro.repositories import MongoRepository
from ml_pipeline_pro.tuning_schemas import TrialRecord, TrialReservation, TuningRecord


class TuningJobRepository(MongoRepository[TuningRecord]):
    async def by_submission(self, project_id: str, submission_key: str):
        document = await self.collection.find_one(
            {"project_id": project_id, "submission_key": submission_key}
        )
        return self._decode(document) if document else None

    async def mark_dispatched(self, project_id: str, job_id: str) -> None:
        now = datetime.now(UTC)
        await self.collection.update_one(
            {"_id": job_id, "project_id": project_id, "status": "queued"},
            {"$set": {"last_dispatch_at": now, "updated_at": now}},
        )

    async def request_cancel(self, project_id: str, job_id: str):
        now = datetime.now(UTC)
        document = await self.collection.find_one_and_update(
            {"_id": job_id, "project_id": project_id, "status": {"$in": ["queued", "running"]}},
            [
                {
                    "$set": {
                        "status": {
                            "$cond": [
                                {"$eq": ["$status", "queued"]},
                                "cancelled",
                                "cancel_requested",
                            ]
                        },
                        "completed_at": {
                            "$cond": [{"$eq": ["$status", "queued"]}, now, "$completed_at"]
                        },
                        "phase": {"$cond": [{"$eq": ["$status", "queued"]}, "complete", "$phase"]},
                        "stop_reason": "cancelled",
                        "updated_at": now,
                    }
                }
            ],
            return_document=ReturnDocument.AFTER,
        )
        return self._decode(document) if document else await self.get(project_id, job_id)

    async def claim(
        self, project_id: str, job_id: str, token: str, *, lease_seconds: int, max_attempts: int
    ):
        now = datetime.now(UTC)
        eligible = {
            "$or": [
                {"status": "queued"},
                {
                    "status": {"$in": ["running", "cancel_requested"]},
                    "lease_expires_at": {"$lte": now},
                },
            ]
        }
        identity = {"_id": job_id, "project_id": project_id, **eligible}
        await self.collection.update_one(
            {**identity, "attempts": {"$gte": max_attempts}},
            [
                {
                    "$set": {
                        "status": {
                            "$cond": [
                                {"$eq": ["$status", "cancel_requested"]},
                                "cancelled",
                                "failed",
                            ]
                        },
                        "phase": "complete",
                        "completed_at": now,
                        "updated_at": now,
                        "error_summary": "Worker recovery attempt limit was exhausted",
                        "worker_token": None,
                        "lease_expires_at": None,
                    }
                }
            ],
        )
        milliseconds = {"$multiply": ["$limits.max_runtime_seconds", 1000]}
        reserve_ms = {"$min": [10000, {"$multiply": ["$limits.max_runtime_seconds", 100]}]}
        document = await self.collection.find_one_and_update(
            {**identity, "attempts": {"$lt": max_attempts}},
            [
                {
                    "$set": {
                        "status": {
                            "$cond": [
                                {"$eq": ["$status", "cancel_requested"]},
                                "cancel_requested",
                                "running",
                            ]
                        },
                        "worker_token": token,
                        "lease_expires_at": now + timedelta(seconds=lease_seconds),
                        "heartbeat_at": now,
                        "updated_at": now,
                        "started_at": {"$ifNull": ["$started_at", now]},
                        "deadline_at": {"$ifNull": ["$deadline_at", {"$add": [now, milliseconds]}]},
                        "search_deadline_at": {
                            "$ifNull": [
                                "$search_deadline_at",
                                {"$add": [now, {"$subtract": [milliseconds, reserve_ms]}]},
                            ]
                        },
                        "attempts": {"$add": ["$attempts", 1]},
                    }
                }
            ],
            return_document=ReturnDocument.AFTER,
        )
        return self._decode(document) if document else None

    def _owner(self, project_id: str, job_id: str, token: str):
        return {
            "_id": job_id,
            "project_id": project_id,
            "worker_token": token,
            "status": {"$in": ["running", "cancel_requested"]},
        }

    async def heartbeat(self, project_id: str, job_id: str, token: str, lease_seconds: int) -> bool:
        now = datetime.now(UTC)
        result = await self.collection.update_one(
            self._owner(project_id, job_id, token),
            {
                "$set": {
                    "heartbeat_at": now,
                    "updated_at": now,
                    "lease_expires_at": now + timedelta(seconds=lease_seconds),
                }
            },
        )
        return result.matched_count == 1

    async def reserve(
        self, project_id: str, job_id: str, token: str, reservation: TrialReservation
    ) -> bool:
        now = datetime.now(UTC)
        result = await self.collection.update_one(
            {
                **self._owner(project_id, job_id, token),
                "status": "running",
                "phase": "searching",
                "reservation": None,
                "scheduled_trials": reservation.number,
                "search_deadline_at": {"$gt": now},
                "$expr": {"$lt": ["$scheduled_trials", "$limits.max_trials"]},
            },
            {
                "$set": {"reservation": reservation.model_dump(), "updated_at": now},
                "$inc": {"scheduled_trials": 1},
            },
        )
        return result.matched_count == 1

    async def progress(
        self, project_id: str, job_id: str, token: str, *, number: int | None, values: dict
    ) -> bool:
        query = self._owner(project_id, job_id, token)
        if number is not None:
            query["reservation.number"] = number
            values = {**values, "reservation": None}
        result = await self.collection.update_one(
            query, {"$set": {**values, "updated_at": datetime.now(UTC)}}
        )
        return result.matched_count == 1

    async def finish(self, project_id: str, job_id: str, token: str, *, values: dict) -> bool:
        if values.get("status") not in {"succeeded", "failed", "cancelled"}:
            raise ValueError("Tuning completion requires a terminal status")
        now = datetime.now(UTC)
        result = await self.collection.update_one(
            self._owner(project_id, job_id, token),
            [
                {
                    "$set": {
                        **values,
                        "status": {
                            "$cond": [
                                {"$eq": ["$status", "cancel_requested"]},
                                "cancelled",
                                values["status"],
                            ]
                        },
                        "stop_reason": {
                            "$cond": [
                                {"$eq": ["$status", "cancel_requested"]},
                                "cancelled",
                                values.get("stop_reason", "$stop_reason"),
                            ]
                        },
                        "phase": "complete",
                        "completed_at": now,
                        "updated_at": now,
                        "worker_token": None,
                        "lease_expires_at": None,
                    }
                }
            ],
        )
        return result.matched_count == 1

    async def refresh_terminal_progress(self, project_id: str, job_id: str, values: dict) -> None:
        await self.collection.update_one(
            {
                "_id": job_id,
                "project_id": project_id,
                "status": {"$in": ["failed", "cancelled"]},
                "worker_token": None,
            },
            {"$set": {**values, "reservation": None, "updated_at": datetime.now(UTC)}},
        )

    async def pending_recovery(self):
        now = datetime.now(UTC)
        cursor = (
            self.collection.find(
                {
                    "$or": [
                        {
                            "status": "queued",
                            "$or": [
                                {"last_dispatch_at": None},
                                {"last_dispatch_at": {"$lte": now - timedelta(seconds=60)}},
                            ],
                        },
                        {
                            "status": {"$in": ["running", "cancel_requested"]},
                            "lease_expires_at": {"$lte": now},
                        },
                    ]
                }
            )
            .sort("created_at", 1)
            .limit(100)
        )
        return [self._decode(document) async for document in cursor]


class TrialRepository(MongoRepository[TrialRecord]):
    async def for_job(self, project_id: str, job_id: str, *, limit: int = 50, offset: int = 0):
        cursor = (
            self.collection.find({"project_id": project_id, "tuning_job_id": job_id})
            .sort("number", 1)
            .skip(offset)
            .limit(limit)
        )
        return [self._decode(document) async for document in cursor]

    async def claim(self, project_id: str, trial_id: str, token: str):
        now = datetime.now(UTC)
        document = await self.collection.find_one_and_update(
            {"_id": trial_id, "project_id": project_id, "status": {"$in": ["queued", "running"]}},
            {
                "$set": {"status": "running", "worker_token": token, "updated_at": now},
            },
            return_document=ReturnDocument.AFTER,
        )
        return self._decode(document) if document else await self.get(project_id, trial_id)

    async def finish(self, project_id: str, trial_id: str, token: str, *, values: dict) -> bool:
        if values.get("status") not in {"succeeded", "failed", "cancelled"}:
            raise ValueError("Trial completion requires a terminal status")
        result = await self.collection.update_one(
            {"_id": trial_id, "project_id": project_id, "status": "running", "worker_token": token},
            {
                "$set": {
                    **values,
                    "completed_at": datetime.now(UTC),
                    "worker_token": None,
                    "updated_at": datetime.now(UTC),
                }
            },
        )
        return result.matched_count == 1

    async def stop_incomplete(
        self, project_id: str, job_id: str, status: str, reason: str, token: str | None = None
    ) -> None:
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
                    "worker_token": None,
                }
            },
        )


class TuningStore:
    def __init__(self, database) -> None:
        self.jobs = TuningJobRepository(database, "tuning_jobs", TuningRecord)
        self.trials = TrialRepository(database, "trials", TrialRecord)
        self._indexed = False
        self._lock = asyncio.Lock()

    async def ensure_indexes(self) -> None:
        async with self._lock:
            if self._indexed:
                return
            await self.jobs.collection.create_index(
                [("project_id", ASCENDING), ("submission_key", ASCENDING)],
                unique=True,
                name="tuning_submission",
            )
            await self.jobs.collection.create_index(
                [("project_id", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)],
                name="tuning_project_status_created",
            )
            await self.jobs.collection.create_index(
                [
                    ("status", ASCENDING),
                    ("lease_expires_at", ASCENDING),
                    ("last_dispatch_at", ASCENDING),
                ],
                name="tuning_recovery",
            )
            await self.jobs.collection.create_index(
                [("project_id", ASCENDING), ("created_at", DESCENDING), ("_id", DESCENDING)],
                name="project_created_id",
            )
            await self.trials.collection.create_index(
                [("project_id", ASCENDING), ("tuning_job_id", ASCENDING), ("number", ASCENDING)],
                unique=True,
                name="tuning_trial_number",
            )
            self._indexed = True


async def get_tuning_store(request: Request) -> TuningStore:
    if not hasattr(request.app.state, "tuning_store"):
        database = request.app.state.connections.mongo.get_database(
            request.app.state.settings.mongodb_database
        )
        request.app.state.tuning_store = TuningStore(database)
    store = request.app.state.tuning_store
    await store.ensure_indexes()
    return store
