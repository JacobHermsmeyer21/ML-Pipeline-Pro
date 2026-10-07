"""Bounded TPE search contracts and durable tuning job/trial records."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, model_validator

from ml_pipeline_pro.repositories import Record
from ml_pipeline_pro.schemas import ExperimentCreate, RequestModel, Sha256, TrainingConfig

FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]


class LearningRateRange(RequestModel):
    low: float = Field(default=0.0001, gt=0, le=1, allow_inf_nan=False)
    high: float = Field(default=0.05, gt=0, le=1, allow_inf_nan=False)
    log: bool = True

    @model_validator(mode="after")
    def ordered_bounds(self):
        if self.low > self.high:
            raise ValueError("Learning rate low must not exceed high")
        return self


class BatchSizeChoices(RequestModel):
    choices: list[Annotated[int, Field(strict=True, ge=1, le=4096)]] = Field(
        default_factory=lambda: [8, 16, 32], min_length=1, max_length=20
    )

    @model_validator(mode="after")
    def distinct_choices(self):
        if len(set(self.choices)) != len(self.choices):
            raise ValueError("Batch size choices must be distinct")
        return self


class HiddenUnitsRange(RequestModel):
    low: int = Field(default=8, strict=True, ge=1, le=512)
    high: int = Field(default=64, strict=True, ge=1, le=512)
    step: int = Field(default=8, strict=True, ge=1, le=512)

    @model_validator(mode="after")
    def ordered_step_bounds(self):
        if self.low > self.high or (self.high - self.low) % self.step:
            raise ValueError(
                "Hidden unit bounds must be ordered and their difference divisible by step"
            )
        return self


class SearchSpace(RequestModel):
    learning_rate: LearningRateRange = Field(default_factory=LearningRateRange)
    batch_size: BatchSizeChoices = Field(default_factory=BatchSizeChoices)
    hidden_units: HiddenUnitsRange = Field(default_factory=HiddenUnitsRange)


class TuningLimits(RequestModel):
    max_trials: int = Field(default=5, strict=True, ge=1, le=50)
    max_runtime_seconds: int = Field(default=300, strict=True, ge=2, le=600)
    concurrency: Literal[1] = 1


class TuningCreate(ExperimentCreate):
    objective_metric: Literal["validation_f1", "validation_accuracy"] = "validation_f1"
    direction: Literal["maximize"] = "maximize"
    sampler_seed: int = Field(default=42, strict=True, ge=0, le=2**32 - 1)
    search_space: SearchSpace = Field(default_factory=SearchSpace)
    limits: TuningLimits = Field(default_factory=TuningLimits)


TuningStatus = Literal["queued", "running", "succeeded", "failed", "cancel_requested", "cancelled"]
TrialStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]


class TrialReservation(RequestModel):
    number: int = Field(ge=0)
    trial_id: str
    experiment_id: str
    parameters: dict[str, int | float]
    config: TrainingConfig


class TuningResult(Record, TuningCreate):
    status: TuningStatus = "queued"
    phase: Literal["searching", "evaluating", "complete"] = "searching"
    attempts: int = 0
    scheduled_trials: int = 0
    completed_trials: int = 0
    failed_trials: int = 0
    heartbeat_at: AwareDatetime | None = None
    started_at: AwareDatetime | None = None
    completed_at: AwareDatetime | None = None
    deadline_at: AwareDatetime | None = None
    search_deadline_at: AwareDatetime | None = None
    best_trial_id: str | None = None
    best_experiment_id: str | None = None
    best_config: TrainingConfig | None = None
    best_value: FiniteFloat | None = None
    sampler_version: str | None = None
    final_evaluation: Literal["pending", "succeeded", "skipped_budget", "not_applicable"] = (
        "not_applicable"
    )
    stop_reason: str | None = None
    error_summary: str | None = None


class TuningRecord(TuningResult):
    submission_key: str
    request_hash: Sha256
    worker_token: str | None = None
    lease_expires_at: AwareDatetime | None = None
    last_dispatch_at: AwareDatetime | None = None
    reservation: TrialReservation | None = None
    ownership_revision: int = 0


class TrialResult(Record):
    tuning_job_id: str
    number: int = Field(ge=0)
    experiment_id: str
    parameters: dict[str, int | float]
    config: TrainingConfig
    status: TrialStatus = "queued"
    objective_value: FiniteFloat | None = None
    metrics: dict[str, FiniteFloat] = Field(default_factory=dict)
    duration_seconds: float = Field(default=0, ge=0, allow_inf_nan=False)
    started_at: AwareDatetime | None = None
    completed_at: AwareDatetime | None = None
    error_summary: str | None = None


class TrialRecord(TrialResult):
    worker_token: str | None = None
