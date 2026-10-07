"""Provider-independent tool arguments, trusted context, and public results."""

from typing import Annotated, Any, Literal
from uuid import uuid4

from pydantic import ConfigDict, Field, SecretStr, field_validator, model_validator

from ml_pipeline_pro.errors import ErrorDetail
from ml_pipeline_pro.schemas import (
    ExperimentCreate,
    ExperimentStatus,
    ProjectId,
    RequestModel,
    TrainingConfig,
)
from ml_pipeline_pro.tuning_schemas import TuningCreate, TuningLimits

ResourceId = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")]
CorrelationId = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")]
SubmissionKey = ResourceId


class ToolContext(RequestModel):
    """Created by the host application, never from provider tool arguments."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    project_id: ProjectId
    api_key: SecretStr | None = Field(default=None, exclude=True, repr=False)
    correlation_id: CorrelationId = Field(default_factory=lambda: str(uuid4()))
    allow_mutations: bool = Field(default=False, strict=True)
    submission_key: SubmissionKey | None = Field(default=None, exclude=True, repr=False)

    @field_validator("api_key")
    @classmethod
    def printable_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and (
            not value.get_secret_value()
            or any(not 33 <= ord(char) <= 126 for char in value.get_secret_value())
        ):
            raise ValueError("API key must contain printable non-space ASCII characters")
        return value


class ToolCall(RequestModel):
    name: str = Field(min_length=1, max_length=80)
    arguments: dict[str, Any] = Field(default_factory=dict)


class ListArguments(RequestModel):
    limit: int = Field(default=50, strict=True, ge=1, le=100)
    offset: int = Field(default=0, strict=True, ge=0)


class DatasetArguments(RequestModel):
    dataset_id: ResourceId


class ModelArguments(RequestModel):
    model_id: ResourceId


class ExperimentArguments(RequestModel):
    experiment_id: ResourceId


class ListExperimentsArguments(ListArguments):
    status: ExperimentStatus | None = None
    model_id: ResourceId | None = None


class CompareArguments(RequestModel):
    experiment_ids: list[ResourceId] = Field(min_length=2, max_length=20)
    metric: Literal["validation_f1", "validation_accuracy"] = "validation_f1"

    @model_validator(mode="after")
    def distinct_ids(self):
        if len(set(self.experiment_ids)) != len(self.experiment_ids):
            raise ValueError("Comparison requires distinct experiment IDs")
        return self


class TuningJobArguments(RequestModel):
    tuning_job_id: ResourceId


class ListTrialsArguments(TuningJobArguments, ListArguments):
    pass


class ToolTrainingConfig(TrainingConfig):
    max_runtime_seconds: int = Field(ge=1, le=600)


class ToolTuningLimits(TuningLimits):
    max_trials: int = Field(strict=True, ge=1, le=50)
    max_runtime_seconds: int = Field(strict=True, ge=2, le=600)


class CreateExperimentArguments(ExperimentCreate):
    dataset_id: ResourceId
    model_id: ResourceId
    config: ToolTrainingConfig = Field()


class CreateTuningArguments(TuningCreate):
    dataset_id: ResourceId
    model_id: ResourceId
    config: ToolTrainingConfig = Field()
    objective_metric: Literal["validation_f1", "validation_accuracy"] = Field()
    limits: ToolTuningLimits = Field()


class ToolDefinition(RequestModel):
    name: str
    description: str
    mutating: bool
    parameters: dict[str, Any]
    defaults: dict[str, Any]


class EvidenceReference(RequestModel):
    kind: Literal["dataset", "model", "experiment", "tuning_job", "trial"]
    record_id: str
    project_id: str
    role: Literal["record", "winner", "parent", "source"] = "record"


class ToolSuccess(RequestModel):
    status: Literal["succeeded"] = "succeeded"
    tool_name: str
    correlation_id: str
    http_status: int
    data: dict[str, Any]
    evidence: list[EvidenceReference]


class ToolFailure(RequestModel):
    status: Literal["error"] = "error"
    tool_name: str | None = None
    correlation_id: str
    http_status: int | None = None
    error: ErrorDetail


ToolResult = Annotated[ToolSuccess | ToolFailure, Field(discriminator="status")]
