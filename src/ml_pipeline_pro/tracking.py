"""MongoDB storage and indexes owned by the model management module."""

import asyncio

from fastapi import Request
from pymongo import ASCENDING, DESCENDING

from ml_pipeline_pro.jobs import ExperimentRepository
from ml_pipeline_pro.lifecycle import Lifecycle
from ml_pipeline_pro.repositories import MongoRepository
from ml_pipeline_pro.schemas import DatasetRecord, ExperimentRecord, ModelRecord, ModelVersionRecord


class TrackingStore:
    def __init__(self, database) -> None:
        self.lifecycle = Lifecycle(database)
        self.datasets = DatasetRepository(database, "datasets", DatasetRecord)
        self.models = MongoRepository(database, "models", ModelRecord)
        self.experiments = ExperimentRepository(database, "experiments", ExperimentRecord)
        self.versions = ModelVersionRepository(database, "model_versions", ModelVersionRecord)
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
            await self.experiments.collection.create_index(
                [("project_id", ASCENDING), ("submission_key", ASCENDING)],
                unique=True,
                name="experiment_submission",
            )
            await self.versions.collection.create_index(
                [("project_id", ASCENDING), ("model_id", ASCENDING), ("version", ASCENDING)],
                unique=True,
                name="model_version_identity",
            )
            for key in ("status", "model_id"):
                await self.experiments.collection.create_index(
                    [("project_id", ASCENDING), (key, ASCENDING), ("created_at", DESCENDING)],
                    name=f"experiment_project_{key}_created",
                )
            await self.experiments.collection.create_index(
                [
                    ("status", ASCENDING),
                    ("last_dispatch_at", ASCENDING),
                    ("lease_expires_at", ASCENDING),
                ],
                name="experiment_recovery",
            )
            for repository in (self.datasets, self.models, self.experiments, self.versions):
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


class ModelVersionRepository(MongoRepository[ModelVersionRecord]):
    async def for_model(self, project_id: str, model_id: str, *, limit: int, offset: int):
        cursor = (
            self.collection.find({"project_id": project_id, "model_id": model_id})
            .sort([("created_at", -1), ("_id", -1)])
            .skip(offset)
            .limit(limit)
        )
        return [self._decode(document) async for document in cursor]


class DatasetRepository(MongoRepository[DatasetRecord]):
    async def by_identity(self, project_id: str, name: str, version: str):
        document = await self.collection.find_one(
            {"project_id": project_id, "name": name, "version": version}
        )
        return self._decode(document) if document is not None else None
