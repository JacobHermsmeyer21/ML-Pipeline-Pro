"""Authenticated preview, permanent deletion and explicit same-operation recovery."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from ml_pipeline_pro.api import Project, SubmissionKey
from ml_pipeline_pro.deletion_schemas import DeletionPreview, DeletionRequest, DeletionResult
from ml_pipeline_pro.deletions import DeletionStore
from ml_pipeline_pro.errors import ErrorResponse


def get_deletion_store(request: Request):
    database = request.app.state.connections.mongo.get_database(
        request.app.state.settings.mongodb_database
    )
    return DeletionStore(database, request.app.state.settings)


Store = Annotated[DeletionStore, Depends(get_deletion_store)]
router = APIRouter(
    prefix="/api/v1",
    tags=["deletion"],
    responses={code: {"model": ErrorResponse} for code in (403, 404, 409, 503)},
)


@router.get("/datasets/{dataset_id}/deletion-preview", response_model=DeletionPreview)
async def dataset_deletion_preview(dataset_id: str, project: Project, store: Store):
    return await store.preview(project, "datasets", dataset_id)


@router.get("/models/{model_id}/deletion-preview", response_model=DeletionPreview)
async def model_deletion_preview(model_id: str, project: Project, store: Store):
    return await store.preview(project, "models", model_id)


@router.delete("/datasets/{dataset_id}", response_model=DeletionResult)
async def delete_dataset(
    dataset_id: str,
    body: DeletionRequest,
    project: Project,
    store: Store,
    key: SubmissionKey,
):
    return await store.delete(project, "datasets", dataset_id, body, key)


@router.delete("/models/{model_id}", response_model=DeletionResult)
async def delete_model(
    model_id: str, body: DeletionRequest, project: Project, store: Store, key: SubmissionKey
):
    return await store.delete(project, "models", model_id, body, key)


@router.get("/deletions/{operation_id}", response_model=DeletionResult)
async def deletion_status(operation_id: str, project: Project, store: Store):
    return await store.get(project, operation_id)
