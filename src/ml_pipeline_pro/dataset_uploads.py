"""Bounded, project-scoped CSV ingestion using the existing dataset record contract."""

import asyncio
import os
import tempfile
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError
from starlette.requests import ClientDisconnect

from ml_pipeline_pro.api import Project, Store
from ml_pipeline_pro.dataset_files import (
    UPLOAD_MAX_BYTES,
    UPLOAD_RECEIVE_SECONDS,
    check_dataset_scope,
    publish_dataset,
    upload_directory,
)
from ml_pipeline_pro.datasets import DatasetValidationError, load_dataset
from ml_pipeline_pro.errors import ApiError, ErrorResponse
from ml_pipeline_pro.schemas import DatasetCreate, DatasetRecord, Name
from ml_pipeline_pro.storage_control import dataset_registration


def upload_access(request: Request, project: Project):
    if not request.app.state.settings.dataset_upload_enabled:
        raise ApiError(404, "not_found", "Dataset uploads are not enabled")
    return project


router = APIRouter(
    prefix="/api/v1/datasets",
    tags=["datasets"],
    dependencies=[Depends(upload_access)],
    responses={
        code: {"model": ErrorResponse} for code in (400, 403, 404, 408, 409, 413, 415, 422, 503)
    },
)


async def _file_io(function, *args, **kwargs):
    """Finish an in-flight filesystem operation before cancellation cleans up its staging file."""
    task = asyncio.create_task(asyncio.to_thread(partial(function, *args, **kwargs)))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError as cancelled:
        # Further cancellations must not cancel the owned task while its thread
        # can still access the staging file. Always retrieve its result/exception.
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        try:
            task.result()
        except Exception:
            pass
        raise cancelled


async def _receive(request: Request, destination, limit: int) -> int:
    received = 0
    try:
        async with asyncio.timeout(UPLOAD_RECEIVE_SECONDS):
            async for chunk in request.stream():
                if len(chunk) > limit - received:
                    raise ApiError(
                        413, "dataset_too_large", "Dataset exceeds the upload byte limit"
                    )
                if chunk:
                    await _file_io(destination.write, chunk)
                    received += len(chunk)
    except TimeoutError:
        raise ApiError(408, "upload_timeout", "Dataset upload did not complete in time") from None
    except ClientDisconnect:
        raise ApiError(400, "upload_interrupted", "Dataset upload did not complete") from None
    return received


async def _matching_record(store, candidate: DatasetRecord, settings):
    saved = await store.datasets.by_identity(
        candidate.project_id, candidate.name, candidate.version
    )
    if saved is None:
        return None
    fields = {
        "project_id",
        "name",
        "version",
        "feature_columns",
        "target_column",
        "split_column",
        "sha256",
        "num_classes",
        "row_counts",
        "preparation",
    }
    if saved.model_dump(include=fields) != candidate.model_dump(include=fields):
        raise ApiError(
            409, "dataset_identity_conflict", "Dataset version already has other content"
        )
    # A prior ordinary registration may reference the same bytes at a different URI.
    check_dataset_scope(saved.uri, saved.project_id, settings)
    try:
        existing = await _file_io(load_dataset, saved, settings)
    except DatasetValidationError:
        raise ApiError(
            409, "dataset_file_conflict", "Saved dataset content is unavailable"
        ) from None
    if existing.sha256 != saved.sha256:
        raise ApiError(409, "dataset_file_conflict", "Saved dataset content does not match")
    return saved


@router.post("/upload", response_model=DatasetRecord, status_code=201)
@dataset_registration
async def upload_dataset(
    request: Request,
    response: Response,
    project: Project,
    store: Store,
    name: Name,
    version: Name,
    feature_columns: Annotated[list[Name], Query(min_length=1, max_length=128)],
    target_column: Name = "target",
    split_column: Name = "split",
):
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "text/csv":
        raise ApiError(415, "unsupported_media_type", "Upload a UTF-8 CSV using text/csv")
    settings = request.app.state.settings
    staged = None
    try:
        directory = await _file_io(upload_directory, project, settings)
        # Acquire the descriptor/name together, without a cancellation point that could
        # lose ownership of a just-created temporary file.
        descriptor, filename = tempfile.mkstemp(prefix="staging_", suffix=".csv", dir=directory)
        staged = Path(filename)
        with os.fdopen(descriptor, "wb") as destination:
            size = await _receive(
                request, destination, min(settings.dataset_max_bytes, UPLOAD_MAX_BYTES)
            )
        try:
            definition = DatasetCreate(
                name=name,
                version=version,
                uri=f"uploads/{project}/{staged.name}",
                feature_columns=feature_columns,
                target_column=target_column,
                split_column=split_column,
            )
            loaded = await _file_io(load_dataset, definition, settings)
        except ValidationError:
            raise ApiError(422, "invalid_dataset", "Dataset columns must be distinct") from None
        except DatasetValidationError as exc:
            raise ApiError(422, "invalid_dataset", str(exc)) from None
        uri = await _file_io(publish_dataset, staged, directory, loaded.sha256, size)
        now = datetime.now(UTC)
        now = now.replace(microsecond=now.microsecond // 1000 * 1000)
        candidate = DatasetRecord(
            **definition.model_dump(exclude={"uri", "expected_sha256"}),
            uri=uri,
            project_id=project,
            sha256=loaded.sha256,
            num_classes=loaded.num_classes,
            row_counts=loaded.row_counts,
            created_at=now,
            updated_at=now,
        )
        saved = await _matching_record(store, candidate, settings)
        if saved is not None:
            response.status_code = 200
            return saved
        try:
            return await store.datasets.insert(candidate)
        except DuplicateKeyError:
            saved = await _matching_record(store, candidate, settings)
            if saved is None:
                raise
            response.status_code = 200
            return saved
    except OSError:
        raise ApiError(
            503, "dataset_storage_unavailable", "Dataset file storage is unavailable"
        ) from None
    finally:
        if staged is not None:
            # Published files can already be referenced by a committed-but-unacknowledged insert.
            # Only this request's temporary name is eligible for cleanup.
            staged.unlink(missing_ok=True)
