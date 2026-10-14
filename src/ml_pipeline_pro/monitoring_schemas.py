"""Immutable measured observations and separately labeled generated advice."""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from ml_pipeline_pro.repositories import Record
from ml_pipeline_pro.schemas import Name, RequestModel, Sha256


class ObservationCreate(RequestModel):
    sample_id: Name
    model_version_id: str = Field(min_length=1, max_length=128)
    observed_at: AwareDatetime
    latency_ms: float = Field(ge=0, le=120_000, allow_inf_nan=False)
    outcome: Literal["success", "error"] = "success"
    prediction_correct: bool | None = None
    fault: Literal["none", "seeded_latency", "inference_error"] = "none"

    @field_validator("observed_at")
    @classmethod
    def milliseconds(cls, value: datetime) -> datetime:
        value = value.astimezone(UTC)
        return value.replace(microsecond=value.microsecond // 1000 * 1000)

    @model_validator(mode="after")
    def consistent_label(self):
        if self.outcome == "error" and self.prediction_correct is not None:
            raise ValueError("Failed inference cannot have a correctness label")
        if self.fault == "inference_error" and self.outcome != "error":
            raise ValueError("Inference error requires an error outcome")
        return self

    def timely(self, now: datetime) -> bool:
        return now - timedelta(days=1) <= self.observed_at <= now + timedelta(seconds=5)


class ObservationRecord(Record, ObservationCreate):
    input_hash: Sha256


class MonitoringSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_version_id: str
    as_of: AwareDatetime
    window_seconds: int
    observation_ids: list[str]
    sample_count: int
    partial: bool
    availability: Literal["missing", "observed"]
    latest_observed_at: AwareDatetime | None
    mean_latency_ms: float | None
    max_latency_ms: float | None
    error_count: int
    labeled_count: int
    labeled_accuracy: float | None
    seeded_count: int
    latency_threshold_ms: float = 100
    issue: Literal["unknown", "latency_threshold_exceeded", "no_threshold_exceedance"]


Check = Literal["inspect_seeded_delay", "profile_inference", "check_resources", "collect_labels"]


class MonitoringAdvice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    interpretation: str = Field(min_length=1, max_length=2000)
    observation_ids: list[Annotated[str, Field(min_length=1, max_length=128)]] = Field(
        min_length=1, max_length=3
    )
    proposed_checks: list[Check] = Field(min_length=1, max_length=4)


class MonitoringStep(BaseModel):
    advice: MonitoringAdvice
    usage: dict[str, int]
    provenance: dict = Field(default_factory=dict)


class MonitoringDiagnosis(BaseModel):
    measurements: MonitoringSummary
    generated_advice: MonitoringAdvice
    review_required: Literal[True] = True
    automatic_changes: Literal[False] = False
    model_provenance: dict
