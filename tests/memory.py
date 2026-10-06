"""Deterministic repository substitute for API and worker contract tests."""

from datetime import UTC, datetime, timedelta

from pymongo.errors import DuplicateKeyError


class MemoryRepository:
    def __init__(self, unique_fields=()) -> None:
        self.records = {}
        self.unique_fields = unique_fields
        self.error = None

    async def insert(self, record):
        if self.error:
            raise self.error
        identity = tuple(getattr(record, key) for key in self.unique_fields)
        for saved in self.records.values():
            if identity == tuple(getattr(saved, key) for key in self.unique_fields):
                raise DuplicateKeyError("Duplicate test identity")
        self.records[record.id] = record.model_copy(deep=True)
        return record

    async def get(self, project_id, record_id):
        record = self.records.get(record_id)
        if record is None or record.project_id != project_id:
            return None
        return record.model_copy(deep=True)

    async def list(self, project_id, *, limit=50, offset=0):
        records = [record for record in self.records.values() if record.project_id == project_id]
        records.sort(key=lambda record: (record.created_at, record.id), reverse=True)
        return [record.model_copy(deep=True) for record in records[offset : offset + limit]]


class MemoryStore:
    def __init__(self) -> None:
        self.datasets = MemoryRepository(("project_id", "name", "version"))
        self.models = MemoryRepository(("project_id", "name"))
        self.experiments = MemoryExperiments(("project_id", "submission_key"))
        self.versions = MemoryVersions(("project_id", "model_id", "version"))


class MemoryVersions(MemoryRepository):
    async def for_model(self, project_id, model_id, *, limit, offset):
        records = await self.list(project_id, limit=100, offset=0)
        return [record for record in records if record.model_id == model_id][
            offset : offset + limit
        ]


class MemoryExperiments(MemoryRepository):
    async def by_submission(self, project_id, submission_key):
        return next(
            (
                record.model_copy(deep=True)
                for record in self.records.values()
                if record.project_id == project_id and record.submission_key == submission_key
            ),
            None,
        )

    async def mark_dispatched(self, project_id, experiment_id):
        record = self.records.get(experiment_id)
        if record and record.project_id == project_id and record.status == "queued":
            record.last_dispatch_at = datetime.now(UTC)

    async def claim(self, project_id, experiment_id, token, *, lease_seconds, max_attempts):
        record = self.records.get(experiment_id)
        now = datetime.now(UTC)
        if record is None or record.project_id != project_id:
            return None
        if record.status != "queued" and not (
            record.status == "running" and record.lease_expires_at <= now
        ):
            return None
        if record.attempts >= max_attempts:
            record.status = "failed"
            record.error_summary = "Worker recovery attempt limit was exhausted"
            return None
        record.status = "running"
        record.worker_token = token
        record.attempts += 1
        record.started_at = now
        record.heartbeat_at = now
        record.lease_expires_at = now + timedelta(seconds=lease_seconds)
        return record.model_copy(deep=True)

    async def heartbeat(self, project_id, experiment_id, token, lease_seconds):
        record = self.records.get(experiment_id)
        if (
            not record
            or record.project_id != project_id
            or record.worker_token != token
            or record.status != "running"
        ):
            return False
        record.heartbeat_at = datetime.now(UTC)
        record.lease_expires_at = record.heartbeat_at + timedelta(seconds=lease_seconds)
        return True

    async def finish(self, project_id, experiment_id, token, *, values):
        record = self.records.get(experiment_id)
        if (
            not record
            or record.project_id != project_id
            or record.worker_token != token
            or record.status != "running"
        ):
            return False
        self.records[experiment_id] = type(record).model_validate(
            {
                **record.model_dump(),
                **values,
                "completed_at": datetime.now(UTC),
                "worker_token": None,
                "lease_expires_at": None,
            }
        )
        return True

    async def filtered_list(self, project_id, *, limit, offset, status, model_id):
        records = await self.list(project_id, limit=100, offset=0)
        filtered = [
            record
            for record in records
            if (status is None or record.status == status)
            and (model_id is None or record.model_id == model_id)
        ]
        return filtered[offset : offset + limit]


class FakePublisher:
    def __init__(self):
        self.published = []
        self.error = None

    def publish(self, project_id, experiment_id):
        if self.error:
            raise self.error
        self.published.append((project_id, experiment_id))
