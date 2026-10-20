"""Permanent project-scoped aliases; canonical IDs remain the storage identity."""

import argparse
import asyncio
import re

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from ml_pipeline_pro.errors import ApiError

KINDS = {"experiments": "e", "conversations": "c", "datasets": "d"}
MAX_NUMBER = 2**63 - 1


def is_short_id(kind, identity):
    """Reject oversized numeric strings before parsing or querying them."""
    return bool(
        len(identity) <= 20
        and re.fullmatch(KINDS[kind] + r"[1-9][0-9]*", identity)
        and int(identity[1:]) <= MAX_NUMBER
    )


class ShortIds:
    def __init__(self, database):
        self.database = database
        self.aliases = database.get_collection("record_aliases")
        self.counters = database.get_collection("record_alias_counters")

    async def ensure_indexes(self):
        await self.aliases.create_index(
            [("project_id", 1), ("kind", 1), ("short_id", 1)],
            unique=True,
            name="alias_project_kind_short",
        )
        await self.aliases.create_index(
            [("project_id", 1), ("kind", 1), ("record_id", 1)],
            unique=True,
            name="alias_project_kind_record",
        )

    async def prepare(self, project, kind):
        # Initialize outside caller transactions: simultaneous first writes may race.
        await self.ensure_indexes()
        key = f"{project}:{kind}"
        try:
            await self.counters.update_one(
                {"_id": key}, {"$setOnInsert": {"value": 0}}, upsert=True
            )
        except DuplicateKeyError:
            if await self.counters.find_one({"_id": key}) is None:
                raise

    async def assign(self, project, kind, identity, *, session):
        """Called inside the transaction publishing the canonical record."""
        scope = {"project_id": project, "kind": kind}
        existing = await self.aliases.find_one({**scope, "record_id": identity}, session=session)
        if existing:
            return existing["short_id"]
        while True:
            counter = await self.counters.find_one_and_update(
                {"_id": f"{project}:{kind}", "value": {"$lt": MAX_NUMBER}},
                {"$inc": {"value": 1}},
                return_document=ReturnDocument.AFTER,
                session=session,
            )
            if counter is None:
                raise ApiError(503, "short_id_exhausted", "Short ID sequence is unavailable")
            alias = f"{KINDS[kind]}{counter['value']}"
            # Literal pre-existing IDs have priority; do not shadow them.
            collision = await self.database[kind].find_one(
                {"_id": alias, "project_id": project}, session=session
            )
            if collision and alias != identity:
                continue
            await self.aliases.insert_one(
                {**scope, "record_id": identity, "short_id": alias}, session=session
            )
            return alias

    async def resolve(self, project, kind, identity, *, session=None):
        if not is_short_id(kind, identity):
            return identity
        exact = await self.database[kind].find_one(
            {"_id": identity, "project_id": project}, session=session
        )
        if exact:
            return identity
        saved = await self.aliases.find_one(
            {"project_id": project, "kind": kind, "short_id": identity}, session=session
        )
        return saved["record_id"] if saved else identity

    async def label(self, project, kind, identity, *, session=None):
        saved = await self.aliases.find_one(
            {"project_id": project, "kind": kind, "record_id": identity}, session=session
        )
        return saved["short_id"] if saved else None

    async def migrate(self):
        """Resume in bounded batches. All canonical-record writers must be paused."""
        from ml_pipeline_pro.lifecycle import Lifecycle

        await self.ensure_indexes()
        counts = dict.fromkeys(KINDS, 0)
        for kind in KINDS:
            collection = self.database[kind]
            for project in sorted(await collection.distinct("project_id")):
                await self.prepare(project, kind)
                while True:
                    batch = await (
                        collection.find({"project_id": project, "short_id": None})
                        .sort([("created_at", 1), ("_id", 1)])
                        .limit(100)
                        .to_list()
                    )
                    if not batch:
                        break
                    for record in batch:

                        async def write(
                            session,
                            record=record,
                            project=project,
                            kind=kind,
                            collection=collection,
                        ):
                            alias = await self.assign(project, kind, record["_id"], session=session)
                            await collection.update_one(
                                {"_id": record["_id"], "project_id": project},
                                {"$set": {"short_id": alias}},
                                session=session,
                            )

                        await Lifecycle(self.database).transaction(write)
                        counts[kind] += 1
                # Verify every remaining record matches its durable mapping.
                async for record in collection.find({"project_id": project}):
                    if record.get("short_id") != await self.label(project, kind, record["_id"]):
                        raise RuntimeError("Short ID migration coverage mismatch")
        return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--writers-paused", action="store_true", required=True)
    parser.parse_args()

    async def run():
        from ml_pipeline_pro.config import Settings
        from ml_pipeline_pro.connections import open_connections

        settings = Settings()
        async with open_connections(settings) as connections:
            database = connections.mongo.get_database(settings.mongodb_database)
            print(await ShortIds(database).migrate())

    asyncio.run(run())


if __name__ == "__main__":
    main()
