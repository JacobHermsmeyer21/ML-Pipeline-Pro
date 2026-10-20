"""Facts from current successful public tool snapshots, never model values."""

import json
from copy import deepcopy
from typing import Any

from ml_pipeline_pro.conversation_diagnostics import safe_validation_details
from ml_pipeline_pro.conversation_schemas import FactRequest, ModelReply, VerifiedFact
from ml_pipeline_pro.errors import ApiError
from ml_pipeline_pro.tool_schemas import EvidenceReference, ToolSuccess

_FIELDS = {
    "id",
    "short_id",
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
            "algorithm",
            "l2_strength",
            "max_runtime_seconds",
        )
    )
_FIELDS.update({"limits.max_trials", "limits.max_runtime_seconds", "limits.concurrency"})

FACT_GUIDANCE_PREFIX = "Current-turn admissible fact references follow as JSON data. "


def fact_guided_tools(tools, messages):
    """Narrow model-facing field choices; public schemas and host policy stay intact."""
    for message in messages:
        if message.get("role") != "system" or not message.get("content", "").startswith(
            FACT_GUIDANCE_PREFIX
        ):
            continue
        references = [
            FactRequest.model_validate(ref)
            for ref in json.loads(message["content"].split("\n", 1)[1])
        ]
        if not references:
            return tools
        if any(ref.field not in _FIELDS for ref in references):
            raise ValueError("Invalid host fact guidance")
        guided = deepcopy(tools)
        for tool in guided:
            function = tool["function"]
            if function["name"] == "finish_conversation":
                properties = function["parameters"]["$defs"]["FactRequest"]["properties"]
                properties["field"]["enum"] = sorted({ref.field for ref in references})
                properties["record_id"]["enum"] = sorted({ref.record_id for ref in references})
        return guided
    return tools


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
            key: (
                {
                    name: context_data(metric)
                    for name, metric in item.items()
                    if f"metrics.{name}" in _FIELDS
                }
                if key == "metrics" and isinstance(item, dict)
                else context_data(item)
            )
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

    def _fact_value(self, request: FactRequest):
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
        return value

    def available_facts(self) -> list[FactRequest]:
        """Use the resolver's exact rules, without publishing any fact values."""
        references = []
        for record_id in sorted({identity for _, identity in self.records}):
            for field in sorted(_FIELDS):
                request = FactRequest(record_id=record_id, field=field)
                try:
                    self._fact_value(request)
                except ApiError:
                    continue
                references.append(request)
        return references

    def resolve(self, reply: ModelReply) -> list[VerifiedFact]:
        ids = {ref.record_id for ref in self.references.values()}
        if any(record_id not in ids for record_id in reply.citations):
            raise invalid_evidence("unknown_citation")
        return [
            VerifiedFact(
                record_id=request.record_id,
                field=request.field,
                value=deepcopy(self._fact_value(request)),
            )
            for request in reply.facts
        ]
