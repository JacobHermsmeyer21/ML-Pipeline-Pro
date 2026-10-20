"""Bounded multipart preview and immutable preparation of raw classification CSVs."""

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from fastapi import APIRouter, Depends, Request, Response
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError
from python_multipart import MultipartParser
from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import parse_options_header

from ml_pipeline_pro.api import Project, Store
from ml_pipeline_pro.dataset_files import UPLOAD_MAX_BYTES, publish_dataset, upload_directory
from ml_pipeline_pro.dataset_preparation import PREPARATION_SECONDS, digest, prepare_csv
from ml_pipeline_pro.dataset_uploads import _file_io, _matching_record, _receive, upload_access
from ml_pipeline_pro.datasets import DatasetValidationError, load_dataset
from ml_pipeline_pro.errors import ApiError, ErrorResponse
from ml_pipeline_pro.preparation_files import read_preparation
from ml_pipeline_pro.preparation_schemas import PreparationSettings
from ml_pipeline_pro.schemas import DatasetFileReference, DatasetRecord, PreparationReference

SETTINGS_MAX_BYTES = 32 * 1024
OVERHEAD_MAX_BYTES = 32 * 1024
router = APIRouter(
    prefix="/api/v1/datasets",
    tags=["datasets"],
    dependencies=[Depends(upload_access)],
    responses={
        code: {"model": ErrorResponse} for code in (400, 403, 404, 408, 409, 413, 415, 422, 503)
    },
)


def parse_multipart(envelope: Path, raw: Path, boundary: bytes, raw_limit: int, deadline: float):
    """Parse only after the bounded envelope arrives; never use unbounded form spooling."""
    fields, current, header, settings_data = {}, {}, {}, bytearray()
    complete = False
    raw_size = 0

    def guard():
        if perf_counter() > deadline:
            raise TimeoutError

    def begin():
        current.clear()
        header.clear()
        current.update(field=bytearray(), value=bytearray())

    def header_field(data, start, end):
        current["field"].extend(data[start:end])

    def header_value(data, start, end):
        current["value"].extend(data[start:end])

    def header_end():
        name = bytes(current["field"]).lower()
        if name in header:
            raise ApiError(422, "invalid_preparation", "Duplicate multipart header")
        header[name] = bytes(current["value"])
        current["field"].clear()
        current["value"].clear()

    def headers_finished():
        kind, options = parse_options_header(header.get(b"content-disposition", b""))
        name = options.get(b"name")
        if kind != b"form-data" or name not in {b"file", b"settings"} or name in fields:
            raise ApiError(422, "invalid_preparation", "Supply exactly one file and settings part")
        fields[name] = True
        current["name"] = name

    def part_data(data, start, end):
        nonlocal raw_size
        guard()
        chunk = data[start:end]
        if current["name"] == b"file":
            if len(chunk) > raw_limit - raw_size:
                raise ApiError(413, "dataset_too_large", "Dataset exceeds the raw CSV byte limit")
            destination.write(chunk)
            raw_size += len(chunk)
        else:
            if len(chunk) > SETTINGS_MAX_BYTES - len(settings_data):
                raise ApiError(413, "settings_too_large", "Preparation settings exceed 32 KiB")
            settings_data.extend(chunk)

    def end():
        nonlocal complete
        complete = True

    callbacks = {
        "on_part_begin": begin,
        "on_header_field": header_field,
        "on_header_value": header_value,
        "on_header_end": header_end,
        "on_headers_finished": headers_finished,
        "on_part_data": part_data,
        "on_end": end,
    }
    with raw.open("wb") as destination, envelope.open("rb") as source:
        parser = MultipartParser(boundary, callbacks)
        while chunk := source.read(65536):
            guard()
            parser.write(chunk)
        parser.finalize()
    if not complete or set(fields) != {b"file", b"settings"}:
        raise ApiError(422, "invalid_preparation", "Multipart upload is incomplete")
    if envelope.stat().st_size - raw_size - len(settings_data) > OVERHEAD_MAX_BYTES:
        raise ApiError(413, "multipart_too_large", "Multipart overhead exceeds its byte limit")
    try:
        # Reject duplicate JSON keys rather than silently discard a reviewed setting.
        def unique_pairs(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError
                value[key] = item
            return value

        parsed = json.loads(settings_data, object_pairs_hook=unique_pairs)
        return PreparationSettings.model_validate(parsed)
    except (ValueError, ValidationError):
        raise ApiError(422, "invalid_preparation", "Preparation settings are invalid") from None


def _stage(directory):
    descriptor, filename = tempfile.mkstemp(prefix="staging_", dir=directory)
    os.close(descriptor)
    return Path(filename)


def _publish(content, directory, suffix=".csv"):
    staged = _stage(directory)
    try:
        staged.write_bytes(content)
        sha = digest(content)
        uri = publish_dataset(staged, directory, sha, len(content), suffix=suffix)
        return DatasetFileReference(uri=uri, sha256=sha, size_bytes=len(content))
    finally:
        staged.unlink(missing_ok=True)


async def _prepare(request, project, store, response, *, register):
    media, options = parse_options_header(request.headers.get("content-type", ""))
    boundary = options.get(b"boundary", b"")
    if media != b"multipart/form-data" or not 1 <= len(boundary) <= 200:
        raise ApiError(415, "unsupported_media_type", "Supply multipart CSV file and JSON settings")
    settings = request.app.state.settings
    envelope = raw = None
    try:
        directory = await _file_io(upload_directory, project, settings)
        envelope = _stage(directory)
        raw = _stage(directory)
        raw_limit = min(settings.dataset_max_bytes, UPLOAD_MAX_BYTES)
        with envelope.open("wb") as destination:
            await _receive(
                request, destination, raw_limit + SETTINGS_MAX_BYTES + OVERHEAD_MAX_BYTES
            )
        deadline = perf_counter() + PREPARATION_SECONDS
        config = await _file_io(parse_multipart, envelope, raw, boundary, raw_limit, deadline)
        content = await _file_io(raw.read_bytes)
        prepared = await _file_io(prepare_csv, content, config, settings, deadline=deadline)
        if not register:
            return prepared.preview
        if config.reviewed_sha256 != prepared.preview["preview_sha256"]:
            raise ApiError(
                409,
                "preparation_review_required",
                "Refresh and review this exact encoding before saving",
            )
        source = await _file_io(_publish, content, directory)
        canonical = await _file_io(_publish, prepared.content, directory)
        manifest = await _file_io(_publish, prepared.manifest, directory, ".preparation.json")
        now = datetime.now(UTC)
        now = now.replace(microsecond=now.microsecond // 1000 * 1000)
        candidate = DatasetRecord(
            project_id=project,
            name=config.name,
            version=config.version,
            uri=canonical.uri,
            sha256=canonical.sha256,
            feature_columns=prepared.preview["feature_columns"],
            row_counts=prepared.preview["row_counts"],
            num_classes=len(prepared.preview["label_mapping"]),
            preparation=PreparationReference(
                source=source,
                manifest=manifest,
                recipe_sha256=prepared.preview["recipe_sha256"],
            ),
            created_at=now,
            updated_at=now,
        )
        # Reach the unchanged loader boundary before registering a prepared dataset.
        await _file_io(load_dataset, candidate, settings)
        saved = await _matching_record(store, candidate, settings)
        if saved is not None:
            await _file_io(read_preparation, saved, settings)
            response.status_code = 200
            return saved
        try:
            return await store.datasets.insert(candidate)
        except DuplicateKeyError:
            saved = await _matching_record(store, candidate, settings)
            if saved is None:
                raise
            await _file_io(read_preparation, saved, settings)
            response.status_code = 200
            return saved
    except DatasetValidationError as exc:
        raise ApiError(422, "invalid_preparation", str(exc)) from None
    except (MultipartParseError, KeyError):
        raise ApiError(422, "invalid_preparation", "Multipart CSV upload is malformed") from None
    except TimeoutError:
        raise ApiError(
            408, "preparation_timeout", "Dataset preparation exceeded its time budget"
        ) from None
    except ImportError:
        raise ApiError(
            503, "preparation_unavailable", "Dataset preparation dependencies are unavailable"
        ) from None
    except OSError:
        raise ApiError(
            503, "dataset_storage_unavailable", "Dataset file storage is unavailable"
        ) from None
    finally:
        for staged in (envelope, raw):
            if staged is not None:
                staged.unlink(missing_ok=True)


@router.post("/preview")
async def preview_dataset(request: Request, project: Project, store: Store, response: Response):
    return await _prepare(request, project, store, response, register=False)


@router.post("/prepare", response_model=DatasetRecord, status_code=201)
async def prepare_dataset(request: Request, project: Project, store: Store, response: Response):
    return await _prepare(request, project, store, response, register=True)
