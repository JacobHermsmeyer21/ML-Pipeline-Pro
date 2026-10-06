"""MongoDB storage and indexes owned by the model management module."""

import asyncio

from fastapi import Request
from pymongo import ASCENDING, DESCENDING

from ml_pipeline_pro.repositories import MongoRepository
from ml_pipeline_pro.schemas import DatasetRecord, ModelRecord


class TrackingStore:
    def __init__(self, database) -> None:
        self.datasets = MongoRepository(database, "datasets", DatasetRecord)
        self.models = MongoRepository(database, "models", ModelRecord)
        self._indexed = False
        self._index_lock = asyncio.Lock()

    async def ensure_indexes(self) -> None:
        async with self._index_lock:
            if self._indexed:
                return
            await self.datasets.collection.create_index(
                [("project_id", ASCENDING), ("name", ASCENDING), ("version", ASCENDING)],
                unique=True,
                name="dataset_project_name_version",
            )
            await self.models.collection.create_index(
                [("project_id", ASCENDING), ("name", ASCENDING)],
                unique=True,
                name="model_project_name",
            )
            for repository in (self.datasets, self.models):
                await repository.collection.create_index(
                    [("project_id", ASCENDING), ("created_at", DESCENDING), ("_id", DESCENDING)],
                    name="project_created_id",
                )
            self._indexed = True


async def get_store(request: Request) -> TrackingStore:
    if not hasattr(request.app.state, "tracking_store"):
        database = request.app.state.connections.mongo.get_database(
            request.app.state.settings.mongodb_database
        )
        request.app.state.tracking_store = TrackingStore(database)
    store = request.app.state.tracking_store
    await store.ensure_indexes()
    return store
