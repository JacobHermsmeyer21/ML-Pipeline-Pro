"""Fixed, payload-free reply rejection categories shared by host and adapter."""

from ml_pipeline_pro.conversation_model import ConversationModelError

# Only these exact pairs may cross the saved-error/logging boundary.
VALIDATION_REASONS = {
    "provider_response": frozenset({"invalid_envelope", "invalid_json", "invalid_usage"}),
    "reply_schema": frozenset({"invalid_json", "invalid_tool_call", "invalid_reply_schema"}),
    "host_step": frozenset({"invalid_step", "invalid_usage"}),
    "evidence_resolution": frozenset(
        {
            "invalid_evidence",
            "unknown_citation",
            "unsupported_fact_field",
            "missing_fact_field",
            "ambiguous_record",
            "nonscalar_fact",
        }
    ),
    "unknown": frozenset({"unknown_validation"}),
}


def safe_validation_details(details=None):
    if isinstance(details, dict):
        stage = details.get("validation_stage")
        reason = details.get("validation_reason")
        if (
            type(stage) is str
            and type(reason) is str
            and reason in VALIDATION_REASONS.get(stage, ())
        ):
            return {"validation_stage": stage, "validation_reason": reason}
    return {"validation_stage": "unknown", "validation_reason": "unknown_validation"}


class ReplyValidationError(ConversationModelError):
    """No rejected values, field names or exception strings are retained."""

    def __init__(self, stage, reason):
        super().__init__("model_invalid_response", "Model reply failed validation")
        self.details = safe_validation_details(
            {"validation_stage": stage, "validation_reason": reason}
        )
