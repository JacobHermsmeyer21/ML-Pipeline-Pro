"""Project-scoped, idempotent tuning submission and cancellation."""

import asyncio
import hashlib
import json
from typing import Annotated

from fastapi import APIRouter, Depends
from kombu.exceptions import OperationalError
from pymongo.errors import DuplicateKeyError
from redis.exceptions import RedisError

from ml_pipeline_pro.access import project_access
from ml_pipeline_pro.api import Dispatch, Limit, Offset, Project, Store, SubmissionKey
from ml_pipeline_pro.errors import ApiError, ErrorResponse
from ml_pipeline_pro.schemas import Page
from ml_pipeline_pro.tuning_schemas import TrialResult, TuningCreate, TuningRecord, TuningResult
from ml_pipeline_pro.tuning_store import TuningStore, get_tuning_store

router = APIRouter(
    prefix="/api/v1/tuning-jobs",
    tags=["tuning"],
    dependencies=[Depends(project_access)],
    responses={code: {"model": ErrorResponse} for code in (403, 404, 409, 503)},
)
Tuning = Annotated[TuningStore, Depends(get_tuning_store)]


@router.post("", response_model=TuningResult, status_code=202)
async def create_tuning_job(
    body: TuningCreate,
    project: Project,
    store: Store,
    tuning: Tuning,
    dispatch: Dispatch,
    key: SubmissionKey,
):
    fingerprint = hashlib.sha256(json.dumps(body.model_dump(), sort_keys=True).encode()).hexdigest()
    record = await tuning.jobs.by_submission(project, key)
    if record is None:
        await store.lifecycle.check_submission(project, "tuning_jobs", key, fingerprint)
        if await store.datasets.get(project, body.dataset_id) is None:
            raise ApiError(404, "dataset_not_found", "Dataset was not found in this project")
        model = await store.models.get(project, body.model_id)
        if model is None:
            raise ApiError(404, "model_not_found", "Model was not found in this project")
        if model.architecture != "mlp":
            raise ApiError(409, "unsupported_model_algorithm", "Logistic tuning is not supported")
        try:
            record = await tuning.jobs.admit(
                TuningRecord(
                    **body.model_dump(),
                    project_id=project,
                    submission_key=key,
                    request_hash=fingerprint,
                ),
                [("datasets", body.dataset_id), ("models", body.model_id)],
            )
        except DuplicateKeyError:
            record = await tuning.jobs.by_submission(project, key)
            if record is None:
                raise
    if record.request_hash != fingerprint:
        raise ApiError(
            409,
            "idempotency_conflict",
            "This submission key already belongs to a different tuning request",
        )
    await store.lifecycle.check_read(project, "tuning_jobs", record.id)
    if record.status == "queued":
        try:
            await asyncio.to_thread(dispatch.publish_tuning, project, record.id)
        except (OperationalError, RedisError, OSError):
            raise ApiError(
                503,
                "queue_unavailable",
                "Tuning queue is unavailable; retry with the same submission key",
                {"tuning_job_id": record.id},
            ) from None
        await tuning.jobs.mark_dispatched(project, record.id)
    return record


@router.get("", response_model=Page[TuningResult])
async def list_tuning_jobs(project: Project, tuning: Tuning, limit: Limit = 50, offset: Offset = 0):
    return Page[TuningResult](
        items=await tuning.jobs.list(project, limit=limit, offset=offset),
        limit=limit,
        offset=offset,
    )


@router.get("/{job_id}", response_model=TuningResult)
async def get_tuning_job(job_id: str, project: Project, tuning: Tuning):
    record = await tuning.jobs.get(project, job_id)
    if record is None:
        raise ApiError(404, "tuning_job_not_found", "Tuning job was not found in this project")
    return record


@router.get("/{job_id}/trials", response_model=Page[TrialResult])
async def list_tuning_trials(
    job_id: str, project: Project, tuning: Tuning, limit: Limit = 50, offset: Offset = 0
):
    await get_tuning_job(job_id, project, tuning)
    return Page[TrialResult](
        items=await tuning.trials.for_job(project, job_id, limit=limit, offset=offset),
        limit=limit,
        offset=offset,
    )


@router.post("/{job_id}/cancel", response_model=TuningResult, status_code=202)
async def cancel_tuning_job(job_id: str, project: Project, tuning: Tuning):
    record = await tuning.jobs.request_cancel(project, job_id)
    if record is None:
        raise ApiError(404, "tuning_job_not_found", "Tuning job was not found in this project")
    if record.status in {"succeeded", "failed"}:
        raise ApiError(409, "tuning_job_complete", "Completed tuning jobs cannot be cancelled")
    return record
