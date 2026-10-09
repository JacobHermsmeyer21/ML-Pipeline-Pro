"""Confirmed immutable actions; inference never participates in execution."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from pymongo.errors import PyMongoError

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.conversation_schemas import TOOL_BYTES, ActionDecision, ConversationAction
from ml_pipeline_pro.conversation_store import ConversationStore
from ml_pipeline_pro.errors import ApiError, ErrorDetail
from ml_pipeline_pro.tool_schemas import ToolCall, ToolContext, ToolFailure, ToolResult, ToolSuccess
from ml_pipeline_pro.tool_transport import HttpToolTransport, ToolTransport
from ml_pipeline_pro.tools import ToolDispatcher

UNCERTAIN_ERRORS = {
    "tool_timeout",
    "tool_transport_error",
    "tool_invalid_response",
    "tool_response_too_large",
}


def outcome_status(outcome: ToolResult) -> str:
    if isinstance(outcome, ToolSuccess):
        return "succeeded"
    if outcome.error.code in UNCERTAIN_ERRORS or (
        outcome.http_status is None or outcome.http_status >= 500
    ):
        return "unknown"
    return "failed"


class ConversationActions:
    def __init__(
        self,
        settings: Settings,
        store: ConversationStore,
        transport: ToolTransport,
        *,
        clock: Callable[[], datetime] | None = None,
    ):
        if isinstance(transport, HttpToolTransport) and (
            transport.max_response_bytes is None or transport.max_response_bytes > TOOL_BYTES
        ):
            raise ValueError("Action HTTP transport requires the approved response byte cap")
        self.settings, self.store, self.transport = settings.model_copy(deep=True), store, transport
        self.clock = clock or (lambda: datetime.now(UTC))

    async def decide(
        self,
        context: ToolContext,
        conversation_id: str,
        action_id: str,
        decision: ActionDecision,
    ) -> ConversationAction:
        if not self.settings.chat_enabled:
            raise ApiError(503, "chat_unavailable", "Conversation decisions are disabled")
        claim = None
        try:
            async with asyncio.timeout(self.settings.chat_action_timeout_seconds):
                claim = await self.store.decide(
                    context,
                    conversation_id,
                    action_id,
                    decision,
                    deadline=self.clock()
                    + timedelta(seconds=self.settings.chat_action_timeout_seconds),
                )
                if claim.owner_token is None:
                    return claim.action
                trusted = ToolContext(
                    project_id=context.project_id,
                    api_key=context.api_key,
                    correlation_id=claim.action.attempts[-1].correlation_id,
                    allow_mutations=True,
                    submission_key=claim.submission_key,
                )
                outcome = await ToolDispatcher(self.transport).execute(claim.action.tool, trusted)
                if isinstance(outcome, ToolFailure) and outcome.error.details:
                    # Queue failure can retain accepted IDs. Refresh through the
                    # same project boundary while preserving the original error.
                    for field, tool in (
                        ("experiment_id", "get_experiment"),
                        ("tuning_job_id", "get_tuning_job"),
                    ):
                        record_id = outcome.error.details.get(field)
                        if isinstance(record_id, str):
                            remaining = (claim.deadline - self.clock()).total_seconds()
                            # Reserve a dependency timeout for saving the audit;
                            # optional reads must not consume the known result.
                            if remaining > 2 * self.settings.dependency_timeout_seconds:
                                try:
                                    async with asyncio.timeout(
                                        self.settings.dependency_timeout_seconds
                                    ):
                                        refreshed = await ToolDispatcher(self.transport).execute(
                                            ToolCall(name=tool, arguments={field: record_id}),
                                            trusted.model_copy(
                                                update={
                                                    "allow_mutations": False,
                                                    "submission_key": None,
                                                }
                                            ),
                                        )
                                    outcome.error.details["record_refresh"] = refreshed.model_dump()
                                except TimeoutError:
                                    outcome.error.details["record_refresh_unavailable"] = True
                            else:
                                outcome.error.details["record_refresh_unavailable"] = True
                            break
                try:
                    return await self.store.finish_action(
                        context,
                        claim,
                        outcome,
                        status=outcome_status(outcome),
                    )
                except ApiError as exc:
                    if exc.code != "chat_limit_exceeded":
                        raise
                    # Dispatch has happened: reject the full oversized audit and
                    # explicitly retain uncertainty without partial evidence.
                    minimal = ToolFailure(
                        tool_name=claim.action.tool.name,
                        correlation_id=trusted.correlation_id,
                        error=ErrorDetail(
                            code="chat_limit_exceeded",
                            message="Action evidence could not be saved",
                            correlation_id=trusted.correlation_id,
                            details={"evidence_not_saved": True},
                        ),
                    )
                    if isinstance(outcome, ToolSuccess):
                        field = (
                            "experiment_id"
                            if claim.action.tool.name == "create_experiment"
                            else "tuning_job_id"
                        )
                        known_ids = {field: outcome.data.get("id")}
                    else:
                        known_ids = outcome.error.details or {}
                    for field in ("experiment_id", "tuning_job_id"):
                        value = known_ids.get(field)
                        if isinstance(value, str) and len(value.encode("utf-8")) <= 128:
                            minimal.error.details[field] = value
                    return await self.store.finish_action(context, claim, minimal, status="unknown")
        except TimeoutError:
            if claim is None:
                raise ApiError(
                    504,
                    "chat_timeout",
                    "Action claim deadline expired",
                    {"conversation_id": conversation_id, "action_id": action_id},
                ) from None
            # Deadline ownership ended; only reconciliation can transition it.
            try:
                return await self.store.action(context.project_id, conversation_id, action_id)
            except PyMongoError:
                raise ApiError(
                    503,
                    "storage_unavailable",
                    "Action storage is unavailable; inspect outcome",
                    {"conversation_id": conversation_id, "action_id": action_id},
                ) from None
        except PyMongoError:
            raise ApiError(
                503,
                "storage_unavailable",
                "Action storage is unavailable; inspect outcome",
                {"conversation_id": conversation_id, "action_id": action_id},
            ) from None
