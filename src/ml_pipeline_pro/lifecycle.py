"""Transactional admission and minimal receipts for permanent deletion."""

import hashlib
from contextvars import ContextVar

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from ml_pipeline_pro.errors import ApiError
from ml_pipeline_pro.short_ids import ShortIds

registration_generation = ContextVar("registration_generation", default=None)
GATED_COLLECTIONS = {
    "datasets",
    "models",
    "experiments",
    "tuning_jobs",
    "model_versions",
    "monitoring_observations",
}


def key_digest(key):
    return hashlib.sha256(key.encode()).hexdigest()


def busy(operation_id=None):
    return ApiError(
        409,
        "deletion_in_progress",
        "Project cleanup is incomplete; resume its deletion first",
        {"operation_id": operation_id} if operation_id else None,
    )


class Lifecycle:
    def __init__(self, database):
        self.database = database
        self.gates = database.project_lifecycle

    async def ensure(self, project):
        try:
            await self.gates.update_one(
                {"_id": project},
                {
                    "$setOnInsert": {
                        "project_id": project,
                        "generation": 0,
                        "revision": 0,
                        "operation_id": None,
                    }
                },
                upsert=True,
            )
        except DuplicateKeyError:
            # Simultaneous first mutations can race creation of the same gate.
            if await self.gates.find_one({"_id": project}) is None:
                raise

    async def transaction(self, callback):
        async with self.database.client.start_session() as session:
            return await session.with_transaction(
                callback,
                read_concern=ReadConcern("snapshot"),
                write_concern=WriteConcern("majority"),
            )

    async def generation(self, project):
        await self.ensure(project)
        gate = await self.gates.find_one({"_id": project})
        if gate["operation_id"] is not None:
            raise busy(gate["operation_id"])
        return gate["generation"]

    async def touch(self, project, session, *, generation=None):
        query = {"_id": project, "operation_id": None}
        if generation is not None:
            query["generation"] = generation
        gate = await self.gates.find_one_and_update(
            query,
            {"$inc": {"revision": 1}},
            session=session,
            return_document=ReturnDocument.AFTER,
        )
        if gate is None:
            current = await self.gates.find_one({"_id": project}, session=session)
            raise busy(current.get("operation_id") if current else None)
        return gate

    async def check_submission(self, project, collection, key, request_hash, *, session=None):
        receipt = await self.database.deleted_submissions.find_one(
            {"project_id": project, "collection": collection, "key_digest": key_digest(key)},
            session=session,
        )
        if receipt:
            if receipt["request_hash"] != request_hash:
                raise ApiError(409, "idempotency_conflict", "Submission key has different input")
            raise ApiError(410, "submission_deleted", "This submission was permanently deleted")

    async def insert(self, collection, record, references=()):
        project = record.project_id
        await self.ensure(project)
        aliases = ShortIds(self.database)
        if collection == "experiments":
            await aliases.prepare(project, collection)
        expected = registration_generation.get()
        generation = expected[1] if expected and expected[0] == project else None
        document = record.model_dump()
        document["_id"] = document.pop("id")

        async def commit(session):
            await self.touch(project, session, generation=generation)
            if collection in {"experiments", "tuning_jobs"}:
                await self.check_submission(
                    project, collection, record.submission_key, record.request_hash, session=session
                )
            for name, identity in references:
                found = await self.database[name].find_one(
                    {"_id": identity, "project_id": project}, session=session
                )
                if found is None:
                    kind = {
                        "datasets": "dataset",
                        "models": "model",
                        "experiments": "experiment",
                        "model_versions": "model_version",
                    }[name]
                    raise ApiError(
                        404, f"{kind}_not_found", f"{kind.replace('_', ' ')} was not found"
                    )
            saved = dict(document)
            if collection == "experiments":
                saved["short_id"] = await aliases.assign(
                    project, collection, record.id, session=session
                )
            await self.database[collection].insert_one(saved, session=session)
            if collection == "experiments":
                return record.model_copy(update={"short_id": saved["short_id"]})
            return record

        return await self.transaction(commit)

    async def check_read(self, project, collection, identity):
        item = await self.database.deletion_items.find_one(
            {"project_id": project, "collection": collection, "record_id": identity}
        )
        if item:
            raise busy(item["operation_id"])
