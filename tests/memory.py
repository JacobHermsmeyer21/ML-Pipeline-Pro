"""Deterministic repository substitute for API and worker contract tests."""

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
