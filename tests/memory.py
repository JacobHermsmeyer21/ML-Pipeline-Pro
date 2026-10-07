"""Deterministic repository substitute for API and worker contract tests."""

from datetime import UTC, datetime, timedelta

from pymongo.errors import DuplicateKeyError

from ml_pipeline_pro.training_control import OwnershipLost


class MemoryRepository:
    def __init__(self, unique_fields=()) -> None:
        self.records = {}
        self.unique_fields = unique_fields
        self.error = None

    def _owns_tuning(self, project_id, job_id, token, *, terminal=False):
        jobs = getattr(self, "tuning_jobs", None)
        job = jobs.records.get(job_id) if jobs is not None else None
        return bool(
            job
            and job.project_id == project_id
            and job.worker_token == token
            and (
                job.status in {"failed", "cancelled"}
                if terminal
                else job.status in {"running", "cancel_requested"}
                and token is not None
                and job.lease_expires_at > datetime.now(UTC)
            )
        )

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
    async def insert(self, record):
        job_id = getattr(record, "tuning_job_id", None)
        if job_id is not None and not self._owns_tuning(
            record.project_id, job_id, record.worker_token
        ):
            raise OwnershipLost()
        return await super().insert(record)

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

    async def claim(
        self, project_id, experiment_id, token, *, lease_seconds, max_attempts, tuning_job_id=None
    ):
        record = self.records.get(experiment_id)
        now = datetime.now(UTC)
        if (
            record is None
            or record.project_id != project_id
            or record.tuning_job_id != tuning_job_id
            or (
                tuning_job_id is not None
                and not self._owns_tuning(project_id, tuning_job_id, token)
            )
        ):
            return None
        if record.status != "queued" and not (
            record.status == "running"
            and (record.lease_expires_at <= now or tuning_job_id is not None)
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
            or (
                record.tuning_job_id is not None
                and not self._owns_tuning(project_id, record.tuning_job_id, token)
            )
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
            or (
                record.tuning_job_id is not None
                and not self._owns_tuning(project_id, record.tuning_job_id, token)
            )
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

    async def finish_tuning_test(self, project_id, experiment_id, job_id, token, *, values):
        record = self.records.get(experiment_id)
        if (
            record is None
            or record.project_id != project_id
            or record.tuning_job_id != job_id
            or record.status != "succeeded"
            or record.test_evaluated
            or not self._owns_tuning(project_id, job_id, token)
        ):
            return False
        self.records[experiment_id] = type(record).model_validate(
            {**record.model_dump(), **values, "test_evaluated": True}
        )
        return True

    async def stop_for_tuning(self, project_id, job_id, status, reason, token=None):
        if not self._owns_tuning(project_id, job_id, token, terminal=token is None):
            return False
        for record in self.records.values():
            if (
                record.project_id == project_id
                and record.tuning_job_id == job_id
                and record.status in {"queued", "running"}
                and (token is None or record.worker_token == token)
            ):
                record.status = status
                record.error_summary = reason
                record.completed_at = datetime.now(UTC)
                record.worker_token = None
                record.lease_expires_at = None
        return True


class FakePublisher:
    def __init__(self):
        self.published = []
        self.error = None
        self.published_tuning = []

    def publish(self, project_id, experiment_id):
        if self.error:
            raise self.error
        self.published.append((project_id, experiment_id))

    def publish_tuning(self, project_id, job_id):
        if self.error:
            raise self.error
        self.published_tuning.append((project_id, job_id))


class MemoryTuningJobs(MemoryExperiments):
    async def refresh_terminal_progress(self, project_id, job_id, values):
        record = self.records.get(job_id)
        if (
            record
            and record.project_id == project_id
            and record.status in {"failed", "cancelled"}
            and record.worker_token is None
        ):
            self.records[job_id] = type(record).model_validate(
                {**record.model_dump(), **values, "reservation": None}
            )

    async def claim(self, project_id, job_id, token, *, lease_seconds, max_attempts):
        record = self.records.get(job_id)
        now = datetime.now(UTC)
        if record is None or record.project_id != project_id:
            return None
        if record.status != "queued" and not (
            record.status in {"running", "cancel_requested"} and record.lease_expires_at <= now
        ):
            return None
        if record.attempts >= max_attempts:
            record.status = "cancelled" if record.status == "cancel_requested" else "failed"
            record.error_summary = "Worker recovery attempt limit was exhausted"
            record.worker_token = None
            return None
        if record.status != "cancel_requested":
            record.status = "running"
        record.worker_token = token
        record.attempts += 1
        record.started_at = record.started_at or now
        record.deadline_at = record.deadline_at or now + timedelta(
            seconds=record.limits.max_runtime_seconds
        )
        record.search_deadline_at = record.search_deadline_at or record.deadline_at - timedelta(
            seconds=min(10, record.limits.max_runtime_seconds / 10)
        )
        record.heartbeat_at = now
        record.lease_expires_at = now + timedelta(seconds=lease_seconds)
        return record.model_copy(deep=True)

    async def heartbeat(self, project_id, job_id, token, lease_seconds):
        record = self.records.get(job_id)
        if (
            record is None
            or record.project_id != project_id
            or record.worker_token != token
            or record.status not in {"running", "cancel_requested"}
        ):
            return False
        record.heartbeat_at = datetime.now(UTC)
        record.lease_expires_at = record.heartbeat_at + timedelta(seconds=lease_seconds)
        return True

    async def reserve(self, project_id, job_id, token, reservation):
        record = self.records.get(job_id)
        if (
            record is None
            or record.project_id != project_id
            or record.worker_token != token
            or record.status != "running"
            or record.phase != "searching"
            or record.reservation is not None
            or record.scheduled_trials != reservation.number
            or record.scheduled_trials >= record.limits.max_trials
            or record.search_deadline_at <= datetime.now(UTC)
        ):
            return False
        record.reservation = reservation.model_copy(deep=True)
        record.scheduled_trials += 1
        return True

    async def progress(self, project_id, job_id, token, *, number, values):
        record = self.records.get(job_id)
        if (
            record is None
            or record.project_id != project_id
            or record.worker_token != token
            or record.status not in {"running", "cancel_requested"}
        ):
            return False
        if number is not None:
            if record.reservation is None or record.reservation.number != number:
                return False
            values = {**values, "reservation": None}
        self.records[job_id] = type(record).model_validate({**record.model_dump(), **values})
        return True

    async def finish(self, project_id, job_id, token, *, values):
        record = self.records.get(job_id)
        if (
            record is None
            or record.project_id != project_id
            or record.worker_token != token
            or record.status not in {"running", "cancel_requested"}
        ):
            return False
        status = "cancelled" if record.status == "cancel_requested" else values["status"]
        self.records[job_id] = type(record).model_validate(
            {
                **record.model_dump(),
                **values,
                "status": status,
                "phase": "complete",
                "worker_token": None,
                "lease_expires_at": None,
                "completed_at": datetime.now(UTC),
            }
        )
        return True

    async def request_cancel(self, project_id, job_id):
        record = self.records.get(job_id)
        if record is None or record.project_id != project_id:
            return None
        if record.status == "queued":
            record.status = "cancelled"
            record.phase = "complete"
            record.completed_at = datetime.now(UTC)
            record.stop_reason = "cancelled"
        elif record.status == "running":
            record.status = "cancel_requested"
            record.stop_reason = "cancelled"
        return record.model_copy(deep=True)


class MemoryTrials(MemoryRepository):
    async def insert(self, record):
        if not self._owns_tuning(record.project_id, record.tuning_job_id, record.worker_token):
            raise OwnershipLost()
        return await super().insert(record)

    async def for_job(self, project_id, job_id, *, limit=50, offset=0):
        records = [
            record.model_copy(deep=True)
            for record in self.records.values()
            if record.project_id == project_id and record.tuning_job_id == job_id
        ]
        records.sort(key=lambda record: record.number)
        return records[offset : offset + limit]

    async def claim(self, project_id, trial_id, token):
        record = self.records.get(trial_id)
        if (
            record is None
            or record.project_id != project_id
            or record.status not in {"queued", "running"}
            or not self._owns_tuning(project_id, record.tuning_job_id, token)
        ):
            return None
        record.status = "running"
        record.worker_token = token
        return await self.get(project_id, trial_id)

    async def finish(self, project_id, trial_id, token, *, values):
        record = self.records.get(trial_id)
        if (
            record is None
            or record.project_id != project_id
            or record.worker_token != token
            or record.status != "running"
            or not self._owns_tuning(project_id, record.tuning_job_id, token)
        ):
            return False
        self.records[trial_id] = type(record).model_validate(
            {
                **record.model_dump(),
                **values,
                "completed_at": datetime.now(UTC),
                "worker_token": None,
            }
        )
        return True

    async def stop_incomplete(self, project_id, job_id, status, reason, token=None):
        if not self._owns_tuning(project_id, job_id, token, terminal=token is None):
            return False
        for record in self.records.values():
            if (
                record.project_id == project_id
                and record.tuning_job_id == job_id
                and record.status in {"queued", "running"}
                and (token is None or record.worker_token == token)
            ):
                record.status = status
                record.error_summary = reason
                record.worker_token = None
                record.completed_at = datetime.now(UTC)
        return True


class MemoryTuningStore:
    def __init__(self):
        self.jobs = MemoryTuningJobs(("project_id", "submission_key"))
        self.trials = MemoryTrials(("project_id", "tuning_job_id", "number"))
        self.trials.tuning_jobs = self.jobs
