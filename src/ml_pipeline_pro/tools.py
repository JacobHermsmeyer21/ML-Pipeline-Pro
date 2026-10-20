"""Allowlisted tools that delegate domain behavior to the existing APIs."""

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ValidationError
from pydantic_core import PydanticUndefined

from ml_pipeline_pro.errors import ErrorDetail, ErrorResponse
from ml_pipeline_pro.logging import JsonFormatter
from ml_pipeline_pro.schemas import (
    DatasetRecord,
    ExperimentComparison,
    ExperimentResult,
    ModelRecord,
    Page,
)
from ml_pipeline_pro.short_ids import is_short_id
from ml_pipeline_pro.tool_schemas import (
    CompareArguments,
    CreateExperimentArguments,
    CreateTuningArguments,
    DatasetArguments,
    EvidenceReference,
    ExperimentArguments,
    ListArguments,
    ListExperimentsArguments,
    ListTrialsArguments,
    ModelArguments,
    ToolCall,
    ToolContext,
    ToolDefinition,
    ToolFailure,
    ToolResult,
    ToolSuccess,
    TuningJobArguments,
)
from ml_pipeline_pro.tool_transport import ToolTransport, ToolTransportError
from ml_pipeline_pro.tuning_schemas import TrialResult, TuningResult


@dataclass(frozen=True)
class _ToolSpec:
    name: str
    description: str
    arguments: type[BaseModel]
    output: type[BaseModel]
    path: str
    path_key: str | None = None
    mutating: bool = False
    submission: bool = False


_SPECS = (
    _ToolSpec(
        "list_datasets",
        "List registered datasets.",
        ListArguments,
        Page[DatasetRecord],
        "/datasets",
    ),
    _ToolSpec(
        "get_dataset",
        "Inspect a registered dataset.",
        DatasetArguments,
        DatasetRecord,
        "/datasets/{dataset_id}",
        "dataset_id",
    ),
    _ToolSpec(
        "list_models", "List model definitions.", ListArguments, Page[ModelRecord], "/models"
    ),
    _ToolSpec(
        "get_model",
        "Inspect a model definition.",
        ModelArguments,
        ModelRecord,
        "/models/{model_id}",
        "model_id",
    ),
    _ToolSpec(
        "list_experiments",
        "List experiments with optional status/model filters.",
        ListExperimentsArguments,
        Page[ExperimentResult],
        "/experiments",
    ),
    _ToolSpec(
        "get_experiment",
        "Inspect experiment status, metrics, and artifact references.",
        ExperimentArguments,
        ExperimentResult,
        "/experiments/{experiment_id}",
        "experiment_id",
    ),
    _ToolSpec(
        "compare_experiments",
        "Compare completed experiments on the same dataset by validation metrics.",
        CompareArguments,
        ExperimentComparison,
        "/experiments/compare",
    ),
    _ToolSpec(
        "list_tuning_jobs", "List tuning jobs.", ListArguments, Page[TuningResult], "/tuning-jobs"
    ),
    _ToolSpec(
        "get_tuning_job",
        "Inspect tuning progress and its selected outcome.",
        TuningJobArguments,
        TuningResult,
        "/tuning-jobs/{tuning_job_id}",
        "tuning_job_id",
    ),
    _ToolSpec(
        "list_tuning_trials",
        "List saved trials for a tuning job.",
        ListTrialsArguments,
        Page[TrialResult],
        "/tuning-jobs/{tuning_job_id}/trials",
        "tuning_job_id",
    ),
    _ToolSpec(
        "create_experiment",
        "Submit training with an explicit runtime budget; queued means accepted.",
        CreateExperimentArguments,
        ExperimentResult,
        "/experiments",
        mutating=True,
        submission=True,
    ),
    _ToolSpec(
        "create_tuning_job",
        "Submit tuning with an explicit validation objective and trial/runtime budgets.",
        CreateTuningArguments,
        TuningResult,
        "/tuning-jobs",
        mutating=True,
        submission=True,
    ),
    _ToolSpec(
        "cancel_tuning_job",
        "Cancel queued tuning or request cooperative cancellation of running tuning.",
        TuningJobArguments,
        TuningResult,
        "/tuning-jobs/{tuning_job_id}/cancel",
        "tuning_job_id",
        mutating=True,
    ),
)
_BY_NAME = {spec.name: spec for spec in _SPECS}


def validated_proposal(call: ToolCall) -> ToolCall:
    """Expand a supported mutation through the existing authoritative schemas.

    Validation never dispatches or grants authorization. Missing inputs remain
    validation errors for the conversation host to explain.
    """
    spec = _BY_NAME.get(call.name)
    if spec is None or not spec.mutating:
        raise ValueError("A proposal must be a supported mutating tool")
    arguments = spec.arguments.model_validate(call.arguments)
    return ToolCall(name=spec.name, arguments=arguments.model_dump(mode="json"))


def tool_catalog() -> list[ToolDefinition]:
    """Return fresh schema/default descriptions, without credentials or context."""
    definitions = []
    for spec in _SPECS:
        defaults = {}
        for name, field in spec.arguments.model_fields.items():
            value = field.get_default(call_default_factory=True)
            if value is not PydanticUndefined:
                defaults[name] = (
                    value.model_dump(mode="json") if isinstance(value, BaseModel) else value
                )
        definitions.append(
            ToolDefinition(
                name=spec.name,
                description=spec.description,
                mutating=spec.mutating,
                parameters=spec.arguments.model_json_schema(),
                defaults=defaults,
            )
        )
    return definitions


def _safe(value: Any, context: ToolContext) -> Any:
    secrets = (context.api_key.get_secret_value(),) if context.api_key is not None else ()
    formatter = JsonFormatter(secrets)

    def redact(item: Any) -> Any:
        if isinstance(item, dict):
            return {formatter.redact(key): redact(value) for key, value in item.items()}
        if isinstance(item, list):
            return [redact(value) for value in item]
        return formatter.redact(item)

    return redact(value)


def _failure(
    context: ToolContext,
    name: str | None,
    code: str,
    message: str,
    *,
    http_status: int | None = None,
    details: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> ToolFailure:
    correlation_id = correlation_id or context.correlation_id
    return ToolFailure(
        tool_name=_safe(name, context),
        correlation_id=correlation_id,
        http_status=http_status,
        error=ErrorDetail(
            code=_safe(code, context),
            message=_safe(message, context),
            correlation_id=correlation_id,
            details=_safe(details, context),
        ),
    )


def _evidence(
    record: BaseModel, context: ToolContext, *, winner: str | None = None
) -> list[EvidenceReference]:
    if isinstance(record, Page):
        return [reference for item in record.items for reference in _evidence(item, context)]
    if isinstance(record, ExperimentComparison):
        if record.best_experiment_id not in {item.id for item in record.experiments}:
            raise ValueError("Comparison winner is absent")
        return [
            reference
            for item in record.experiments
            for reference in _evidence(item, context, winner=record.best_experiment_id)
        ]
    if record.project_id != context.project_id:
        raise ValueError("Foreign project in API response")
    kind: Literal["dataset", "model", "experiment", "tuning_job", "trial"]
    if isinstance(record, DatasetRecord):
        kind = "dataset"
    elif isinstance(record, ModelRecord):
        kind = "model"
    elif isinstance(record, ExperimentResult):
        kind = "experiment"
    elif isinstance(record, TuningResult):
        kind = "tuning_job"
    else:
        kind = "trial"
    references = [
        EvidenceReference(
            kind=kind,
            record_id=record.id,
            project_id=context.project_id,
            role="winner" if record.id == winner else "record",
        )
    ]
    if isinstance(record, TrialResult):
        references.extend(
            [
                EvidenceReference(
                    kind="tuning_job",
                    record_id=record.tuning_job_id,
                    project_id=context.project_id,
                    role="parent",
                ),
                EvidenceReference(
                    kind="experiment",
                    record_id=record.experiment_id,
                    project_id=context.project_id,
                    role="source",
                ),
            ]
        )
    if isinstance(record, TuningResult):
        for selected_kind, selected_id in (
            ("trial", record.best_trial_id),
            ("experiment", record.best_experiment_id),
        ):
            if selected_id is not None:
                references.append(
                    EvidenceReference(
                        kind=selected_kind,
                        record_id=selected_id,
                        project_id=context.project_id,
                        role="winner",
                    )
                )
    return references


def _parse_output(spec: _ToolSpec, payload: Any) -> BaseModel:
    if not isinstance(payload, dict):
        raise ValueError("Expected an API object")
    if issubclass(spec.output, Page):
        records = payload.get("items")
    elif spec.output is ExperimentComparison:
        records = payload.get("experiments")
    else:
        records = [payload]
    if not isinstance(records, list):
        raise ValueError("Expected API records")
    # Record defaults generate IDs/timestamps for inserts. They must never invent
    # evidence when parsing an incomplete response from an upstream API.
    metadata = {"id", "project_id", "schema_version", "created_at", "updated_at"}
    for record in records:
        if (
            not isinstance(record, dict)
            or not metadata.issubset(record)
            or not isinstance(record["id"], str)
            or not record["id"]
        ):
            raise ValueError("API record metadata is missing")
    return spec.output.model_validate(payload)


class ToolDispatcher:
    def __init__(self, transport: ToolTransport):
        self._transport = transport

    async def _resolve_references(self, arguments, context):
        """Resolve aliases through the same authenticated API before identity assertions."""
        values = arguments.model_dump()
        dataset = "dataset_id" in values
        kind = "datasets" if dataset else "experiments"
        field = "dataset_id" if dataset else "experiment_id"
        lookup = "get_dataset" if dataset else "get_experiment"
        identities = values.get("experiment_ids", [values.get(field)])
        resolved = []
        for identity in identities:
            if identity is None or not is_short_id(kind, identity):
                resolved.append(identity)
                continue
            response = await self._transport.request(
                "GET", f"/api/v1/{kind}/{identity}", context=context, query=[], body=None
            )
            if response.status_code >= 400:
                error = ErrorResponse.model_validate(response.payload).error
                if error.correlation_id != response.correlation_id:
                    raise ValueError("Error correlation mismatch")
                return _failure(
                    context,
                    None,
                    error.code,
                    error.message,
                    details=error.details,
                    http_status=response.status_code,
                    correlation_id=response.correlation_id,
                )
            record = _parse_output(_BY_NAME[lookup], response.payload)
            if (
                response.status_code != 200
                or record.project_id != context.project_id
                or (record.id != identity and record.short_id != identity)
            ):
                raise ValueError("Alias resolution identity mismatch")
            resolved.append(record.id)
        if "experiment_ids" in values:
            values["experiment_ids"] = resolved
        elif field in values:
            values[field] = resolved[0]
        return type(arguments).model_validate(values)

    async def mutation_preflight(self, call: ToolCall, context: ToolContext) -> ToolFailure | None:
        if call.name not in {"create_experiment", "create_tuning_job"}:
            return None
        lookup = ToolCall(name="get_model", arguments={"model_id": call.arguments["model_id"]})
        result = await self.execute(
            lookup, context.model_copy(update={"allow_mutations": False, "submission_key": None})
        )
        if isinstance(result, ToolFailure):
            return result
        if result.data["architecture"] != "mlp":
            return _failure(
                context,
                call.name,
                "unsupported_model_algorithm",
                "AI training and tuning proposals support MLP only; use manual logistic training.",
                http_status=409,
            )
        return None

    async def execute(self, call: ToolCall | dict[str, Any], context: ToolContext) -> ToolResult:
        """Execute one validated call; the host owns approval and submission keys."""
        name = None
        try:
            call = ToolCall.model_validate(call)
            spec = _BY_NAME.get(call.name)
            if spec is None:
                return _failure(context, None, "tool_not_found", "Tool name is not supported")
            name = spec.name
            arguments = spec.arguments.model_validate(call.arguments)
        except ValidationError as exc:
            fields = [
                {"location": ".".join(map(str, error["loc"])), "type": error["type"]}
                for error in exc.errors()
            ]
            return _failure(
                context,
                name,
                "tool_validation_error",
                "Tool arguments are invalid or incomplete",
                details={"fields": fields},
            )
        if spec.mutating and not context.allow_mutations:
            return _failure(
                context,
                name,
                "tool_mutation_denied",
                "The host must authorize this mutating action",
            )
        if spec.submission and context.submission_key is None:
            return _failure(
                context,
                name,
                "tool_submission_key_required",
                "The host must supply a stable submission key",
            )
        if spec.submission:
            failure = await self.mutation_preflight(call, context)
            if failure is not None:
                return failure
        if name in {"get_experiment", "compare_experiments", "get_dataset"}:
            try:
                normalized = await self._resolve_references(arguments, context)
                if isinstance(normalized, ToolFailure):
                    return normalized.model_copy(update={"tool_name": name})
                arguments = normalized
            except ToolTransportError as exc:
                return _failure(context, name, exc.code, str(exc), http_status=exc.status_code)
            except (ValidationError, ValueError, AttributeError):
                return _failure(
                    context,
                    name,
                    "tool_validation_error",
                    "References could not be resolved to distinct scoped records",
                )
        values = arguments.model_dump(mode="json", exclude_none=True)
        path = spec.path
        if spec.path_key is not None:
            path = path.format(**{spec.path_key: values.pop(spec.path_key)})
        query = []
        if not spec.mutating:
            if "experiment_ids" in values:
                query.extend(("experiment_id", value) for value in values.pop("experiment_ids"))
            query.extend((key, str(value)) for key, value in values.items())
        try:
            response = await self._transport.request(
                "POST" if spec.mutating else "GET",
                f"/api/v1{path}",
                context=context,
                query=query,
                body=values if spec.submission else None,
            )
        except ToolTransportError as exc:
            return _failure(context, name, exc.code, str(exc), http_status=exc.status_code)
        try:
            if response.status_code >= 400:
                error = ErrorResponse.model_validate(response.payload).error
                if error.correlation_id != response.correlation_id:
                    raise ValueError("Error correlation mismatch")
                return _failure(
                    context,
                    name,
                    error.code,
                    error.message,
                    details=error.details,
                    http_status=response.status_code,
                    correlation_id=response.correlation_id,
                )
            if response.status_code != (202 if spec.mutating else 200):
                raise ValueError("Unexpected success status")
            record = _parse_output(spec, response.payload)
            if (
                spec.path_key is not None
                and not isinstance(record, Page)
                and record.id != getattr(arguments, spec.path_key)
            ):
                raise ValueError("Record identity mismatch")
            if isinstance(record, Page) and (
                record.limit != arguments.limit
                or record.offset != arguments.offset
                or len(record.items) > arguments.limit
            ):
                raise ValueError("Invalid page bounds")
            if isinstance(record, ExperimentComparison) and record.metric != arguments.metric:
                raise ValueError("Comparison metric mismatch")
            if isinstance(record, ExperimentComparison) and {
                item.id for item in record.experiments
            } != set(arguments.experiment_ids):
                raise ValueError("Comparison records do not match the request")
            if (
                isinstance(record, Page)
                and name == "list_tuning_trials"
                and any(item.tuning_job_id != arguments.tuning_job_id for item in record.items)
            ):
                raise ValueError("Trial parent mismatch")
            evidence = _evidence(record, context)
            if name == "list_tuning_trials":
                evidence.append(
                    EvidenceReference(
                        kind="tuning_job",
                        record_id=arguments.tuning_job_id,
                        project_id=context.project_id,
                        role="parent",
                    )
                )
            # Deduplicate shared parents/source records without losing winner roles.
            unique = {tuple(item.model_dump().values()): item for item in evidence}
            return ToolSuccess(
                tool_name=name,
                correlation_id=response.correlation_id,
                http_status=response.status_code,
                data=_safe(record.model_dump(mode="json"), context),
                evidence=[
                    EvidenceReference.model_validate(_safe(item.model_dump(), context))
                    for item in unique.values()
                ],
            )
        except (ValidationError, ValueError, AttributeError):
            return _failure(
                context,
                name,
                "tool_invalid_response",
                "API response did not match the tool contract",
                http_status=response.status_code,
            )
