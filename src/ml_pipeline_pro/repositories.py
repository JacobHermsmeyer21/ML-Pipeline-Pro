"""Project-scoped record storage; domain services supply their own record schemas."""

from datetime import UTC, datetime
from typing import Any, Generic, Protocol, TypeVar
from uuid import uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from pymongo.asynchronous.database import AsyncDatabase


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")
    schema_version: int = Field(default=1, ge=1)
    created_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))


RecordT = TypeVar("RecordT", bound=Record)


class Repository(Protocol[RecordT]):
    async def insert(self, record: RecordT) -> RecordT: ...

    async def get(self, project_id: str, record_id: str) -> RecordT | None: ...

    async def list(self, project_id: str, *, limit: int = 50, offset: int = 0) -> list[RecordT]: ...


class MongoRepository(Generic[RecordT]):
    def __init__(
        self, database: AsyncDatabase, collection_name: str, record_type: type[RecordT]
    ) -> None:
        self.database = database
        self.collection = database.get_collection(collection_name)
        self.record_type = record_type

    async def insert(self, record: RecordT) -> RecordT:
        document = record.model_dump()
        document["_id"] = document.pop("id")
        await self.collection.insert_one(document)
        return record

    async def get(self, project_id: str, record_id: str) -> RecordT | None:
        document = await self.collection.find_one({"_id": record_id, "project_id": project_id})
        return self._decode(document) if document is not None else None

    async def list(self, project_id: str, *, limit: int = 50, offset: int = 0) -> list[RecordT]:
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("limit must be between 1 and 100; offset must be nonnegative")
        cursor = (
            self.collection.find({"project_id": project_id})
            .sort([("created_at", -1), ("_id", -1)])
            .skip(offset)
            .limit(limit)
        )
        return [self._decode(document) async for document in cursor]

    def _decode(self, document: dict[str, Any]) -> RecordT:
        values = {key: value for key, value in document.items() if key != "_id"}
        return self.record_type.model_validate({**values, "id": document["_id"]})
