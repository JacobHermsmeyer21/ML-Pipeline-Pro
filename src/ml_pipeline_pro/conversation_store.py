"""Transactional conversation turns and immutable proposals; no external calls."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from pymongo.errors import DuplicateKeyError
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.conversation_schemas import (
    RECORD_BYTES,
    ActionAttempt,
    ActionDecision,
    ChatRequest,
    ConversationAction,
    ConversationHistory,
    ConversationTurn,
    fingerprint,
    serialized,
)
from ml_pipeline_pro.errors import ApiError
from ml_pipeline_pro.logging import JsonFormatter, configured_secrets
from ml_pipeline_pro.tool_schemas import ToolCall, ToolContext, ToolResult
from ml_pipeline_pro.tools import validated_proposal


@dataclass(frozen=True)
class TurnClaim:
    """Host-private reservation. Replays carry no permission to generate."""

    turn: ConversationTurn
    owner_token: str | None
    deadline: datetime
    replayed: bool


@dataclass(frozen=True)
class ActionClaim:
    """Only a newly committed attempt carries dispatch authority."""

    action: ConversationAction
    owner_token: str | None = None
    submission_key: str | None = None
    deadline: datetime | None = None


def _action_conflict() -> ApiError:
    return ApiError(409, "action_conflict", "Action decision, fingerprint or ownership changed")


def _conflict() -> ApiError:
    return ApiError(409, "conversation_conflict", "Conversation revision or turn ownership changed")


def _bounded(document: dict[str, Any]) -> dict[str, Any]:
    if len(serialized(document)) > RECORD_BYTES:
        raise ApiError(422, "chat_limit_exceeded", "Conversation record exceeds byte limit")
    return document


def _mongodb_time(value: datetime) -> datetime:
    """Return the same UTC millisecond precision BSON will persist."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Conversation time must be timezone-aware")
    value = value.astimezone(UTC)
    return value.replace(microsecond=value.microsecond // 1000 * 1000)


class ConversationStore:
    """Schema-v1 additive collections; transaction-capable MongoDB is required.

    Reservation/completion and reconciliation serialize on a conversation write.
    Transaction callbacks may retry and contain database work only. IDs, hashes,
    redaction, validated proposals and submission keys are prepared outside them.
    Action decisions and attempt completion also write that parent. HTTP calls
    occur only after the attempt transaction has committed.
    """

    def __init__(
        self, database, settings: Settings, *, clock: Callable[[], datetime] | None = None
    ):
        self.database = database
        self.conversations = database.get_collection("conversations")
        self.turns = database.get_collection("conversation_turns")
        self.actions = database.get_collection("conversation_actions")
        self._settings = settings.model_copy(deep=True)
        self._secrets = configured_secrets(settings)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._indexed = False
        self._index_lock = asyncio.Lock()

    def _now(self) -> datetime:
        return _mongodb_time(self._clock())

    async def ensure_indexes(self) -> None:
        async with self._index_lock:
            if self._indexed:
                return
            await self.conversations.create_index(
                [("project_id", 1), ("updated_at", -1)], name="conversation_project_updated"
            )
            await self.turns.create_index(
                [("project_id", 1), ("request_id", 1)], unique=True, name="chat_request"
            )
            await self.turns.create_index(
                [("project_id", 1), ("conversation_id", 1), ("sequence", 1)],
                unique=True,
                name="conversation_sequence",
            )
            await self.actions.create_index(
                [("project_id", 1), ("conversation_id", 1), ("turn_id", 1)],
                unique=True,
                name="conversation_turn_action",
            )
            self._indexed = True

    async def _transaction(self, callback):
        async with self.database.client.start_session() as session:
            return await session.with_transaction(
                callback,
                read_concern=ReadConcern("snapshot"),
                write_concern=WriteConcern("majority"),
            )

    def _safe(self, value: Any, context: ToolContext) -> Any:
        secrets = self._secrets + ((context.api_key.get_secret_value(),) if context.api_key else ())
        formatter = JsonFormatter(secrets)

        def redact(item):
            if isinstance(item, dict):
                return {formatter.redact(key): redact(child) for key, child in item.items()}
            if isinstance(item, list):
                return [redact(child) for child in item]
            return formatter.redact(item)

        return redact(value)

    @staticmethod
    def _scope(project_id: str, conversation_id: str) -> dict[str, Any]:
        return {"project_id": project_id, "conversation_id": conversation_id}

    async def _reconcile(self, project_id: str, conversation_id: str, session):
        query = {"_id": conversation_id, "project_id": project_id}
        conversation = await self.conversations.find_one(query, session=session)
        if conversation is None:
            raise ApiError(404, "conversation_not_found", "Conversation was not found")
        now = self._now()
        scope = self._scope(project_id, conversation_id)
        expired_turn = conversation["owner_token"] is not None and conversation["deadline"] <= now
        expired_actions = {
            **scope,
            "public.status": "pending_confirmation",
            "public.expires_at": {"$lte": now},
        }
        expired_action = await self.actions.find_one(expired_actions, session=session)
        expired_executions = {
            **scope,
            "public.status": "running",
            "deadline": {"$lte": now},
        }
        executions = await self.actions.find(expired_executions, session=session).to_list()
        if expired_turn or expired_action or executions:
            # A parent write makes transitions conflict with completion/decisions.
            update = {"$inc": {"fence_revision": 1}, "$set": {"updated_at": now}}
            if expired_turn:
                update["$set"].update(owner_token=None, active_turn_id=None, deadline=None)
            changed = await self.conversations.update_one(
                {
                    **query,
                    "revision": conversation["revision"],
                    "owner_token": conversation["owner_token"],
                },
                update,
                session=session,
            )
            if changed.matched_count != 1:
                raise _conflict()
            if expired_turn:
                changed = await self.turns.update_one(
                    {
                        **scope,
                        "_id": conversation["active_turn_id"],
                        "owner_token": conversation["owner_token"],
                        "public.status": "running",
                    },
                    {
                        "$set": {
                            "owner_token": None,
                            "updated_at": now,
                            "public.status": "interrupted",
                            "public.error": {
                                "code": "chat_interrupted",
                                "message": "Turn deadline expired; generation was not resumed",
                            },
                        }
                    },
                    session=session,
                )
                if changed.matched_count != 1:
                    raise _conflict()
            await self.actions.update_many(
                expired_actions,
                {"$set": {"public.status": "expired", "updated_at": now}},
                session=session,
            )
            for execution in executions:
                public = ConversationAction.model_validate(execution["public"])
                public.status = "unknown"
                public.attempts[-1].status = "unknown"
                await self.actions.update_one(
                    {**expired_executions, "_id": execution["_id"]},
                    {
                        "$set": {
                            "public": public.model_dump(),
                            "owner_token": None,
                            "updated_at": now,
                        }
                    },
                    session=session,
                )
            conversation = await self.conversations.find_one(query, session=session)
        return conversation

    async def _public_turn(self, document, session) -> ConversationTurn:
        turn = ConversationTurn.model_validate(document["public"])
        action = await self.actions.find_one(
            {**self._scope(document["project_id"], turn.conversation_id), "turn_id": turn.turn_id},
            session=session,
        )
        if action is not None:
            turn.pending_action = ConversationAction.model_validate(action["public"])
        return turn

    async def reserve(
        self, context: ToolContext, request: ChatRequest, *, deadline: datetime
    ) -> TurnClaim:
        """Atomically reserve one new turn or replay its project-scoped identity."""
        request = ChatRequest.model_validate(request.model_dump())
        deadline = _mongodb_time(deadline)
        if deadline - self._now() > timedelta(seconds=self._settings.chat_timeout_seconds):
            raise ValueError("Turn deadline exceeds the configured timeout")
        conversation_id = request.conversation_id or str(uuid4())
        turn_id, token = str(uuid4()), str(uuid4())
        body_hash = fingerprint(request.model_dump())
        public = ConversationTurn(
            conversation_id=conversation_id,
            turn_id=turn_id,
            request_id=request.request_id,
            revision=request.expected_revision + 1,
            status="running",
            user_message=self._safe(request.message, context),
            correlation_id=context.correlation_id,
        )
        now = self._now()
        document = _bounded(
            {
                "_id": turn_id,
                **self._scope(context.project_id, conversation_id),
                "schema_version": 1,
                "request_id": request.request_id,
                "sequence": public.revision,
                "request_hash": body_hash,
                "owner_token": token,
                "deadline": deadline,
                "created_at": now,
                "updated_at": now,
                "public": public.model_dump(),
            }
        )
        # Unique replay/sequence indexes must exist before the first reservation.
        await self.ensure_indexes()

        async def commit(session):
            saved = await self.turns.find_one(
                {"project_id": context.project_id, "request_id": request.request_id},
                session=session,
            )
            if saved is not None:
                if saved["request_hash"] != body_hash:
                    raise ApiError(
                        409, "chat_idempotency_conflict", "Request ID has a different body"
                    )
                await self._reconcile(context.project_id, saved["conversation_id"], session)
                saved = await self.turns.find_one(
                    {"_id": saved["_id"], "project_id": context.project_id}, session=session
                )
                return TurnClaim(
                    await self._public_turn(saved, session), None, saved["deadline"], True
                )
            if deadline <= self._now():
                raise ApiError(504, "chat_timeout", "Turn deadline expired before reservation")
            if request.conversation_id is None:
                if request.expected_revision != 0:
                    raise _conflict()
                await self.conversations.insert_one(
                    {
                        "_id": conversation_id,
                        "project_id": context.project_id,
                        "schema_version": 1,
                        "revision": 0,
                        "fence_revision": 0,
                        "owner_token": None,
                        "active_turn_id": None,
                        "deadline": None,
                        "created_at": now,
                        "updated_at": now,
                    },
                    session=session,
                )
            conversation = await self._reconcile(context.project_id, conversation_id, session)
            if conversation["revision"] != request.expected_revision or conversation["owner_token"]:
                raise _conflict()
            owner = await self.conversations.update_one(
                {
                    "_id": conversation_id,
                    "project_id": context.project_id,
                    "revision": request.expected_revision,
                    "owner_token": None,
                },
                {
                    "$inc": {"revision": 1, "fence_revision": 1},
                    "$set": {
                        "owner_token": token,
                        "active_turn_id": turn_id,
                        "deadline": deadline,
                        "updated_at": self._now(),
                    },
                },
                session=session,
            )
            if owner.matched_count != 1:
                raise _conflict()
            await self.actions.update_many(
                {
                    **self._scope(context.project_id, conversation_id),
                    "public.status": "pending_confirmation",
                },
                {"$set": {"public.status": "superseded", "updated_at": self._now()}},
                session=session,
            )
            await self.turns.insert_one(document, session=session)
            return TurnClaim(public.model_copy(deep=True), token, deadline, False)

        try:
            return await self._transaction(commit)
        except DuplicateKeyError:
            # A simultaneous first request may lose the unique request-ID race.
            # Its transaction rolled back; one fresh transaction reads the winner.
            return await self._transaction(commit)

    async def finish(
        self,
        context: ToolContext,
        claim: TurnClaim,
        result: ConversationTurn,
        *,
        proposal: ToolCall | None = None,
    ) -> ConversationTurn:
        """Publish a result/proposal only under the same unexpired parent owner."""
        result = ConversationTurn.model_validate(self._safe(result.model_dump(), context))
        if claim.replayed or claim.owner_token is None:
            raise _conflict()
        if result.status not in {"completed", "needs_input", "awaiting_confirmation", "failed"}:
            raise ValueError("Turn completion requires a supported final status")
        if (result.status == "awaiting_confirmation") != (
            proposal is not None
        ) or result.pending_action:
            raise ValueError("The store owns the saved proposal and its identity")
        action_document = None
        if proposal is not None:
            call = validated_proposal(
                ToolCall.model_validate(self._safe(proposal.model_dump(), context))
            )
            action = ConversationAction(
                action_id=str(uuid4()),
                conversation_id=result.conversation_id,
                turn_id=result.turn_id,
                revision=result.revision,
                status="pending_confirmation",
                tool=call,
                arguments_hash=fingerprint(call.model_dump()),
                expires_at=self._now() + timedelta(minutes=15),
            )
            result.pending_action = action
            action_document = _bounded(
                {
                    "_id": action.action_id,
                    **self._scope(context.project_id, action.conversation_id),
                    "turn_id": action.turn_id,
                    "schema_version": 1,
                    "submission_key": str(uuid4()),
                    "created_at": self._now(),
                    "updated_at": self._now(),
                    "public": action.model_dump(),
                }
            )
        public = result.model_dump()
        _bounded(public)

        async def commit(session):
            scope = self._scope(context.project_id, claim.turn.conversation_id)
            owner = await self.conversations.update_one(
                {
                    "_id": claim.turn.conversation_id,
                    "project_id": context.project_id,
                    "revision": claim.turn.revision,
                    "active_turn_id": claim.turn.turn_id,
                    "owner_token": claim.owner_token,
                    "deadline": {"$gt": self._now()},
                },
                {
                    "$inc": {"fence_revision": 1},
                    "$set": {
                        "owner_token": None,
                        "active_turn_id": None,
                        "deadline": None,
                        "updated_at": self._now(),
                    },
                },
                session=session,
            )
            if owner.matched_count != 1:
                raise _conflict()
            query = {
                **scope,
                "_id": claim.turn.turn_id,
                "owner_token": claim.owner_token,
                "public.status": "running",
                "deadline": {"$gt": self._now()},
            }
            saved = await self.turns.find_one(query, session=session)
            if saved is None or any(
                public[field] != saved["public"][field]
                for field in (
                    "conversation_id",
                    "turn_id",
                    "request_id",
                    "revision",
                    "user_message",
                    "correlation_id",
                )
            ):
                raise _conflict()
            _bounded({**saved, "public": public})
            if action_document is not None:
                await self.actions.insert_one(action_document, session=session)
            changed = await self.turns.update_one(
                {**query, "deadline": {"$gt": self._now()}},
                {"$set": {"public": public, "owner_token": None, "updated_at": self._now()}},
                session=session,
            )
            if changed.matched_count != 1:
                raise _conflict()
            return result.model_copy(deep=True)

        return await self._transaction(commit)

    async def decide(
        self,
        context: ToolContext,
        conversation_id: str,
        action_id: str,
        decision: ActionDecision,
        *,
        deadline: datetime,
    ) -> ActionClaim:
        """Commit an exact decision/attempt; repeated decisions never steal a claim."""
        decision = ActionDecision.model_validate(decision.model_dump())
        deadline = _mongodb_time(deadline)
        if deadline - self._now() > timedelta(seconds=self._settings.chat_action_timeout_seconds):
            raise ValueError("Action deadline exceeds configured timeout")
        token = str(uuid4())

        async def commit(session):
            parent = await self._reconcile(context.project_id, conversation_id, session)
            query = {**self._scope(context.project_id, conversation_id), "_id": action_id}
            saved = await self.actions.find_one(query, session=session)
            if saved is None:
                raise ApiError(404, "action_not_found", "Action was not found")
            action = ConversationAction.model_validate(saved["public"])
            if decision.arguments_hash != action.arguments_hash or (
                fingerprint(validated_proposal(action.tool).model_dump()) != action.arguments_hash
            ):
                raise _action_conflict()
            if action.status in {"expired", "superseded"}:
                raise _action_conflict()
            if action.status != "pending_confirmation":
                if action.decision is None or action.decision["decision"] != decision.decision:
                    raise _action_conflict()
                if action.status != "unknown":
                    return ActionClaim(action)
                if len(action.attempts) >= 3:
                    raise ApiError(
                        409,
                        "action_attempts_exhausted",
                        "Uncertain action requires operator investigation",
                    )
            elif parent["revision"] != action.revision or parent["owner_token"] is not None:
                raise _action_conflict()
            now = self._now()
            if deadline <= now:
                raise ApiError(504, "chat_timeout", "Action deadline expired before claim")
            changed = await self.conversations.update_one(
                {
                    "_id": conversation_id,
                    "project_id": context.project_id,
                    "revision": parent["revision"],
                    "fence_revision": parent["fence_revision"],
                },
                {"$inc": {"fence_revision": 1}, "$set": {"updated_at": now}},
                session=session,
            )
            if changed.matched_count != 1:
                raise _action_conflict()
            if deadline <= self._now():
                raise ApiError(504, "chat_timeout", "Action deadline expired during claim")
            if action.decision is None:
                action.decision = {
                    "decision": decision.decision,
                    "correlation_id": context.correlation_id,
                    "authentication": (
                        "project_key"
                        if context.api_key and self._settings.project_api_keys
                        else "local_project"
                    ),
                    "decided_at": now,
                }
            if decision.decision == "reject":
                action.status = "rejected"
                owner = None
            else:
                action.status = "running"
                action.attempts.append(
                    ActionAttempt(
                        number=len(action.attempts) + 1,
                        correlation_id=context.correlation_id,
                        deadline=deadline,
                        status="running",
                    )
                )
                owner = token
            document = _bounded(
                {
                    **saved,
                    "public": action.model_dump(),
                    "owner_token": owner,
                    "deadline": deadline if owner else None,
                    "updated_at": now,
                }
            )
            await self.actions.update_one(
                query,
                {"$set": {key: value for key, value in document.items() if key != "_id"}},
                session=session,
            )
            return ActionClaim(
                action,
                owner,
                saved["submission_key"] if owner else None,
                deadline if owner else None,
            )

        return await self._transaction(commit)

    async def finish_action(
        self,
        context: ToolContext,
        claim: ActionClaim,
        outcome: ToolResult,
        *,
        status: str,
    ) -> ConversationAction:
        """Fence the unexpired attempt and retain every public attempt outcome."""
        if not claim.owner_token or status not in {"succeeded", "failed", "unknown"}:
            raise _action_conflict()

        async def commit(session):
            action = claim.action
            scope = self._scope(context.project_id, action.conversation_id)
            query = {
                **scope,
                "_id": action.action_id,
                "owner_token": claim.owner_token,
                "public.status": "running",
                "deadline": {"$gt": self._now()},
            }
            saved = await self.actions.find_one(query, session=session)
            if saved is None:
                raise _action_conflict()
            public = ConversationAction.model_validate(saved["public"])
            # A later 4xx cannot establish that an earlier uncertain submission
            # was never accepted. Only successful same-key replay resolves it.
            public.status = (
                "unknown"
                if status == "failed"
                and any(attempt.status == "unknown" for attempt in public.attempts[:-1])
                else status
            )
            public.outcome = outcome
            public.attempts[-1].status = status
            public.attempts[-1].outcome = outcome
            public = ConversationAction.model_validate(self._safe(public.model_dump(), context))
            _bounded({**saved, "public": public.model_dump()})
            parent = await self.conversations.update_one(
                {"_id": action.conversation_id, "project_id": context.project_id},
                {"$inc": {"fence_revision": 1}, "$set": {"updated_at": self._now()}},
                session=session,
            )
            if parent.matched_count != 1:
                raise _action_conflict()
            changed = await self.actions.update_one(
                {**query, "deadline": {"$gt": self._now()}},
                {
                    "$set": {
                        "public": public.model_dump(),
                        "owner_token": None,
                        "updated_at": self._now(),
                    }
                },
                session=session,
            )
            if changed.matched_count != 1:
                raise _action_conflict()
            return public

        return await self._transaction(commit)

    async def history(
        self, project_id: str, conversation_id: str, *, limit: int = 50, offset: int = 0
    ) -> ConversationHistory:
        if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0:
            raise ValueError("Invalid conversation pagination")

        async def read(session):
            conversation = await self._reconcile(project_id, conversation_id, session)
            cursor = self.turns.find(self._scope(project_id, conversation_id), session=session)
            documents = await cursor.sort("sequence", 1).skip(offset).limit(limit).to_list()
            return ConversationHistory(
                conversation_id=conversation_id,
                revision=conversation["revision"],
                turns=[await self._public_turn(item, session) for item in documents],
                limit=limit,
                offset=offset,
            )

        return await self._transaction(read)

    async def action(
        self, project_id: str, conversation_id: str, action_id: str
    ) -> ConversationAction:
        async def read(session):
            await self._reconcile(project_id, conversation_id, session)
            saved = await self.actions.find_one(
                {**self._scope(project_id, conversation_id), "_id": action_id}, session=session
            )
            if saved is None:
                raise ApiError(404, "action_not_found", "Action was not found")
            return ConversationAction.model_validate(saved["public"])

        return await self._transaction(read)
