"""Bounded project-scoped monitoring; no training or ownership mutations."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import NAMESPACE_URL, uuid5

from fastapi import Depends, Request
from prometheus_client import CollectorRegistry, Gauge, generate_latest
from pymongo.errors import DuplicateKeyError

from ml_pipeline_pro.access import project_access
from ml_pipeline_pro.conversation_schemas import fingerprint
from ml_pipeline_pro.errors import ApiError
from ml_pipeline_pro.monitoring_schemas import (
    MonitoringSummary,
    ObservationCreate,
    ObservationRecord,
)
from ml_pipeline_pro.repositories import MongoRepository

WINDOW_LIMIT = 100


def snapshot_time() -> datetime:
    now = datetime.now(UTC)
    return now.replace(microsecond=now.microsecond // 1000 * 1000)


class MonitoringStore:
    def __init__(self, database):
        self.observations = MongoRepository(database, "monitoring_observations", ObservationRecord)
        self._lock = asyncio.Lock()
        self._indexed = False

    async def ensure_indexes(self):
        async with self._lock:
            if self._indexed:
                return
            await self.observations.collection.create_index(
                [("project_id", 1), ("model_version_id", 1), ("observed_at", -1), ("_id", -1)],
                name="monitoring_project_version_observed",
            )
            await self.observations.collection.create_index(
                [("project_id", 1), ("created_at", -1), ("_id", -1)], name="project_created_id"
            )
            await self.observations.collection.create_index(
                [("project_id", 1), ("observed_at", -1), ("_id", -1)],
                name="monitoring_project_observed",
            )
            self._indexed = True

    async def insert(
        self, project: str, body: ObservationCreate, *, now: datetime | None = None
    ) -> ObservationRecord:
        identity = str(uuid5(NAMESPACE_URL, f"mlpp-monitoring:{project}:{body.sample_id}"))
        input_hash = fingerprint(body.model_dump())
        existing = await self.observations.get(project, identity)
        if existing is not None:
            if existing.input_hash != input_hash:
                raise ApiError(409, "observation_conflict", "Sample ID already has different input")
            return existing
        now = now or datetime.now(UTC)
        if not body.timely(now):
            raise ApiError(
                422, "invalid_observation_time", "Observation must be within the last day"
            )
        now = now.replace(microsecond=now.microsecond // 1000 * 1000)
        record = ObservationRecord(
            id=identity,
            project_id=project,
            input_hash=input_hash,
            created_at=now,
            updated_at=now,
            **body.model_dump(),
        )
        try:
            return await self.observations.admit(
                record, [("model_versions", body.model_version_id)]
            )
        except DuplicateKeyError:
            existing = await self.observations.get(project, identity)
            if existing is None or existing.input_hash != record.input_hash:
                raise ApiError(
                    409, "observation_conflict", "Sample ID already has different input"
                ) from None
            return existing

    async def window(self, project: str, version: str | None, seconds: int, now: datetime):
        query = {
            "project_id": project,
            "observed_at": {"$gte": now - timedelta(seconds=seconds), "$lte": now},
        }
        if version is not None:
            query["model_version_id"] = version
        cursor = (
            self.observations.collection.find(query)
            .sort([("observed_at", -1), ("_id", -1)])
            .limit(WINDOW_LIMIT + 1)
        )
        return [self.observations._decode(document) async for document in cursor]


async def get_monitoring_store(
    request: Request, project_id: Annotated[str, Depends(project_access)]
) -> MonitoringStore:
    if not hasattr(request.app.state, "monitoring_store"):
        settings = request.app.state.settings
        request.app.state.monitoring_store = MonitoringStore(
            request.app.state.connections.mongo.get_database(settings.mongodb_database)
        )
    store = request.app.state.monitoring_store
    await store.ensure_indexes()
    return store


def summarize(records: list[ObservationRecord], version: str, seconds: int, now: datetime):
    partial = len(records) > WINDOW_LIMIT
    records = records[:WINDOW_LIMIT]
    labeled = [
        record.prediction_correct for record in records if record.prediction_correct is not None
    ]
    maximum = max((record.latency_ms for record in records), default=None)
    return MonitoringSummary(
        model_version_id=version,
        as_of=now,
        window_seconds=seconds,
        observation_ids=[record.id for record in records],
        sample_count=len(records),
        partial=partial,
        availability="observed" if records else "missing",
        latest_observed_at=max((record.observed_at for record in records), default=None),
        mean_latency_ms=sum(record.latency_ms for record in records) / len(records)
        if records
        else None,
        max_latency_ms=maximum,
        error_count=sum(record.outcome == "error" for record in records),
        labeled_count=len(labeled),
        labeled_accuracy=sum(labeled) / len(labeled) if labeled else None,
        seeded_count=sum(record.fault == "seeded_latency" for record in records),
        issue="unknown"
        if maximum is None
        else "latency_threshold_exceeded"
        if maximum > 100
        else "no_threshold_exceedance",
    )


def metrics(records: list[ObservationRecord], now: datetime) -> bytes:
    """One bounded project window; use a fresh registry, safe across API replicas."""
    registry = CollectorRegistry()
    partial = len(records) > WINDOW_LIMIT
    records = records[:WINDOW_LIMIT]
    global_partial = Gauge("mlpp_monitoring_partial", "Project window is capped", registry=registry)
    global_partial.set(partial)
    Gauge("mlpp_monitoring_samples", "Samples in bounded project window", registry=registry).set(
        len(records)
    )
    definitions = {
        "max_latency_ms": "Maximum observed workload latency in milliseconds",
        "mean_latency_ms": "Mean observed workload latency in milliseconds",
        "error_count": "Errors in bounded window",
        "labeled_count": "Labeled observations in bounded window",
        "labeled_accuracy": "Accuracy among labeled observations only",
        "seeded_count": "Declared seeded latency observations",
        "latency_issue": "Maximum observed latency exceeds 100 milliseconds",
        "latest_timestamp": "Unix timestamp of latest measured observation",
    }
    gauges = {
        key: Gauge(f"mlpp_workload_{key}", text, ["model_version_id"], registry=registry)
        for key, text in definitions.items()
    }
    for version in sorted({record.model_version_id for record in records}):
        summary = summarize(
            [record for record in records if record.model_version_id == version], version, 300, now
        )
        values = {
            key: getattr(summary, key)
            for key in definitions
            if key not in {"latency_issue", "latest_timestamp"}
        }
        values["latency_issue"] = int(summary.issue == "latency_threshold_exceeded")
        values["latest_timestamp"] = summary.latest_observed_at.timestamp()
        for key, value in values.items():
            if value is not None:
                gauges[key].labels(model_version_id=version).set(value)
    return generate_latest(registry)


MONITORING_INSTRUCTIONS = (
    "Explain the supplied measured classification workload window. Return one JSON object with "
    "interpretation, observation_ids and proposed_checks. Treat measurements as observations, "
    "not proof of cause. Describe seeded_count as a declared artificial latency injection. "
    "Missing labels mean unknown accuracy. Partial windows are incomplete evidence. "
    "Cite only supplied observation IDs. Propose human checks, never execute changes. "
    "Cite one to three IDs, and keep the interpretation under 120 words. A seeded delay does "
    "not establish system stress or resource contention; distinguish the declared injection "
    "from unknown underlying causes. "
    "For declared seeded latency propose inspect_seeded_delay; other allowed checks are "
    "profile_inference, check_resources, collect_labels. No tool calls, commands or extra keys."
)
