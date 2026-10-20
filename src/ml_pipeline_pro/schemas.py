"""Request and persistence schemas for classification experiment tracking."""

import re
from pathlib import PurePosixPath
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from ml_pipeline_pro.repositories import Record

ProjectId = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")]
Name = Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")]
Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DatasetDefinition(RequestModel):
    name: Name
    version: Name
    uri: str = Field(min_length=1, max_length=256)
    feature_columns: list[Name] = Field(min_length=1, max_length=128)
    target_column: Name = "target"
    split_column: Name = "split"

    @field_validator("uri")
    @classmethod
    def local_csv_reference(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            not re.fullmatch(r"[a-zA-Z0-9_./-]+", value)
            or path.is_absolute()
            or ".." in path.parts
            or path.suffix != ".csv"
        ):
            raise ValueError("uri must be a relative .csv path under the configured dataset root")
        return str(path)

    @model_validator(mode="after")
    def distinct_columns(self):
        columns = [*self.feature_columns, self.target_column, self.split_column]
        if len(set(columns)) != len(columns):
            raise ValueError("Feature, target, and split columns must be distinct")
        return self


class DatasetCreate(DatasetDefinition):
    expected_sha256: Sha256 | None = None


class DatasetFileReference(RequestModel):
    uri: str = Field(min_length=1, max_length=256)
    sha256: Sha256
    size_bytes: int = Field(ge=1)


class PreparationReference(RequestModel):
    source: DatasetFileReference
    manifest: DatasetFileReference
    recipe_sha256: Sha256


class DatasetSelection(RequestModel):
    parent_id: str = Field(min_length=1, max_length=128)
    parent_sha256: Sha256
    parent_manifest_sha256: Sha256 | None = None
    drop_columns: list[Annotated[str, Field(min_length=1, max_length=128)]] = Field(
        min_length=1, max_length=128
    )
    request_sha256: Sha256
    reviewed_sha256: Sha256


class DatasetRecord(Record, DatasetDefinition):
    sha256: Sha256
    num_classes: int = Field(ge=2, le=64)
    row_counts: dict[Literal["train", "validation", "test"], int]
    preparation: PreparationReference | None = None
    selection: DatasetSelection | None = None


class ModelCreate(RequestModel):
    name: Name
    framework: Literal["pytorch"] = "pytorch"
    task: Literal["classification"] = "classification"
    architecture: Literal["mlp", "logistic_regression"] = "mlp"


class ModelRecord(Record, ModelCreate):
    pass


class TrainingConfig(RequestModel):
    seed: int = Field(default=42, ge=0, le=2**32 - 1)
    epochs: int = Field(default=30, ge=1, le=500)
    batch_size: int = Field(default=16, ge=1, le=4096)
    learning_rate: float = Field(default=0.01, gt=0, le=1, allow_inf_nan=False)
    hidden_units: int = Field(default=16, ge=1, le=512)
    max_runtime_seconds: int = Field(default=60, ge=1, le=600)


class LogisticRegressionConfig(RequestModel):
    algorithm: Literal["logistic_regression"]
    seed: int = Field(default=42, ge=0, le=2**32 - 1)
    epochs: int = Field(default=30, ge=1, le=500)
    batch_size: int = Field(default=16, ge=1, le=4096)
    learning_rate: float = Field(default=0.01, gt=0, le=1, allow_inf_nan=False)
    max_runtime_seconds: int = Field(default=60, ge=1, le=600)
    l2_strength: float = Field(default=0.0, ge=0, le=1, allow_inf_nan=False)


def config_algorithm(config: TrainingConfig | LogisticRegressionConfig) -> str:
    return "logistic_regression" if isinstance(config, LogisticRegressionConfig) else "mlp"


class ExperimentCreate(RequestModel):
    dataset_id: str = Field(min_length=1, max_length=128)
    model_id: str = Field(min_length=1, max_length=128)
    config: TrainingConfig | LogisticRegressionConfig = Field(default_factory=TrainingConfig)


class ArtifactReference(RequestModel):
    name: Literal["model.pt", "manifest.json"]
    uri: str
    sha256: Sha256
    size_bytes: int = Field(ge=1)


ExperimentStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]


class ExperimentResult(Record, ExperimentCreate):
    status: ExperimentStatus = "queued"
    attempts: int = 0
    heartbeat_at: AwareDatetime | None = None
    started_at: AwareDatetime | None = None
    completed_at: AwareDatetime | None = None
    metrics: dict[str, Annotated[float, Field(allow_inf_nan=False)]] = Field(default_factory=dict)
    artifacts: list[ArtifactReference] = Field(default_factory=list)
    dependencies: dict[str, str] = Field(default_factory=dict)
    error_summary: str | None = None
    tuning_job_id: str | None = None
    tuning_trial_number: int | None = None
    test_evaluated: bool = False

    @model_validator(mode="after")
    def infer_existing_test_evaluation(self):
        if {"test_accuracy", "test_f1"}.issubset(self.metrics):
            self.test_evaluated = True
        return self


class ExperimentRecord(ExperimentResult):
    submission_key: str
    request_hash: Sha256
    worker_token: str | None = None
    lease_expires_at: AwareDatetime | None = None
    last_dispatch_at: AwareDatetime | None = None
    evaluate_test: bool = True
    selection_metric: Literal["validation_f1", "validation_accuracy"] = "validation_f1"


class ModelVersionCreate(RequestModel):
    version: Name
    experiment_id: str = Field(min_length=1, max_length=128)


class ModelVersionRecord(Record):
    model_id: str
    version: Name
    experiment_id: str
    artifact: ArtifactReference
    dependencies: dict[str, str]


class ExperimentComparison(BaseModel):
    metric: Literal["validation_f1", "validation_accuracy"]
    direction: Literal["maximize"] = "maximize"
    best_experiment_id: str
    experiments: list[ExperimentResult]


ItemT = TypeVar("ItemT", bound=BaseModel)


class Page(BaseModel, Generic[ItemT]):
    items: list[ItemT]
    limit: int
    offset: int
