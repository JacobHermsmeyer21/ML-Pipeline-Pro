"""Versioned endpoints for dataset and model registration."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from ml_pipeline_pro.access import project_access
from ml_pipeline_pro.datasets import DatasetValidationError, load_dataset
from ml_pipeline_pro.errors import ApiError, ErrorResponse
from ml_pipeline_pro.schemas import DatasetCreate, DatasetRecord, ModelCreate, ModelRecord, Page
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


@router.post("/datasets", response_model=DatasetRecord, status_code=201, tags=["datasets"])
async def create_dataset(body: DatasetCreate, project: Project, store: Store, request: Request):
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
