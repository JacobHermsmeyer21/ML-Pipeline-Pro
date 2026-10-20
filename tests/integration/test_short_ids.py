"""Real transaction, migration and ownership evidence for permanent short IDs."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import OperationFailure

from ml_pipeline_pro.connections import open_connections
from ml_pipeline_pro.conversation_schemas import ActionDecision, ChatRequest, fingerprint
from ml_pipeline_pro.conversation_store import ConversationStore
from ml_pipeline_pro.errors import ApiError
from ml_pipeline_pro.schemas import ExperimentRecord
from ml_pipeline_pro.short_ids import MAX_NUMBER, ShortIds
from ml_pipeline_pro.tool_schemas import ToolContext
from ml_pipeline_pro.tracking import TrackingStore
from ml_pipeline_pro.training_control import OwnershipLost
from ml_pipeline_pro.tuning_schemas import TuningRecord
from ml_pipeline_pro.tuning_store import TuningStore
from tests.integration.helpers import integration_settings
from tests.integration.test_conversation_store import completed, proposal

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("MLPP_RUN_INTEGRATION") != "1", reason="Requires real MongoDB"),
]


def exercise(callback):
    async def run():
        settings = integration_settings(mongodb_database=f"mlpp_short_ids_{uuid4().hex}")
        async with open_connections(settings) as connections:
            database = connections.mongo.get_database(settings.mongodb_database)
            store = TrackingStore(database)
            await store.ensure_indexes()
            try:
                await callback(database, store, settings)
            finally:
                await connections.mongo.drop_database(settings.mongodb_database)

    asyncio.run(run())


def experiment(project="demo", **changes):
    return ExperimentRecord(
        project_id=project,
        dataset_id="dataset",
        model_id="model",
        submission_key=uuid4().hex,
        request_hash="0" * 64,
        **changes,
    )


def test_concurrent_allocations_scoping_restart_deletion_and_counter_exhaustion():
    async def run(database, store, settings):
        records = await asyncio.gather(*[store.experiments.insert(experiment()) for _ in range(12)])
        assert {r.short_id for r in records} == {f"e{i}" for i in range(1, 13)}
        aliases = ShortIds(database)
        restarted = TrackingStore(database)
        for record in records:
            assert (await restarted.experiments.get("demo", record.short_id)).id == record.id
            assert (await restarted.experiments.get("demo", record.id)).short_id == record.short_id
            assert await restarted.experiments.get("foreign", record.short_id) is None
        foreign = await store.experiments.insert(experiment("foreign"))
        assert foreign.short_id == "e1"
        removed = next(r for r in records if r.short_id == "e1")
        await database.experiments.delete_one({"_id": removed.id})
        replacement = await store.experiments.insert(experiment())
        assert replacement.short_id == "e13"
        assert await store.experiments.get("demo", "e1") is None
        assert await aliases.resolve("demo", "experiments", "e1") == removed.id
        await aliases.counters.update_one(
            {"_id": "demo:experiments"}, {"$set": {"value": MAX_NUMBER - 1}}
        )
        last = await store.experiments.insert(experiment())
        assert last.short_id == f"e{MAX_NUMBER}"
        rejected = experiment()
        with pytest.raises(ApiError) as caught:
            await store.experiments.insert(rejected)
        assert caught.value.code == "short_id_exhausted"
        assert await database.experiments.find_one({"_id": rejected.id}) is None
        assert await aliases.label("demo", "experiments", rejected.id) is None

    exercise(run)


def test_allocation_rolls_back_and_retries_with_record_publication(monkeypatch):
    async def run(database, store, settings):
        record = experiment()
        original = AsyncCollection.insert_one
        failures = []

        async def insert(collection, document, *args, **kwargs):
            if collection.name == "experiments" and document["_id"] == record.id and not failures:
                failures.append(True)
                raise OperationFailure(
                    "controlled transaction conflict",
                    112,
                    {"errorLabels": ["TransientTransactionError"]},
                )
            return await original(collection, document, *args, **kwargs)

        monkeypatch.setattr(AsyncCollection, "insert_one", insert)
        saved = await store.experiments.insert(record)
        assert failures == [True] and saved.short_id == "e1"
        assert await database.record_aliases.count_documents({}) == 1
        assert (await database.record_alias_counters.find_one({"_id": "demo:experiments"}))[
            "value"
        ] == 1

    exercise(run)


def test_resumable_migration_preserves_history_and_literal_id_collisions(monkeypatch):
    async def run(database, store, settings):
        now = datetime.now(UTC)
        for index, identity in enumerate(["old-first", "e1", "old-last"]):
            record = experiment(id=identity, created_at=now + timedelta(seconds=index))
            document = record.model_dump(exclude={"short_id"})
            document["_id"] = document.pop("id")
            await database.experiments.insert_one(document)
        await database.conversations.insert_one(
            {"_id": "old-conversation", "project_id": "demo", "created_at": now}
        )
        historical = {
            "_id": "historical-turn",
            "public": {"conversation_id": "old-conversation", "message": "old-first"},
        }
        await database.conversation_turns.insert_one(historical)
        aliases = ShortIds(database)
        assign = aliases.assign
        calls = []

        async def interrupted(project, kind, identity, *, session):
            calls.append(identity)
            if len(calls) == 2:
                raise RuntimeError("controlled migration interruption")
            return await assign(project, kind, identity, session=session)

        monkeypatch.setattr(aliases, "assign", interrupted)
        with pytest.raises(RuntimeError, match="controlled migration interruption"):
            await aliases.migrate()
        first = await database.experiments.find_one({"_id": "old-first"})
        assert first["short_id"] == "e2"  # e1 is a literal historical identity.
        resumed = ShortIds(database)
        assert await resumed.migrate() == {"experiments": 2, "conversations": 1, "datasets": 0}
        assert await resumed.migrate() == {"experiments": 0, "conversations": 0, "datasets": 0}
        assert (await database.experiments.find_one({"_id": "old-first"}))["short_id"] == "e2"
        assert await resumed.resolve("demo", "experiments", "e1") == "e1"
        assert await resumed.resolve("demo", "experiments", "e2") == "old-first"
        assert await resumed.label("demo", "conversations", "old-conversation") == "c1"
        assert await database.conversation_turns.find_one({"_id": "historical-turn"}) == historical
        created = await store.experiments.insert(experiment())
        assert created.short_id == "e5"

    exercise(run)


def test_conversation_alias_continuation_history_exact_replay_and_action_decisions():
    async def run(database, store, settings):
        conversations = ConversationStore(database, settings)
        context = ToolContext(project_id="demo")
        first = ChatRequest(request_id="first", message="inspect", expected_revision=0)
        claim = await conversations.reserve(
            context, first, deadline=datetime.now(UTC) + timedelta(seconds=30)
        )
        assert claim.turn.short_id == "c1" and claim.turn.conversation_id != "c1"
        finished = await conversations.finish(context, claim, completed(claim))
        assert (await conversations.history("demo", "c1")).turns == [finished]
        next_body = ChatRequest(
            request_id="second",
            message="propose training",
            expected_revision=1,
            conversation_id="c1",
        )
        second = await conversations.reserve(
            context, next_body, deadline=datetime.now(UTC) + timedelta(seconds=30)
        )
        assert second.turn.conversation_id == claim.turn.conversation_id
        result = await conversations.finish(
            context, second, completed(second, status="awaiting_confirmation"), proposal=proposal()
        )
        restarted = ConversationStore(database, settings)
        replay = await restarted.reserve(
            context, next_body, deadline=datetime.now(UTC) + timedelta(seconds=30)
        )
        assert replay.replayed and replay.turn == result
        raw = await database.conversation_turns.find_one({"_id": second.turn.turn_id})
        assert raw["request_hash"] == fingerprint(next_body.model_dump())
        with pytest.raises(ApiError) as conflict:
            await restarted.reserve(
                context,
                next_body.model_copy(update={"conversation_id": claim.turn.conversation_id}),
                deadline=datetime.now(UTC) + timedelta(seconds=30),
            )
        assert conflict.value.code == "chat_idempotency_conflict"
        action = await restarted.action("demo", "c1", result.pending_action.action_id)
        rejected = await restarted.decide(
            context,
            "c1",
            action.action_id,
            ActionDecision(decision="reject", arguments_hash=action.arguments_hash),
            deadline=datetime.now(UTC) + timedelta(seconds=10),
        )
        assert rejected.action.status == "rejected"
        assert rejected.action.arguments_hash == action.arguments_hash
        with pytest.raises(ApiError) as foreign:
            await restarted.history("foreign", "c1")
        assert foreign.value.code == "conversation_not_found"
        assert await database.record_aliases.count_documents({"kind": "conversations"}) == 1

    exercise(run)


def test_migrated_conversation_projects_alias_without_rewriting_saved_turn_or_hash():
    async def run(database, store, settings):
        conversations = ConversationStore(database, settings)
        context = ToolContext(project_id="demo")
        body = ChatRequest(request_id="legacy", message="inspect", expected_revision=0)
        claim = await conversations.reserve(
            context, body, deadline=datetime.now(UTC) + timedelta(seconds=30)
        )
        await conversations.finish(context, claim, completed(claim))
        # Reproduce pre-upgrade documents: no alias metadata or registry.
        await database.conversations.update_one(
            {"_id": claim.turn.conversation_id}, {"$unset": {"short_id": ""}}
        )
        await database.conversation_turns.update_one(
            {"_id": claim.turn.turn_id}, {"$unset": {"public.short_id": ""}}
        )
        await database.record_aliases.delete_many({})
        await database.record_alias_counters.delete_many({})
        before = await database.conversation_turns.find_one({"_id": claim.turn.turn_id})
        assert await ShortIds(database).migrate() == {
            "experiments": 0,
            "conversations": 1,
            "datasets": 0,
        }
        restarted = ConversationStore(database, settings)
        replay = await restarted.reserve(
            context, body, deadline=datetime.now(UTC) + timedelta(seconds=30)
        )
        assert replay.replayed and replay.turn.short_id == "c1"
        assert replay.turn.conversation_id == claim.turn.conversation_id
        assert (await restarted.history("demo", "c1")).turns == [replay.turn]
        after = await database.conversation_turns.find_one({"_id": claim.turn.turn_id})
        assert before == after and after["request_hash"] == fingerprint(body.model_dump())

    exercise(run)


def test_tuning_children_allocate_only_with_live_parent_owner():
    async def run(database, store, settings):
        tuning = TuningStore(database)
        await tuning.ensure_indexes()
        job = await tuning.jobs.insert(
            TuningRecord(
                project_id="demo",
                dataset_id="dataset",
                model_id="model",
                submission_key="job",
                request_hash="0" * 64,
            )
        )
        await tuning.jobs.claim("demo", job.id, "owner", lease_seconds=30, max_attempts=3)
        child = await store.experiments.insert(
            experiment(tuning_job_id=job.id, worker_token="owner")
        )
        assert child.short_id == "e1"
        await database.tuning_jobs.update_one({"_id": job.id}, {"$set": {"worker_token": "next"}})
        stale = experiment(tuning_job_id=job.id, worker_token="owner")
        with pytest.raises(OwnershipLost):
            await store.experiments.insert(stale)
        assert await ShortIds(database).label("demo", "experiments", stale.id) is None
        assert await database.record_aliases.count_documents({}) == 1

    exercise(run)
