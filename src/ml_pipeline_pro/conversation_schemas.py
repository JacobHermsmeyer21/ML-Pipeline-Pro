"""Conversation wire contracts; credentials and execution ownership stay private."""

import hashlib
import json
from datetime import datetime
from typing import Any, Literal

from pydantic import AwareDatetime, Field, field_validator, model_validator

from ml_pipeline_pro.schemas import RequestModel, Sha256
from ml_pipeline_pro.tool_schemas import (
    CorrelationId,
    EvidenceReference,
    ResourceId,
    ToolCall,
    ToolResult,
)

REQUEST_BYTES = 64 * 1024
MESSAGE_BYTES = 8 * 1024
CONTEXT_BYTES = 64 * 1024
TOOL_BYTES = 128 * 1024
RECORD_BYTES = 256 * 1024
HISTORY_TURNS = 10

TurnStatus = Literal[
    "running", "completed", "needs_input", "awaiting_confirmation", "failed", "interrupted"
]
ActionStatus = Literal[
    "pending_confirmation",
    "rejected",
    "expired",
    "superseded",
    "running",
    "succeeded",
    "failed",
    "unknown",
]


def serialized(value: Any) -> bytes:
    """Canonical finite JSON for replay bodies and action fingerprints."""

    def encode(item: Any) -> str:
        if isinstance(item, datetime):
            return item.isoformat()
        raise TypeError("Unsupported serialized value")

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=encode,
    ).encode("utf-8")


def fingerprint(value: Any) -> str:
    return hashlib.sha256(serialized(value)).hexdigest()


class ChatRequest(RequestModel):
    request_id: ResourceId
    message: str = Field(min_length=1)
    expected_revision: int = Field(strict=True, ge=0)
    conversation_id: ResourceId | None = None

    @field_validator("message")
    @classmethod
    def message_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > MESSAGE_BYTES:
            raise ValueError("Message exceeds the UTF-8 byte limit")
        return value


class ActionDecision(RequestModel):
    decision: Literal["approve", "reject"]
    arguments_hash: Sha256


class FactRequest(RequestModel):
    record_id: ResourceId
    field: str = Field(pattern=r"^[a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)*$", max_length=128)


class VerifiedFact(FactRequest):
    value: Any


class ModelReply(RequestModel):
    """The model requests fact references; the host renders their saved values."""

    message: str = Field(max_length=8192)
    citations: list[ResourceId] = Field(default_factory=list, max_length=100)
    facts: list[FactRequest] = Field(default_factory=list, max_length=100)
    required_inputs: list[str] = Field(default_factory=list, max_length=30)


class ModelStep(RequestModel):
    call: ToolCall | None = None
    reply: ModelReply | None = None
    usage: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def exactly_one_result(self):
        if (self.call is None) == (self.reply is None):
            raise ValueError("A model step must contain exactly one tool call or reply")
        return self


class ActionAttempt(RequestModel):
    number: int = Field(strict=True, ge=1, le=3)
    correlation_id: CorrelationId
    deadline: AwareDatetime
    status: Literal["running", "succeeded", "failed", "unknown"]
    outcome: ToolResult | None = None


class ConversationAction(RequestModel):
    action_id: ResourceId
    conversation_id: ResourceId
    turn_id: ResourceId
    revision: int = Field(strict=True, ge=1)
    status: ActionStatus
    tool: ToolCall
    arguments_hash: Sha256
    argument_origin: Literal["model_proposed"] = "model_proposed"
    expires_at: AwareDatetime
    decision: dict[str, Any] | None = None
    attempts: list[ActionAttempt] = Field(default_factory=list, max_length=3)
    outcome: ToolResult | None = None


class ConversationTurn(RequestModel):
    conversation_id: ResourceId
    turn_id: ResourceId
    request_id: ResourceId
    revision: int = Field(strict=True, ge=1)
    status: TurnStatus
    user_message: str
    message: str = ""
    correlation_id: CorrelationId
    required_inputs: list[str] = Field(default_factory=list)
    facts: list[VerifiedFact] = Field(default_factory=list)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    pending_action: ConversationAction | None = None
    history_omitted: bool = False
    error: dict[str, Any] | None = None
    model_provenance: dict[str, Any] = Field(default_factory=dict)


class ConversationHistory(RequestModel):
    conversation_id: ResourceId
    revision: int = Field(strict=True, ge=0)
    turns: list[ConversationTurn]
    limit: int = Field(strict=True, ge=1, le=100)
    offset: int = Field(strict=True, ge=0)
