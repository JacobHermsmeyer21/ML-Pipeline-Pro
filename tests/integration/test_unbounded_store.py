"""Real transactions for marked no-expiry turns and unchanged finite ownership."""

import asyncio
import os
from datetime import UTC, datetime, timedelta

import pytest
from pymongo.asynchronous.collection import AsyncCollection

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.conversation_store import ConversationStore, TurnClaim
from ml_pipeline_pro.errors import ApiError
from tests.integration.test_conversation_store import CONTEXT, completed, exercise, request, reserve
from tests.integration.test_conversation_store import proposal as saved_proposal

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("MLPP_RUN_INTEGRATION") != "1", reason="Requires real MongoDB"),
]


def unbounded_store(database, settings, clock):
    config = Settings(
        _env_file=None,
        **(
            settings.model_dump()
            | {
                "chat_backend": "ollama",
                "chat_unbounded_diagnostic": True,
                "chat_timeout_seconds": None,
                "chat_model_timeout_seconds": None,
            }
        ),
    )
    return ConversationStore(database, config, clock=clock)


def test_unbounded_turn_survives_elapsed_time_reader_restart_and_exact_replay():
    async def run(store, database, settings, clock):
        diagnostic = unbounded_store(database, settings, clock)
        body = request()
        claim = await diagnostic.reserve(CONTEXT, body, deadline=None)
        assert claim.timeout_mode == "diagnostic_unbounded" and claim.deadline is None
        for collection, identity in [
            (database.conversations, claim.turn.conversation_id),
            (database.conversation_turns, claim.turn.turn_id),
        ]:
            saved = await collection.find_one({"_id": identity})
            assert saved["timeout_mode"] == "diagnostic_unbounded" and saved["deadline"] is None
        clock.now += timedelta(days=1)
        history = await store.history("demo", claim.turn.conversation_id)
        assert history.turns[0].status == "running"
        replay = await diagnostic.reserve(CONTEXT, body, deadline=None)
        assert replay.replayed and replay.owner_token is None
        assert replay.timeout_mode == claim.timeout_mode and replay.deadline is None
        with pytest.raises(ApiError):
            await store.finish(CONTEXT, replay, completed(claim))
        with pytest.raises(ApiError):
            await diagnostic.reserve(
                CONTEXT,
                request("second", conversation_id=claim.turn.conversation_id, revision=1),
                deadline=None,
            )
        await store.finish(CONTEXT, claim, completed(claim))
        replay = await reserve(store, body)
        assert replay.turn.status == "completed" and replay.deadline is None
        assert replay.timeout_mode == "diagnostic_unbounded"

    exercise(run)


def test_diagnostic_reader_preserves_old_finite_expiry_and_legacy_markers():
    async def run(store, database, settings, clock):
        claim = await reserve(store)
        for collection, identity in [
            (database.conversations, claim.turn.conversation_id),
            (database.conversation_turns, claim.turn.turn_id),
        ]:
            await collection.update_one({"_id": identity}, {"$unset": {"timeout_mode": ""}})
        diagnostic = unbounded_store(database, settings, clock)
        clock.now = claim.deadline
        replay = await diagnostic.reserve(CONTEXT, request(), deadline=None)
        assert replay.replayed and replay.turn.status == "interrupted"
        assert replay.deadline == claim.deadline and replay.timeout_mode == "bounded"
        with pytest.raises(ApiError):
            await diagnostic.finish(CONTEXT, claim, completed(claim))

    exercise(run)


def test_legacy_unmarked_finite_turn_still_completes_without_extending_deadline():
    async def run(store, database, settings, clock):
        claim = await reserve(store)
        for collection, identity in [
            (database.conversations, claim.turn.conversation_id),
            (database.conversation_turns, claim.turn.turn_id),
        ]:
            await collection.update_one({"_id": identity}, {"$unset": {"timeout_mode": ""}})
        result = await store.finish(CONTEXT, claim, completed(claim))
        assert result.status == "completed"
        replay = await reserve(store)
        assert replay.deadline == claim.deadline and replay.timeout_mode == "bounded"

    exercise(run)


@pytest.mark.parametrize(
    "collection,change",
    [
        ("conversations", {"$unset": {"timeout_mode": ""}}),
        ("conversation_turns", {"$unset": {"timeout_mode": ""}}),
        ("conversations", {"$set": {"timeout_mode": "bounded"}}),
        ("conversation_turns", {"$set": {"deadline": datetime(2026, 11, 1, tzinfo=UTC)}}),
    ],
)
def test_malformed_or_mismatched_unbounded_records_fail_closed(collection, change):
    async def run(store, database, settings, clock):
        diagnostic = unbounded_store(database, settings, clock)
        claim = await diagnostic.reserve(CONTEXT, request(), deadline=None)
        target = database.get_collection(collection)
        identity = (
            claim.turn.conversation_id if collection == "conversations" else claim.turn.turn_id
        )
        await target.update_one({"_id": identity}, change)
        with pytest.raises(ApiError) as caught:
            await diagnostic.history("demo", claim.turn.conversation_id)
        assert caught.value.code == "conversation_conflict"
        with pytest.raises(ApiError):
            await diagnostic.finish(CONTEXT, claim, completed(claim))
        saved = await database.conversation_turns.find_one({"_id": claim.turn.turn_id})
        assert saved["public"]["status"] == "running" and saved["owner_token"] == claim.owner_token
        assert await database.conversation_actions.count_documents({}) == 0

    exercise(run)


def test_unbounded_completion_rejects_lost_owner_and_finite_deadline_mismatch():
    async def run(store, database, settings, clock):
        diagnostic = unbounded_store(database, settings, clock)
        claim = await diagnostic.reserve(CONTEXT, request(), deadline=None)
        wrong = TurnClaim(claim.turn, "wrong-owner", None, False, "diagnostic_unbounded")
        with pytest.raises(ApiError):
            await diagnostic.finish(CONTEXT, wrong, completed(claim))
        assert (await database.conversations.find_one({"_id": claim.turn.conversation_id}))[
            "owner_token"
        ] == claim.owner_token
        finite = await reserve(store, request("finite"))
        await database.conversation_turns.update_one(
            {"_id": finite.turn.turn_id},
            {"$set": {"deadline": finite.deadline + timedelta(seconds=1)}},
        )
        with pytest.raises(ApiError):
            await store.finish(CONTEXT, finite, completed(finite))

    exercise(run)


@pytest.mark.parametrize("with_proposal", [False, True])
def test_unbounded_parent_write_fences_owner_loss_after_valid_snapshot(monkeypatch, with_proposal):
    async def run(store, database, settings, clock):
        diagnostic = unbounded_store(database, settings, clock)
        claim = await diagnostic.reserve(CONTEXT, request(), deadline=None)
        original = AsyncCollection.update_one
        paused, resume = asyncio.Event(), asyncio.Event()
        intercepted = False

        async def pause(collection, query, *args, **kwargs):
            nonlocal intercepted
            if (
                not intercepted
                and collection.full_name == diagnostic.conversations.full_name
                and query.get("owner_token") == claim.owner_token
            ):
                intercepted = True
                paused.set()
                await asyncio.wait_for(resume.wait(), 5)
            return await original(collection, query, *args, **kwargs)

        monkeypatch.setattr(AsyncCollection, "update_one", pause)
        result = completed(claim, status="awaiting_confirmation" if with_proposal else "completed")
        task = asyncio.create_task(
            diagnostic.finish(
                CONTEXT, claim, result, proposal=saved_proposal() if with_proposal else None
            )
        )
        try:
            await asyncio.wait_for(paused.wait(), 5)
            for collection, identity in [
                (database.conversations, claim.turn.conversation_id),
                (database.conversation_turns, claim.turn.turn_id),
            ]:
                await collection.update_one(
                    {"_id": identity}, {"$set": {"owner_token": "replacement"}}
                )
            resume.set()
            with pytest.raises(ApiError) as caught:
                await task
            assert caught.value.code == "conversation_conflict" and intercepted
            parent = await database.conversations.find_one({"_id": claim.turn.conversation_id})
            turn = await database.conversation_turns.find_one({"_id": claim.turn.turn_id})
            assert parent["owner_token"] == turn["owner_token"] == "replacement"
            assert turn["public"]["status"] == "running"
            assert await database.conversation_actions.count_documents({}) == 0
        finally:
            resume.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    exercise(run)
