"""Review and save a column subset as a separate, immutable dataset version."""

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Response
from pymongo.errors import DuplicateKeyError

from ml_pipeline_pro.api import Project, Store
from ml_pipeline_pro.column_schemas import ColumnEdit, ColumnPreview, ColumnSave, DatasetColumns
from ml_pipeline_pro.dataset_columns import project_columns, request_digest, snapshot
from ml_pipeline_pro.dataset_files import upload_directory
from ml_pipeline_pro.dataset_uploads import _file_io, _matching_record, upload_access
from ml_pipeline_pro.datasets import DatasetValidationError, load_dataset
from ml_pipeline_pro.errors import ApiError, ErrorResponse
from ml_pipeline_pro.preparation_api import _publish
from ml_pipeline_pro.preparation_files import read_preparation
from ml_pipeline_pro.schemas import DatasetRecord, DatasetSelection, PreparationReference
from ml_pipeline_pro.storage_control import dataset_registration

router = APIRouter(
    prefix="/api/v1/datasets",
    tags=["datasets"],
    dependencies=[Depends(upload_access)],
    responses={code: {"model": ErrorResponse} for code in (403, 404, 408, 409, 422, 503)},
)


async def parent_record(store, project, identity):
    record = await store.datasets.get(project, identity)
    if record is None:
        raise ApiError(404, "dataset_not_found", "Dataset was not found")
    return record


@router.get("/{dataset_id}/columns", response_model=DatasetColumns)
async def dataset_columns(dataset_id: str, request: Request, project: Project, store: Store):
    parent = await parent_record(store, project, dataset_id)
    return (await _file_io(snapshot, parent, request.app.state.settings))[2]


@router.post("/{dataset_id}/columns/preview", response_model=ColumnPreview)
async def preview_columns(
    dataset_id: str,
    body: ColumnEdit,
    request: Request,
    project: Project,
    store: Store,
):
    parent = await parent_record(store, project, dataset_id)
    try:
        return (await _file_io(project_columns, parent, body, request.app.state.settings)).preview
    except TimeoutError:
        raise ApiError(
            408, "preparation_timeout", "Column preview exceeded its time budget"
        ) from None


async def matching_selection(store, project, dataset_id, body, settings):
    dataset_id = await store.datasets.resolve(project, dataset_id)
    saved = await store.datasets.by_selection(project, dataset_id, body.version)
    if saved is None:
        return None
    expected = request_digest(
        project, dataset_id, ColumnEdit.model_validate(body.model_dump(exclude={"reviewed_sha256"}))
    )
    if (
        saved.selection.request_sha256 != expected
        or saved.selection.reviewed_sha256 != body.reviewed_sha256
    ):
        raise ApiError(
            409, "dataset_identity_conflict", "Dataset version already has other content"
        )
    await _matching_record(store, saved, settings)
    try:
        await _file_io(read_preparation, saved, settings)
    except DatasetValidationError:
        raise ApiError(409, "dataset_file_conflict", "Saved preparation is unavailable") from None
    return saved


@router.post("/{dataset_id}/columns", response_model=DatasetRecord, status_code=201)
@dataset_registration
async def save_columns(
    dataset_id: str,
    body: ColumnSave,
    request: Request,
    project: Project,
    store: Store,
    response: Response,
):
    settings = request.app.state.settings
    saved = await matching_selection(store, project, dataset_id, body, settings)
    if saved is not None:
        response.status_code = 200
        return saved
    parent = await parent_record(store, project, dataset_id)
    edit = ColumnEdit.model_validate(body.model_dump(exclude={"reviewed_sha256"}))
    try:
        result = await _file_io(project_columns, parent, edit, settings)
        if body.reviewed_sha256 != result.preview.preview_sha256:
            raise ApiError(409, "column_review_required", "Refresh and review this exact selection")
        directory = await _file_io(upload_directory, project, settings)
        canonical = await _file_io(_publish, result.content, directory)
        preparation = None
        if result.manifest is not None:
            manifest = await _file_io(_publish, result.manifest, directory, ".preparation.json")
            recipe = json.loads(result.manifest)
            preparation = PreparationReference(
                source=parent.preparation.source,
                manifest=manifest,
                recipe_sha256=recipe["recipe_sha256"],
            )
        now = datetime.now(UTC)
        now = now.replace(microsecond=now.microsecond // 1000 * 1000)
        candidate = DatasetRecord(
            project_id=project,
            name=parent.name,
            version=body.version,
            uri=canonical.uri,
            sha256=canonical.sha256,
            feature_columns=result.preview.feature_columns,
            target_column=parent.target_column,
            split_column=parent.split_column,
            num_classes=parent.num_classes,
            row_counts=parent.row_counts,
            preparation=preparation,
            selection=DatasetSelection(**result.lineage, reviewed_sha256=body.reviewed_sha256),
            created_at=now,
            updated_at=now,
        )
        await _file_io(load_dataset, candidate, settings)
        await _file_io(read_preparation, candidate, settings)
        try:
            return await store.datasets.admit(candidate, (("datasets", parent.id),))
        except DuplicateKeyError:
            saved = await matching_selection(store, project, dataset_id, body, settings)
            if saved is None:
                raise ApiError(
                    409, "dataset_identity_conflict", "Choose an unused dataset version"
                ) from None
            response.status_code = 200
            return saved
    except TimeoutError:
        raise ApiError(
            408, "preparation_timeout", "Column selection exceeded its time budget"
        ) from None
    except DatasetValidationError:
        raise ApiError(
            409, "dataset_file_conflict", "Selected dataset verification failed"
        ) from None
    except OSError:
        raise ApiError(
            503, "dataset_storage_unavailable", "Dataset storage is unavailable"
        ) from None
