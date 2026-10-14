"""Independent REST observation, visualization and bounded diagnosis endpoints."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST

from ml_pipeline_pro.access import project_access
from ml_pipeline_pro.conversation_model import ConversationModelError
from ml_pipeline_pro.conversation_schemas import serialized
from ml_pipeline_pro.errors import ApiError
from ml_pipeline_pro.logging import JsonFormatter, configured_secrets
from ml_pipeline_pro.monitoring import get_monitoring_store, metrics, snapshot_time, summarize
from ml_pipeline_pro.monitoring_schemas import (
    MonitoringDiagnosis,
    MonitoringSummary,
    ObservationCreate,
    ObservationRecord,
)
from ml_pipeline_pro.schemas import Page
from ml_pipeline_pro.tool_schemas import ResourceId
from ml_pipeline_pro.tracking import get_store

router = APIRouter(
    prefix="/api/v1/monitoring", dependencies=[Depends(project_access)], tags=["monitoring"]
)
Project = Annotated[str, Depends(project_access)]
Store = Annotated[object, Depends(get_monitoring_store)]
Tracking = Annotated[object, Depends(get_store)]
Window = Annotated[int, Query(ge=30, le=3600)]


async def require_version(project, version, tracking):
    if await tracking.versions.get(project, version) is None:
        raise ApiError(404, "model_version_not_found", "Model version was not found")


@router.post("/observations", response_model=ObservationRecord, status_code=201)
async def observe(body: ObservationCreate, project: Project, store: Store, tracking: Tracking):
    await require_version(project, body.model_version_id, tracking)
    return await store.insert(project, body)


@router.get("/observations", response_model=Page[ObservationRecord])
async def observations(
    project: Project,
    store: Store,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return Page(
        items=await store.observations.list(project, limit=limit, offset=offset),
        limit=limit,
        offset=offset,
    )


async def measured_summary(project, version, store, tracking, seconds):
    await require_version(project, version, tracking)
    now = snapshot_time()
    return summarize(await store.window(project, version, seconds, now), version, seconds, now)


@router.get("/model-versions/{version_id}/summary", response_model=MonitoringSummary)
async def summary(
    version_id: ResourceId,
    project: Project,
    store: Store,
    tracking: Tracking,
    window_seconds: Window = 300,
):
    return await measured_summary(project, version_id, store, tracking, window_seconds)


@router.post("/model-versions/{version_id}/diagnosis", response_model=MonitoringDiagnosis)
async def diagnosis(
    version_id: ResourceId,
    request: Request,
    project: Project,
    store: Store,
    tracking: Tracking,
    window_seconds: Window = 300,
):
    measured = await measured_summary(project, version_id, store, tracking, window_seconds)
    if measured.availability == "missing":
        raise ApiError(409, "monitoring_data_missing", "No observations in the requested window")
    model = request.app.state.conversation_model
    if model is None or not hasattr(model, "generate_monitoring"):
        raise ApiError(503, "model_unavailable", "Monitoring explanation model is not configured")
    try:
        async with asyncio.timeout(request.app.state.settings.chat_model_timeout_seconds):
            step = await model.generate_monitoring(
                [{"role": "user", "content": serialized(measured.model_dump()).decode()}]
            )
    except ConversationModelError as exc:
        raise ApiError(
            503 if exc.code == "model_unavailable" else 422, exc.code, exc.message
        ) from None
    except TimeoutError:
        raise ApiError(503, "chat_timeout", "Monitoring explanation timed out") from None
    if not set(step.advice.observation_ids) <= set(measured.observation_ids):
        raise ApiError(422, "model_invalid_response", "Explanation cites absent observations")
    from ml_pipeline_pro.conversation_service import PUBLIC_MODEL_PROVENANCE

    formatter = JsonFormatter(
        (*configured_secrets(request.app.state.settings), request.headers.get("X-API-Key", ""))
    )

    def safe(value):
        if isinstance(value, dict):
            return {formatter.redact(key): safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [safe(item) for item in value]
        return formatter.redact(value)

    return MonitoringDiagnosis(
        measurements=measured,
        generated_advice=safe(step.advice.model_dump()),
        model_provenance=safe(
            {
                **{
                    key: value
                    for key, value in model.provenance.items()
                    if key in PUBLIC_MODEL_PROVENANCE
                },
                **step.provenance,
                **step.usage,
            }
        ),
    )


@router.get("/metrics", response_class=Response)
async def export_metrics(project: Project, store: Store):
    now = snapshot_time()
    records = await store.window(project, None, 300, now)
    return Response(metrics(records, now), media_type=CONTENT_TYPE_LATEST)
