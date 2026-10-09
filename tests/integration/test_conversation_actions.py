"""Action claims against real MongoDB, including forced competing snapshots."""

import asyncio
from datetime import timedelta

import pytest
from pymongo.asynchronous.collection import AsyncCollection

from ml_pipeline_pro.conversation_schemas import ActionDecision
from ml_pipeline_pro.conversation_store import ConversationStore
from ml_pipeline_pro.errors import ApiError, ErrorDetail
from ml_pipeline_pro.tool_schemas import ToolContext, ToolFailure, ToolSuccess
from tests.integration.test_conversation_store import (
    CONTEXT,
    completed,
    exercise,
    proposal,
    request,
    reserve,
)
from tests.integration.test_conversation_store import pytestmark as store_marks

pytestmark = store_marks


async def saved_action(store):
    claim = await reserve(store)
    turn = await store.finish(
        CONTEXT,
        claim,
        completed(claim, status="awaiting_confirmation"),
        proposal=proposal(),
    )
    return turn.pending_action


async def decide(store, action, decision="approve", *, context=CONTEXT, arguments_hash=None):
    return await store.decide(
        context,
        action.conversation_id,
        action.action_id,
        ActionDecision(decision=decision, arguments_hash=arguments_hash or action.arguments_hash),
        deadline=store._now() + timedelta(seconds=30),
    )


def success():
    return ToolSuccess(
        tool_name="create_experiment",
        correlation_id="original",
        http_status=202,
        data={"id": "accepted", "status": "queued"},
        evidence=[],
    )


def failure(status=503):
    return ToolFailure(
        tool_name="create_experiment",
        correlation_id="original",
        http_status=status,
        error=ErrorDetail(
            code="upstream_error",
            message="Saved fixture-project-secret",
            correlation_id="original",
            details={"experiment_id": "accepted"},
        ),
    )


def test_exact_hash_scoping_rejection_and_terminal_replays():
    async def run(store, database, settings, clock):
        action = await saved_action(store)
        for context, hash_value, code in (
            (CONTEXT, "0" * 64, "action_conflict"),
            (ToolContext(project_id="foreign"), action.arguments_hash, "conversation_not_found"),
        ):
            with pytest.raises(ApiError) as caught:
                await decide(store, action, context=context, arguments_hash=hash_value)
            assert caught.value.code == code
        rejected = await decide(store, action, "reject")
        assert rejected.owner_token is None and rejected.action.status == "rejected"
        assert not rejected.action.attempts
        assert rejected.action.decision["authentication"] == "local_project"
        assert (await decide(store, action, "reject")).action == rejected.action
        with pytest.raises(ApiError):
            await decide(store, action)
        assert (await database.conversation_actions.find_one({"_id": action.action_id}))["public"][
            "status"
        ] == "rejected"

    exercise(run)


def test_successful_completion_replay_and_new_turn_preserve_active_owner():
    async def run(store, database, settings, clock):
        action = await saved_action(store)
        claim = await decide(store, action)
        active = await reserve(
            store, request("next", conversation_id=action.conversation_id, revision=1)
        )
        finished = await store.finish_action(CONTEXT, claim, success(), status="succeeded")
        replay = await decide(store, action)
        assert replay.owner_token is None and replay.action == finished
        parent = await database.conversations.find_one({"_id": action.conversation_id})
        assert parent["owner_token"] == active.owner_token and parent["revision"] == 2
        assert (await store.history("demo", action.conversation_id)).turns[
            0
        ].pending_action == finished
        assert len(finished.attempts) == 1 and finished.outcome.data["status"] == "queued"

    exercise(run)


@pytest.mark.parametrize("stale", ["expired", "superseded"])
def test_stale_pending_action_cannot_be_approved(stale):
    async def run(store, database, settings, clock):
        action = await saved_action(store)
        if stale == "expired":
            clock.now = action.expires_at
        else:
            await reserve(
                store, request("next", conversation_id=action.conversation_id, revision=1)
            )
        assert (
            await store.action("demo", action.conversation_id, action.action_id)
        ).status == stale
        with pytest.raises(ApiError) as caught:
            await decide(store, action)
        assert caught.value.code == "action_conflict"

    exercise(run)


def test_unknown_retry_uses_original_key_after_revision_advance_and_caps_three_attempts():
    async def run(store, database, settings, clock):
        settings = settings.model_copy(update={"project_api_keys": {"demo": CONTEXT.api_key}})
        store = ConversationStore(database, settings, clock=clock)
        action = await saved_action(store)
        first = await decide(store, action)
        await store.finish_action(CONTEXT, first, failure(), status="unknown")
        next_turn = await reserve(
            store, request("next", conversation_id=action.conversation_id, revision=1)
        )
        await store.finish(CONTEXT, next_turn, completed(next_turn))
        for number in (2, 3):
            claim = await decide(ConversationStore(database, settings, clock=clock), action)
            assert claim.submission_key == first.submission_key
            assert claim.owner_token != first.owner_token and claim.action.tool == first.action.tool
            assert claim.action.attempts[-1].number == number
            # A definitive later rejection does not resolve earlier uncertainty.
            result = await store.finish_action(CONTEXT, claim, failure(409), status="failed")
            assert result.status == "unknown" and result.attempts[-1].status == "failed"
        with pytest.raises(ApiError) as caught:
            await decide(store, action)
        assert caught.value.code == "action_attempts_exhausted"
        public = await store.action("demo", action.conversation_id, action.action_id)
        assert public.attempts[0].outcome.error.details["experiment_id"] == "accepted"
        assert "fixture-project-secret" not in str(public.model_dump())
        assert public.decision["authentication"] == "project_key"
        assert "person" not in public.decision

    exercise(run)


def test_expired_attempt_is_unknown_and_late_completion_cannot_overwrite_new_claim():
    async def run(store, database, settings, clock):
        action = await saved_action(store)
        old = await decide(store, action)
        clock.now = old.deadline
        public = await store.action("demo", action.conversation_id, action.action_id)
        assert public.status == public.attempts[0].status == "unknown"
        replacement = await decide(store, action)
        with pytest.raises(ApiError) as caught:
            await store.finish_action(CONTEXT, old, success(), status="succeeded")
        assert caught.value.code == "action_conflict"
        saved = await database.conversation_actions.find_one({"_id": action.action_id})
        assert saved["owner_token"] == replacement.owner_token
        final = await store.finish_action(CONTEXT, replacement, success(), status="succeeded")
        assert [attempt.status for attempt in final.attempts] == ["unknown", "succeeded"]

    exercise(run)


def test_competing_approval_snapshots_commit_one_dispatch_claim(monkeypatch):
    async def run(store, database, settings, clock):
        action = await saved_action(store)
        other = ConversationStore(database, settings, clock=clock)
        original = AsyncCollection.find_one
        both = asyncio.Event()
        snapshots = 0

        async def barrier(collection, query, *args, **kwargs):
            nonlocal snapshots
            document = await original(collection, query, *args, **kwargs)
            if (
                collection.full_name == store.actions.full_name
                and document
                and document["public"]["status"] == "pending_confirmation"
            ):
                snapshots += 1
                if snapshots == 2:
                    both.set()
                await asyncio.wait_for(both.wait(), 5)
            return document

        monkeypatch.setattr(AsyncCollection, "find_one", barrier)
        claims = await asyncio.gather(decide(store, action), decide(other, action))
        assert snapshots >= 2 and sum(bool(claim.owner_token) for claim in claims) == 1
        assert len(claims[0].action.attempts) == len(claims[1].action.attempts) == 1
        assert claims[0].action == claims[1].action

    exercise(run)


def test_new_turn_wins_after_approval_snapshot_and_prevents_dispatch(monkeypatch):
    async def run(store, database, settings, clock):
        action = await saved_action(store)
        original = AsyncCollection.update_one
        paused, resume = asyncio.Event(), asyncio.Event()
        intercepted = False

        async def pause(collection, query, update, *args, **kwargs):
            nonlocal intercepted
            if (
                not intercepted
                and collection.full_name == store.conversations.full_name
                and "fence_revision" in query
            ):
                intercepted = True
                paused.set()
                await asyncio.wait_for(resume.wait(), 5)
            return await original(collection, query, update, *args, **kwargs)

        monkeypatch.setattr(AsyncCollection, "update_one", pause)
        task = asyncio.create_task(decide(store, action))
        try:
            await asyncio.wait_for(paused.wait(), 5)
            other = ConversationStore(database, settings, clock=clock)
            new_turn = await reserve(
                other, request("next", conversation_id=action.conversation_id, revision=1)
            )
            resume.set()
            with pytest.raises(ApiError) as caught:
                await task
            assert caught.value.code == "action_conflict"
            assert (
                await store.action("demo", action.conversation_id, action.action_id)
            ).status == "superseded"
            assert (await database.conversations.find_one({"_id": action.conversation_id}))[
                "owner_token"
            ] == new_turn.owner_token
        finally:
            resume.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    exercise(run)


@pytest.mark.parametrize("replace_owner", [False, True])
def test_completion_snapshot_cannot_publish_after_deadline_or_attempt_takeover(
    replace_owner, monkeypatch
):
    async def run(store, database, settings, clock):
        action = await saved_action(store)
        old = await decide(store, action)
        original = AsyncCollection.update_one
        paused, resume = asyncio.Event(), asyncio.Event()
        intercepted = False

        async def pause(collection, query, update, *args, **kwargs):
            nonlocal intercepted
            if not intercepted and collection.full_name == store.conversations.full_name:
                intercepted = True
                paused.set()
                await asyncio.wait_for(resume.wait(), 5)
            return await original(collection, query, update, *args, **kwargs)

        monkeypatch.setattr(AsyncCollection, "update_one", pause)
        task = asyncio.create_task(store.finish_action(CONTEXT, old, success(), status="succeeded"))
        try:
            await asyncio.wait_for(paused.wait(), 5)
            clock.now = old.deadline
            replacement = None
            if replace_owner:
                replacement = await decide(
                    ConversationStore(database, settings, clock=clock), action
                )
            resume.set()
            with pytest.raises(ApiError) as caught:
                await task
            assert caught.value.code == "action_conflict"
            public = await store.action("demo", action.conversation_id, action.action_id)
            assert public.status == ("running" if replace_owner else "unknown")
            assert public.outcome is None
            if replacement:
                raw = await database.conversation_actions.find_one({"_id": action.action_id})
                assert raw["owner_token"] == replacement.owner_token
        finally:
            resume.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    exercise(run)
