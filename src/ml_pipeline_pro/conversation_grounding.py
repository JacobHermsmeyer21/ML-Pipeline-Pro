"""Facts from current successful public tool snapshots, never model values."""

from copy import deepcopy
from typing import Any

from ml_pipeline_pro.conversation_diagnostics import safe_validation_details
from ml_pipeline_pro.conversation_schemas import ModelReply, VerifiedFact
from ml_pipeline_pro.errors import ApiError
from ml_pipeline_pro.tool_schemas import EvidenceReference, ToolSuccess

_FIELDS = {
    "id",
    "project_id",
    "schema_version",
    "created_at",
    "updated_at",
    "name",
    "version",
    "framework",
    "task",
    "architecture",
    "dataset_id",
    "model_id",
    "status",
    "attempts",
    "started_at",
    "completed_at",
    "heartbeat_at",
    "test_evaluated",
    "tuning_job_id",
    "tuning_trial_number",
    "experiment_id",
    "number",
    "objective_metric",
    "objective_value",
    "direction",
    "phase",
    "scheduled_trials",
    "completed_trials",
    "failed_trials",
    "best_trial_id",
    "best_experiment_id",
    "best_value",
    "final_evaluation",
    "stop_reason",
    "duration_seconds",
    "row_counts.train",
    "row_counts.validation",
    "row_counts.test",
    "comparison.metric",
    "comparison.direction",
    "comparison.best_experiment_id",
    "metrics.validation_accuracy",
    "metrics.validation_f1",
    "metrics.train_loss",
}
for _prefix in ("config", "best_config"):
    _FIELDS.update(
        f"{_prefix}.{name}"
        for name in (
            "seed",
            "epochs",
            "batch_size",
            "learning_rate",
            "hidden_units",
            "max_runtime_seconds",
        )
    )
_FIELDS.update({"limits.max_trials", "limits.max_runtime_seconds", "limits.concurrency"})


def invalid_evidence(reason="invalid_evidence") -> ApiError:
    return ApiError(
        422,
        "model_invalid_response",
        "Reply references unsupported or absent tool evidence",
        safe_validation_details(
            {"validation_stage": "evidence_resolution", "validation_reason": reason}
        ),
    )


def context_data(value: Any) -> Any:
    """Minimize model context; retain complete public snapshots in the audit."""
    blocked = {
        "artifacts",
        "dependencies",
        "uri",
        "worker_token",
        "owner_token",
        "submission_key",
        "lease_expires_at",
        "reservation",
        "api_key",
        "headers",
        "reasoning_content",
        "correlation_id",
    }
    if isinstance(value, dict):
        return {
            key: context_data(item)
            for key, item in value.items()
            if key not in blocked and not key.startswith("test_")
        }
    if isinstance(value, list):
        return [context_data(item) for item in value]
    return value


def supplied_snapshot(normalized: Any, supplied: Any) -> Any:
    """Keep validated values only for fields the upstream API actually supplied."""
    if isinstance(normalized, dict) and isinstance(supplied, dict):
        return {
            key: supplied_snapshot(value, supplied[key])
            for key, value in normalized.items()
            if key in supplied
        }
    if isinstance(normalized, list) and isinstance(supplied, list):
        return [
            supplied_snapshot(value, raw) for value, raw in zip(normalized, supplied, strict=True)
        ]
    return normalized


class EvidenceLedger:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.records: dict[tuple[str, str], dict[str, Any]] = {}
        self.references: dict[tuple[str, str, str], EvidenceReference] = {}

    def add(self, result: ToolSuccess) -> None:
        for reference in result.evidence:
            if reference.project_id != self.project_id:
                raise invalid_evidence()
            self.references[(reference.kind, reference.record_id, reference.role)] = reference
        data = result.data
        records = data.get("items", data.get("experiments", [data]))
        if not isinstance(records, list):
            raise invalid_evidence()
        for record in records:
            if (
                not isinstance(record, dict)
                or not {"id", "project_id", "schema_version", "created_at", "updated_at"}
                <= record.keys()
            ):
                raise invalid_evidence()
            matches = {
                ref.kind
                for ref in result.evidence
                if ref.record_id == record["id"] and ref.role in {"record", "winner"}
            }
            if record["project_id"] != self.project_id or len(matches) != 1:
                raise invalid_evidence()
            snapshot = deepcopy(record)
            if "experiments" in data:
                snapshot["comparison"] = {
                    key: data[key]
                    for key in ("metric", "direction", "best_experiment_id")
                    if key in data
                }
            self.records[(matches.pop(), record["id"])] = snapshot

    def contains(self, kind: str, record_id: str) -> bool:
        return (kind, record_id) in self.records

    @property
    def evidence(self) -> list[EvidenceReference]:
        return list(self.references.values())

    def resolve(self, reply: ModelReply) -> list[VerifiedFact]:
        ids = {ref.record_id for ref in self.references.values()}
        if any(record_id not in ids for record_id in reply.citations):
            raise invalid_evidence("unknown_citation")
        facts = []
        for request in reply.facts:
            matches = [
                record
                for (_, record_id), record in self.records.items()
                if record_id == request.record_id
            ]
            if request.field not in _FIELDS:
                raise invalid_evidence("unsupported_fact_field")
            if len(matches) != 1:
                raise invalid_evidence("ambiguous_record")
            value: Any = matches[0]
            for part in request.field.split("."):
                if not isinstance(value, dict) or part not in value:
                    raise invalid_evidence("missing_fact_field")
                value = value[part]
            if isinstance(value, (dict, list)):
                raise invalid_evidence("nonscalar_fact")
            facts.append(
                VerifiedFact(
                    record_id=request.record_id, field=request.field, value=deepcopy(value)
                )
            )
        return facts
