"""Real MongoDB transactions, replay and turn-owner takeovers."""

import asyncio
import os
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import DuplicateKeyError, OperationFailure

from ml_pipeline_pro.connections import open_connections
from ml_pipeline_pro.conversation_schemas import ChatRequest, fingerprint
from ml_pipeline_pro.conversation_store import ConversationStore, TurnClaim
from ml_pipeline_pro.errors import ApiError
from ml_pipeline_pro.tool_schemas import ToolCall, ToolContext
from tests.integration.helpers import integration_settings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("MLPP_RUN_INTEGRATION") != "1", reason="Requires real MongoDB"),
]


class Clock:
    def __init__(self):
        self.now = datetime(2026, 10, 8, 20, tzinfo=UTC)

    def __call__(self):
        return self.now


CONTEXT = ToolContext(
    project_id="demo", api_key="fixture-project-secret", correlation_id="original"
)


def request(request_id="first", *, conversation_id=None, revision=0, message="Inspect models"):
    return ChatRequest(
        request_id=request_id,
        conversation_id=conversation_id,
        expected_revision=revision,
        message=message,
    )


async def reserve(store, body=None, *, context=CONTEXT):
    return await store.reserve(
        context, body or request(), deadline=store._now() + timedelta(seconds=60)
    )


def completed(claim, **changes):
    return claim.turn.model_copy(
        update={"status": "completed", "message": "Recorded answer", **changes}
    )


def proposal():
    return ToolCall(
        name="create_experiment",
        arguments={
            "dataset_id": "dataset",
            "model_id": "model",
            "config": {"max_runtime_seconds": 10},
        },
    )


def exercise(callback):
    async def run():
        settings = integration_settings(mongodb_database=f"mlpp_conversation_{uuid4().hex}")
        clock = Clock()
        async with open_connections(settings) as connections:
            database = connections.mongo.get_database(settings.mongodb_database)
            store = ConversationStore(database, settings, clock=clock)
            await store.ensure_indexes()
            try:
                await callback(store, database, settings, clock)
            finally:
                await connections.mongo.drop_database(settings.mongodb_database)

    asyncio.run(run())


def test_reservation_replay_scoping_redaction_indexes_and_restart():
    async def run(store, database, settings, clock):
        body = request(message="Inspect fixture-project-secret")
        claim = await reserve(store, body)
        assert claim.turn.user_message == "Inspect [REDACTED]"
        assert claim.turn.revision == 1 and claim.owner_token and not claim.replayed
        other_context = ToolContext(project_id="demo", correlation_id="replay")
        replay = await reserve(store, body, context=other_context)
        assert replay.replayed and replay.owner_token is None
        assert replay.turn == claim.turn
        with pytest.raises(ApiError) as caught:
            await reserve(store, request(message="different"))
        assert caught.value.code == "chat_idempotency_conflict"
        assert await database.conversations.count_documents({}) == 1
        with pytest.raises(ApiError) as caught:
            await store.history("foreign", claim.turn.conversation_id)
        assert caught.value.code == "conversation_not_found"
        foreign = await reserve(store, body, context=ToolContext(project_id="foreign"))
        assert foreign.turn.conversation_id != claim.turn.conversation_id
        await store.finish(CONTEXT, claim, completed(claim, message="fixture-project-secret"))
        restarted = ConversationStore(database, settings, clock=clock)
        replay = await reserve(restarted, body, context=other_context)
        assert replay.turn.status == "completed"
        assert replay.turn.message == "[REDACTED]"
        assert replay.turn.correlation_id == "original"
        raw = await database.conversation_turns.find_one({"_id": claim.turn.turn_id})
        assert "fixture-project-secret" not in str(raw)
        indexes = await database.conversation_turns.index_information()
        assert indexes["chat_request"]["unique"] and indexes["conversation_sequence"]["unique"]
        with pytest.raises(DuplicateKeyError):
            await database.conversation_turns.insert_one({**raw, "_id": "duplicate"})

    exercise(run)


def test_active_turn_and_wrong_revision_conflict_and_history_is_ascending():
    async def run(store, database, settings, clock):
        first = await reserve(store)
        body = request("next", conversation_id=first.turn.conversation_id, revision=1)
        with pytest.raises(ApiError) as caught:
            await reserve(store, body)
        assert caught.value.code == "conversation_conflict"
        await store.finish(CONTEXT, first, completed(first))
        with pytest.raises(ApiError):
            await reserve(store, body.model_copy(update={"expected_revision": 0}))
        second = await reserve(store, body)
        history = await store.history("demo", first.turn.conversation_id)
        assert [turn.revision for turn in history.turns] == [1, 2]
        assert history.revision == 2
        page = await store.history("demo", first.turn.conversation_id, limit=1, offset=1)
        assert page.turns == [second.turn]
        assert await database.conversation_turns.count_documents({}) == 2

    exercise(run)


@pytest.mark.parametrize("read", ["history", "replay", "new_request"])
def test_expired_turn_is_interrupted_and_stale_completion_cannot_publish(read):
    async def run(store, database, settings, clock):
        claim = await reserve(store)
        clock.now += timedelta(seconds=60)  # Exact deadline is no longer owned.
        if read == "history":
            turn = (await store.history("demo", claim.turn.conversation_id)).turns[0]
        elif read == "replay":
            turn = (await reserve(store)).turn
        else:
            await reserve(
                store, request("new", conversation_id=claim.turn.conversation_id, revision=1)
            )
            turn = (await store.history("demo", claim.turn.conversation_id)).turns[0]
        assert turn.status == "interrupted"
        assert turn.error["code"] == "chat_interrupted"
        with pytest.raises(ApiError) as caught:
            await store.finish(CONTEXT, claim, completed(claim))
        assert caught.value.code == "conversation_conflict"
        saved = await database.conversation_turns.find_one({"_id": claim.turn.turn_id})
        assert saved["public"]["status"] == "interrupted"
        assert saved["public"]["message"] == ""

    exercise(run)


def test_saved_proposal_has_expanded_immutable_arguments_and_private_key():
    async def run(store, database, settings, clock):
        claim = await reserve(store)
        result = await store.finish(
            CONTEXT, claim, completed(claim, status="awaiting_confirmation"), proposal=proposal()
        )
        action = result.pending_action
        assert action.tool.arguments["config"]["epochs"] == 30
        assert action.arguments_hash == fingerprint(action.tool.model_dump())
        saved = await database.conversation_actions.find_one({"_id": action.action_id})
        assert saved["submission_key"]
        assert "submission_key" not in action.model_dump()
        assert "owner_token" not in result.model_dump()
        assert await store.action("demo", claim.turn.conversation_id, action.action_id) == action
        with pytest.raises(ApiError):
            await store.action("foreign", claim.turn.conversation_id, action.action_id)
        another = await reserve(store, request("other-conversation"))
        with pytest.raises(ApiError) as caught:
            await store.action("demo", another.turn.conversation_id, action.action_id)
        assert caught.value.code == "action_not_found"
        replay = await reserve(ConversationStore(database, settings, clock=clock))
        assert replay.turn.pending_action == action
        assert replay.owner_token is None
        with pytest.raises(ApiError):
            await store.finish(
                CONTEXT,
                claim,
                completed(claim, status="awaiting_confirmation"),
                proposal=proposal(),
            )
        assert await database.conversation_actions.count_documents({}) == 1
        assert (await database.conversation_actions.find_one({"_id": action.action_id}))[
            "submission_key"
        ] == saved["submission_key"]

    exercise(run)


def test_proposal_timestamp_and_claim_deadline_replay_exactly_at_millisecond_precision():
    async def run(store, database, settings, clock):
        clock.now = clock.now.replace(microsecond=123456)
        claim = await reserve(store)
        replay = await reserve(store)
        assert claim.deadline == replay.deadline
        first = await store.finish(
            CONTEXT, claim, completed(claim, status="awaiting_confirmation"), proposal=proposal()
        )
        replay = await reserve(store)
        assert first == replay.turn

    exercise(run)


@pytest.mark.parametrize("transition", ["superseded", "expired"])
def test_pending_action_lifecycle_and_history_hydrates_current_state(transition):
    async def run(store, database, settings, clock):
        claim = await reserve(store)
        action = (
            await store.finish(
                CONTEXT,
                claim,
                completed(claim, status="awaiting_confirmation"),
                proposal=proposal(),
            )
        ).pending_action
        if transition == "superseded":
            await reserve(
                store, request("next", conversation_id=claim.turn.conversation_id, revision=1)
            )
        else:
            clock.now += timedelta(minutes=15)
        current = await store.action("demo", claim.turn.conversation_id, action.action_id)
        assert current.status == transition
        assert current.arguments_hash == action.arguments_hash
        history = await store.history("demo", claim.turn.conversation_id)
        assert history.turns[0].pending_action.status == transition
        assert history.turns[0].status == "awaiting_confirmation"

    exercise(run)


def test_replayed_claim_wrong_context_and_changed_identity_cannot_complete():
    async def run(store, database, settings, clock):
        claim = await reserve(store)
        replay = await reserve(store)
        for context, candidate, result in [
            (CONTEXT, replay, completed(claim)),
            (ToolContext(project_id="foreign"), claim, completed(claim)),
            (CONTEXT, claim, completed(claim, request_id="tampered")),
            (CONTEXT, claim, completed(claim, correlation_id="tampered")),
            (CONTEXT, claim, completed(claim, user_message="tampered")),
            (
                CONTEXT,
                TurnClaim(claim.turn, "wrong-token", claim.deadline, False),
                completed(claim),
            ),
        ]:
            with pytest.raises(ApiError) as caught:
                await store.finish(context, candidate, result)
            assert caught.value.code == "conversation_conflict"
        parent = await database.conversations.find_one({"_id": claim.turn.conversation_id})
        assert parent["owner_token"] == claim.owner_token
        assert (await store.history("demo", claim.turn.conversation_id)).turns[
            0
        ].status == "running"

    exercise(run)


def test_oversize_and_invalid_proposals_leave_reservation_unchanged():
    async def run(store, database, settings, clock):
        claim = await reserve(store)
        with pytest.raises(ApiError) as caught:
            await store.finish(CONTEXT, claim, completed(claim, message="é" * 140000))
        assert caught.value.code == "chat_limit_exceeded"
        with pytest.raises(ValueError):
            await store.finish(
                CONTEXT,
                claim,
                completed(claim, status="awaiting_confirmation"),
                proposal=ToolCall(name="list_models"),
            )
        assert await database.conversation_actions.count_documents({}) == 0
        assert (await database.conversations.find_one({"_id": claim.turn.conversation_id}))[
            "owner_token"
        ] == claim.owner_token
        await store.finish(CONTEXT, claim, completed(claim))

    exercise(run)


def test_simultaneous_first_request_has_one_identity_and_no_orphan_conversation(monkeypatch):
    async def run(store, database, settings, clock):
        other = ConversationStore(database, settings, clock=clock)
        original = AsyncCollection.find_one
        both_read = asyncio.Event()
        snapshots = 0

        async def barrier(collection, query, *args, **kwargs):
            nonlocal snapshots
            saved = await original(collection, query, *args, **kwargs)
            if (
                collection.full_name == store.turns.full_name
                and query.get("request_id") == "first"
                and saved is None
            ):
                snapshots += 1
                if snapshots == 2:
                    both_read.set()
                await asyncio.wait_for(both_read.wait(), 5)
            return saved

        monkeypatch.setattr(AsyncCollection, "find_one", barrier)
        results = await asyncio.gather(reserve(store), reserve(other))
        assert snapshots >= 2
        assert sum(not result.replayed for result in results) == 1
        assert results[0].turn == results[1].turn
        assert await database.conversations.count_documents({}) == 1
        assert await database.conversation_turns.count_documents({}) == 1

    exercise(run)


def test_competing_new_turns_have_one_owner_across_store_instances(monkeypatch):
    async def run(store, database, settings, clock):
        first = await reserve(store)
        await store.finish(CONTEXT, first, completed(first))
        other = ConversationStore(database, settings, clock=clock)
        original = AsyncCollection.find_one
        both_read = asyncio.Event()
        snapshots = 0

        async def barrier(collection, query, *args, **kwargs):
            nonlocal snapshots
            saved = await original(collection, query, *args, **kwargs)
            if (
                collection.full_name == store.conversations.full_name
                and saved
                and saved["revision"] == 1
                and saved["owner_token"] is None
            ):
                snapshots += 1
                if snapshots == 2:
                    both_read.set()
                await asyncio.wait_for(both_read.wait(), 5)
            return saved

        monkeypatch.setattr(AsyncCollection, "find_one", barrier)
        results = await asyncio.gather(
            *[
                reserve(
                    instance, request(name, conversation_id=first.turn.conversation_id, revision=1)
                )
                for instance, name in [(store, "left"), (other, "right")]
            ],
            return_exceptions=True,
        )
        assert sum(isinstance(result, TurnClaim) for result in results) == 1
        assert snapshots >= 2
        failure = next(result for result in results if isinstance(result, Exception))
        assert isinstance(failure, ApiError) and failure.code == "conversation_conflict"
        assert await database.conversation_turns.count_documents({}) == 2

    exercise(run)


@pytest.mark.parametrize("with_proposal", [False, True])
def test_takeover_after_snapshot_rejects_stale_answer_and_proposal(with_proposal, monkeypatch):
    async def run(store, database, settings, clock):
        claim = await reserve(store)
        paused, resume = asyncio.Event(), asyncio.Event()
        original = AsyncCollection.update_one
        intercepted = False

        async def pause(collection, query, update, *args, **kwargs):
            nonlocal intercepted
            if (
                not intercepted
                and collection.full_name == store.conversations.full_name
                and query.get("owner_token") == claim.owner_token
                and "deadline" in query
            ):
                intercepted = True
                assert await collection.find_one(query, session=kwargs["session"])
                paused.set()
                await asyncio.wait_for(resume.wait(), 5)
            return await original(collection, query, update, *args, **kwargs)

        monkeypatch.setattr(AsyncCollection, "update_one", pause)
        result = completed(claim, status="awaiting_confirmation" if with_proposal else "completed")
        stale = asyncio.create_task(
            store.finish(CONTEXT, claim, result, proposal=proposal() if with_proposal else None)
        )
        try:
            await asyncio.wait_for(paused.wait(), 5)
            clock.now += timedelta(seconds=61)
            other = ConversationStore(database, settings, clock=clock)
            replacement = await reserve(
                other,
                request("replacement", conversation_id=claim.turn.conversation_id, revision=1),
            )
            resume.set()
            with pytest.raises(ApiError) as caught:
                await stale
            assert caught.value.code == "conversation_conflict"
            assert intercepted
            assert (await database.conversations.find_one({"_id": claim.turn.conversation_id}))[
                "owner_token"
            ] == replacement.owner_token
            assert (await database.conversation_turns.find_one({"_id": claim.turn.turn_id}))[
                "public"
            ]["status"] == "interrupted"
            assert await database.conversation_actions.count_documents({}) == 0
        finally:
            resume.set()
            if not stale.done():
                stale.cancel()
            await asyncio.gather(stale, return_exceptions=True)

    exercise(run)


def test_transaction_retry_reuses_proposal_identity_and_submission_key(monkeypatch):
    async def run(store, database, settings, clock):
        claim = await reserve(store)
        attempted = []
        original = AsyncCollection.insert_one

        async def fail_once(collection, document, *args, **kwargs):
            if collection.full_name == store.actions.full_name:
                attempted.append(deepcopy(document))
                if len(attempted) == 1:
                    raise OperationFailure(
                        "Injected transaction retry",
                        code=112,
                        details={"errorLabels": ["TransientTransactionError"]},
                    )
            return await original(collection, document, *args, **kwargs)

        monkeypatch.setattr(AsyncCollection, "insert_one", fail_once)
        await store.finish(
            CONTEXT, claim, completed(claim, status="awaiting_confirmation"), proposal=proposal()
        )
        assert len(attempted) == 2 and attempted[0] == attempted[1]
        assert await database.conversation_actions.count_documents({}) == 1
        assert (await store.history("demo", claim.turn.conversation_id)).turns[
            0
        ].status == "awaiting_confirmation"

    exercise(run)
