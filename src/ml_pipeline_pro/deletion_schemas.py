"""Public permanent-erasure preview, request and durable operation status."""

from typing import Literal

from pydantic import AwareDatetime

from ml_pipeline_pro.schemas import RequestModel, Sha256


class DeletionCounts(RequestModel):
    datasets: int = 0
    models: int = 0
    experiments: int = 0
    tuning_jobs: int = 0
    trials: int = 0
    model_versions: int = 0
    monitoring_observations: int = 0
    files: int = 0
    size_bytes: int = 0
    shared_files: int = 0
    unmanaged_files: int = 0


class DeletionPreview(RequestModel):
    kind: Literal["datasets", "models"]
    record_id: str
    name: str
    version: str | None = None
    preview_sha256: Sha256
    counts: DeletionCounts
    active_jobs: int


class DeletionRequest(RequestModel):
    preview_sha256: Sha256


class DeletionResult(RequestModel):
    operation_id: str
    kind: Literal["datasets", "models"]
    record_id: str
    status: Literal["preparing", "cleaning", "complete"]
    counts: DeletionCounts
    created_at: AwareDatetime
    completed_at: AwareDatetime | None = None
