"""Serial host-loop substitute; transaction/ownership evidence uses real MongoDB."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from ml_pipeline_pro.conversation_schemas import (
    ConversationAction,
    ConversationHistory,
    ConversationTurn,
    fingerprint,
)
from ml_pipeline_pro.conversation_store import TurnClaim
from ml_pipeline_pro.errors import ApiError
from ml_pipeline_pro.logging import JsonFormatter


class MemoryConversations:
    def __init__(self):
        self.turns = {}
        self.requests = {}
        self.claims = {}
        self.revisions = {}
        self.reserve_calls = 0
        self.finish_error = None

    async def reserve(self, context, request, *, deadline):
        self.reserve_calls += 1
        identity = context.project_id, request.request_id
        body_hash = fingerprint(request.model_dump())
        if identity in self.requests:
            saved_hash, turn_id = self.requests[identity]
            if saved_hash != body_hash:
                raise ApiError(409, "chat_idempotency_conflict", "Different body")
            turn = self.turns[turn_id].model_copy(deep=True)
            return TurnClaim(
                turn, None, self.claims[turn_id].deadline, True, self.claims[turn_id].timeout_mode
            )
        conversation_id = request.conversation_id or str(uuid4())
        key = context.project_id, conversation_id
        if request.expected_revision != self.revisions.get(key, 0):
            raise ApiError(409, "conversation_conflict", "Wrong revision")
        token, turn_id = str(uuid4()), str(uuid4())
        secrets = (context.api_key.get_secret_value(),) if context.api_key else ()
        turn = ConversationTurn(
            conversation_id=conversation_id,
            turn_id=turn_id,
            request_id=request.request_id,
            revision=request.expected_revision + 1,
            status="running",
            user_message=JsonFormatter(secrets).redact(request.message),
            correlation_id=context.correlation_id,
        )
        claim = TurnClaim(
            turn.model_copy(deep=True),
            token,
            deadline,
            False,
            "diagnostic_unbounded" if deadline is None else "bounded",
        )
        self.claims[turn_id] = claim
        self.turns[turn_id] = turn
        self.requests[identity] = body_hash, turn_id
        self.revisions[key] = turn.revision
        return claim

    async def finish(self, context, claim, result, *, proposal=None):
        if self.finish_error:
            raise self.finish_error
        saved = result.model_copy(deep=True)
        if proposal:
            saved.pending_action = ConversationAction(
                action_id=str(uuid4()),
                conversation_id=saved.conversation_id,
                turn_id=saved.turn_id,
                revision=saved.revision,
                status="pending_confirmation",
                tool=proposal.model_copy(deep=True),
                arguments_hash=fingerprint(proposal.model_dump()),
                expires_at=datetime.now(UTC) + timedelta(minutes=15),
            )
        self.turns[result.turn_id] = saved
        return saved.model_copy(deep=True)

    async def history(self, project_id, conversation_id, *, limit=50, offset=0):
        if (project_id, conversation_id) not in self.revisions:
            raise ApiError(404, "conversation_not_found", "Conversation was not found")
        turns = sorted(
            [
                item.model_copy(deep=True)
                for item in self.turns.values()
                if item.conversation_id == conversation_id
            ],
            key=lambda item: item.revision,
        )
        return ConversationHistory(
            conversation_id=conversation_id,
            revision=self.revisions[(project_id, conversation_id)],
            turns=turns[offset : offset + limit],
            limit=limit,
            offset=offset,
        )
