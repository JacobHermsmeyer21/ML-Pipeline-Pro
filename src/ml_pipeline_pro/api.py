"""Versioned endpoints for dataset and model registration."""

import asyncio
import hashlib
import json
import math
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import Response
from kombu.exceptions import OperationalError
from pymongo.errors import DuplicateKeyError
from redis.exceptions import RedisError

from ml_pipeline_pro.access import project_access
from ml_pipeline_pro.artifacts import ArtifactError, read_artifact
from ml_pipeline_pro.dataset_files import check_dataset_scope
from ml_pipeline_pro.datasets import DatasetValidationError, load_dataset
from ml_pipeline_pro.errors import ApiError, ErrorResponse
from ml_pipeline_pro.queue import Publisher, get_publisher
from ml_pipeline_pro.schemas import (
    DatasetCreate,
    DatasetRecord,
    ExperimentComparison,
    ExperimentCreate,
    ExperimentRecord,
    ExperimentResult,
    ExperimentStatus,
    ModelCreate,
    ModelRecord,
    ModelVersionCreate,
    ModelVersionRecord,
    Page,
)
from ml_pipeline_pro.storage_control import dataset_registration
from ml_pipeline_pro.tracking import TrackingStore, get_store

router = APIRouter(
    prefix="/api/v1",
    dependencies=[Depends(project_access)],
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
Project = Annotated[str, Depends(project_access)]
Store = Annotated[TrackingStore, Depends(get_store)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]
Dispatch = Annotated[Publisher, Depends(get_publisher)]
SubmissionKey = Annotated[
    str, Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")
]


@router.post("/datasets", response_model=DatasetRecord, status_code=201, tags=["datasets"])
@dataset_registration
async def create_dataset(body: DatasetCreate, project: Project, store: Store, request: Request):
    check_dataset_scope(body.uri, project, request.app.state.settings)
    try:
        loaded = await asyncio.to_thread(load_dataset, body, request.app.state.settings)
    except DatasetValidationError as exc:
        raise ApiError(422, "invalid_dataset", str(exc)) from None
    if body.expected_sha256 is not None and loaded.sha256 != body.expected_sha256:
        raise ApiError(
            409, "dataset_hash_mismatch", "Dataset content does not match the expected hash"
        )
    record = DatasetRecord(
        **body.model_dump(exclude={"expected_sha256"}),
        project_id=project,
        sha256=loaded.sha256,
        num_classes=loaded.num_classes,
        row_counts=loaded.row_counts,
    )
    return await store.datasets.insert(record)


@router.get("/datasets", response_model=Page[DatasetRecord], tags=["datasets"])
async def list_datasets(project: Project, store: Store, limit: Limit = 50, offset: Offset = 0):
    return Page(
        items=await store.datasets.list(project, limit=limit, offset=offset),
        limit=limit,
        offset=offset,
    )


@router.get("/datasets/{dataset_id}", response_model=DatasetRecord, tags=["datasets"])
async def get_dataset(dataset_id: str, project: Project, store: Store):
    record = await store.datasets.get(project, dataset_id)
    if record is None:
        raise ApiError(404, "dataset_not_found", "Dataset was not found in this project")
    return record


@router.post("/models", response_model=ModelRecord, status_code=201, tags=["models"])
async def create_model(body: ModelCreate, project: Project, store: Store):
    return await store.models.insert(ModelRecord(**body.model_dump(), project_id=project))


@router.get("/models", response_model=Page[ModelRecord], tags=["models"])
async def list_models(project: Project, store: Store, limit: Limit = 50, offset: Offset = 0):
    return Page(
        items=await store.models.list(project, limit=limit, offset=offset),
        limit=limit,
        offset=offset,
    )


@router.get("/models/{model_id}", response_model=ModelRecord, tags=["models"])
async def get_model(model_id: str, project: Project, store: Store):
    record = await store.models.get(project, model_id)
    if record is None:
        raise ApiError(404, "model_not_found", "Model was not found in this project")
    return record


@router.post("/experiments", response_model=ExperimentResult, status_code=202, tags=["experiments"])
async def create_experiment(
    body: ExperimentCreate, project: Project, store: Store, dispatch: Dispatch, key: SubmissionKey
):
    fingerprint = hashlib.sha256(json.dumps(body.model_dump(), sort_keys=True).encode()).hexdigest()
    existing = await store.experiments.by_submission(project, key)
    if existing is None:
        await store.lifecycle.check_submission(project, "experiments", key, fingerprint)
        if await store.datasets.get(project, body.dataset_id) is None:
            raise ApiError(404, "dataset_not_found", "Dataset was not found in this project")
        model = await store.models.get(project, body.model_id)
        if model is None:
            raise ApiError(404, "model_not_found", "Model was not found in this project")
        from ml_pipeline_pro.schemas import config_algorithm

        if model.architecture != config_algorithm(body.config):
            raise ApiError(409, "model_config_mismatch", "Config algorithm must match the model")
        record = ExperimentRecord(
            **body.model_dump(), project_id=project, submission_key=key, request_hash=fingerprint
        )
        try:
            existing = await store.experiments.admit(
                record, [("datasets", body.dataset_id), ("models", body.model_id)]
            )
        except DuplicateKeyError:
            existing = await store.experiments.by_submission(project, key)
            if existing is None:
                raise
    if existing.request_hash != fingerprint:
        raise ApiError(
            409,
            "idempotency_conflict",
            "This submission key already belongs to a different request",
        )
    await store.lifecycle.check_read(project, "experiments", existing.id)
    if existing.status == "queued":
        try:
            await asyncio.to_thread(dispatch.publish, project, existing.id)
        except (OperationalError, RedisError, OSError):
            raise ApiError(
                503,
                "queue_unavailable",
                "Training queue is unavailable; retry with the same submission key",
                {"experiment_id": existing.id},
            ) from None
        await store.experiments.mark_dispatched(project, existing.id)
    return existing


@router.get("/experiments", response_model=Page[ExperimentResult], tags=["experiments"])
async def list_experiments(
    project: Project,
    store: Store,
    limit: Limit = 50,
    offset: Offset = 0,
    status: ExperimentStatus | None = None,
    model_id: str | None = None,
):
    items = await store.experiments.filtered_list(
        project, limit=limit, offset=offset, status=status, model_id=model_id
    )
    return Page[ExperimentResult](items=items, limit=limit, offset=offset)


@router.get("/experiments/compare", response_model=ExperimentComparison, tags=["experiments"])
async def compare_experiments(
    project: Project,
    store: Store,
    ids: Annotated[list[str], Query(alias="experiment_id", min_length=2, max_length=20)],
    metric: Annotated[str, Query(pattern=r"^validation_(f1|accuracy)$")] = "validation_f1",
):
    if len(set(ids)) != len(ids):
        raise ApiError(422, "invalid_comparison", "Comparison requires distinct experiment IDs")
    records = []
    for experiment_id in ids:
        record = await store.experiments.get(project, experiment_id)
        if record is None:
            raise ApiError(404, "experiment_not_found", "Experiment was not found in this project")
        if (
            record.status != "succeeded"
            or metric not in record.metrics
            or not math.isfinite(record.metrics[metric])
        ):
            raise ApiError(
                409,
                "experiment_not_comparable",
                "All experiments must have succeeded with the requested metric",
            )
        records.append(record)
    if len({record.dataset_id for record in records}) != 1:
        raise ApiError(
            409, "dataset_mismatch", "Compare experiments using the same dataset version"
        )
    records.sort(key=lambda record: (-record.metrics[metric], record.created_at, record.id))
    return ExperimentComparison(
        metric=metric, best_experiment_id=records[0].id, experiments=records
    )


@router.get("/experiments/{experiment_id}", response_model=ExperimentResult, tags=["experiments"])
async def get_experiment(experiment_id: str, project: Project, store: Store):
    record = await store.experiments.get(project, experiment_id)
    if record is None:
        raise ApiError(404, "experiment_not_found", "Experiment was not found in this project")
    return record


@router.get("/experiments/{experiment_id}/artifacts/{name}", tags=["experiments"])
async def download_artifact(
    experiment_id: str, name: str, project: Project, store: Store, request: Request
):
    experiment = await get_experiment(experiment_id, project, store)
    artifact = next((item for item in experiment.artifacts if item.name == name), None)
    if experiment.status != "succeeded" or artifact is None:
        raise ApiError(404, "artifact_not_found", "A completed artifact was not found")
    try:
        content = await asyncio.to_thread(
            read_artifact, artifact, project, experiment.id, request.app.state.settings
        )
    except ArtifactError as exc:
        raise ApiError(409, "artifact_invalid", str(exc)) from None
    return Response(
        content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{artifact.name}"'},
    )


@router.get("/models/{model_id}/versions", response_model=Page[ModelVersionRecord], tags=["models"])
async def list_model_versions(
    model_id: str, project: Project, store: Store, limit: Limit = 50, offset: Offset = 0
):
    if await store.models.get(project, model_id) is None:
        raise ApiError(404, "model_not_found", "Model was not found in this project")
    return Page(
        items=await store.versions.for_model(project, model_id, limit=limit, offset=offset),
        limit=limit,
        offset=offset,
    )


@router.get(
    "/models/{model_id}/versions/{version_id}", response_model=ModelVersionRecord, tags=["models"]
)
async def get_model_version(model_id: str, version_id: str, project: Project, store: Store):
    record = await store.versions.get(project, version_id)
    if record is None or record.model_id != model_id:
        raise ApiError(404, "version_not_found", "Model version was not found in this project")
    return record


@router.post(
    "/models/{model_id}/versions",
    response_model=ModelVersionRecord,
    status_code=201,
    tags=["models"],
)
async def create_model_version(
    model_id: str, body: ModelVersionCreate, project: Project, store: Store, request: Request
):
    if await store.models.get(project, model_id) is None:
        raise ApiError(404, "model_not_found", "Model was not found in this project")
    experiment = await get_experiment(body.experiment_id, project, store)
    if experiment.model_id != model_id:
        raise ApiError(409, "model_mismatch", "Experiment belongs to a different model")
    if experiment.status != "succeeded":
        raise ApiError(
            409, "experiment_incomplete", "Model versions require a succeeded experiment"
        )
    if not experiment.test_evaluated:
        raise ApiError(
            409,
            "test_evaluation_required",
            "Model versions require final test evaluation after selection",
        )
    artifact = next((item for item in experiment.artifacts if item.name == "model.pt"), None)
    if artifact is None:
        raise ApiError(409, "artifact_not_found", "Experiment has no checkpoint")
    try:
        await asyncio.to_thread(
            read_artifact, artifact, project, experiment.id, request.app.state.settings
        )
    except ArtifactError as exc:
        raise ApiError(409, "artifact_invalid", str(exc)) from None
    return await store.versions.admit(
        ModelVersionRecord(
            project_id=project,
            model_id=model_id,
            version=body.version,
            experiment_id=experiment.id,
            artifact=artifact,
            dependencies=experiment.dependencies,
        ),
        [("models", model_id), ("experiments", experiment.id)],
    )
