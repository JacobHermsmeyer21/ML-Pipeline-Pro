"""FastAPI entry point. Run with uvicorn ml_pipeline_pro.main:create_app --factory."""

import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, FastAPI, Request
from pydantic import BaseModel
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from ml_pipeline_pro import __version__
from ml_pipeline_pro.api import router
from ml_pipeline_pro.column_api import router as column_router
from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.connections import check_readiness, open_connections
from ml_pipeline_pro.conversation_api import ModelFactory, conversation_clients
from ml_pipeline_pro.conversation_api import router as conversation_router
from ml_pipeline_pro.conversation_schemas import REQUEST_BYTES
from ml_pipeline_pro.dashboard_api import install_dashboard
from ml_pipeline_pro.dataset_uploads import router as upload_router
from ml_pipeline_pro.deletion_api import router as deletion_router
from ml_pipeline_pro.errors import ApiError, ErrorResponse, error_response, install_error_handlers
from ml_pipeline_pro.logging import configure_logging
from ml_pipeline_pro.monitoring_api import router as monitoring_router
from ml_pipeline_pro.preparation_api import router as preparation_router
from ml_pipeline_pro.tuning_api import router as tuning_router

logger = logging.getLogger(__name__)
_CORRELATION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"
    correlation_id: str


class ReadinessResponse(BaseModel):
    status: Literal["ready"] = "ready"
    checks: dict[str, str]
    correlation_id: str


def create_app(
    settings: Settings | None = None,
    *,
    chat_model_factory: ModelFactory | None = None,
) -> FastAPI:
    """Compatibility application for existing host/recovery workflows."""
    return _create_app(
        settings,
        (router, tuning_router, conversation_router),
        chat_model_factory=chat_model_factory,
    )


def create_model_app(
    settings: Settings | None = None,
    *,
    chat_model_factory: ModelFactory | None = None,
) -> FastAPI:
    """Independently deployable model management and conversation API."""
    return _create_app(
        settings, (router, conversation_router), chat_model_factory=chat_model_factory
    )


def create_tuning_app(settings: Settings | None = None) -> FastAPI:
    """Tuning REST API; retains shared tracking references and worker repositories."""
    return _create_app(settings, (tuning_router,))


def create_monitoring_app(
    settings: Settings | None = None, *, chat_model_factory: ModelFactory | None = None
) -> FastAPI:
    return _create_app(settings, (monitoring_router,), chat_model_factory=chat_model_factory)


def _create_app(
    settings: Settings | None,
    routers: tuple[APIRouter, ...],
    *,
    chat_model_factory: ModelFactory | None = None,
) -> FastAPI:
    settings = settings if settings is not None else Settings()
    chat_settings = (
        settings
        if conversation_router in routers or monitoring_router in routers
        else settings.model_copy(update={"chat_enabled": False})
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings)
        async with open_connections(settings) as connections:
            app.state.connections = connections
            async with conversation_clients(
                chat_settings, model_factory=chat_model_factory
            ) as clients:
                app.state.conversation_model, app.state.conversation_transport = clients
                logger.info("API started")
                try:
                    yield
                finally:
                    logger.info("API stopping")

    docs_prefix = (
        "/tuning"
        if routers == (tuning_router,)
        else "/monitoring"
        if (routers == (monitoring_router,))
        else ""
    )
    app = FastAPI(
        title="ML Pipeline Pro",
        description="Project-scoped datasets, queued training experiments, and model versions.",
        version=__version__,
        lifespan=lifespan,
        docs_url=f"{docs_prefix}/docs",
        openapi_url=f"{docs_prefix}/openapi.json",
        redoc_url=None if docs_prefix else "/redoc",
        responses={422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    )
    app.state.settings = settings
    install_error_handlers(app)
    for domain_router in routers:
        app.include_router(domain_router)
    if router in routers:
        app.include_router(deletion_router)
        app.include_router(upload_router)
        app.include_router(preparation_router)
        app.include_router(column_router)
        install_dashboard(app)

    @app.middleware("http")
    async def correlate_request(request: Request, call_next: RequestResponseEndpoint) -> Response:
        supplied_id = request.headers.get("X-Correlation-ID", "")
        correlation_id = supplied_id if _CORRELATION_ID.fullmatch(supplied_id) else str(uuid4())
        request.state.correlation_id = correlation_id
        started = perf_counter()
        path = request.url.path
        monitoring_post = path.startswith("/api/v1/monitoring/")
        column_post = path.startswith("/api/v1/datasets/") and (
            path.endswith("/columns") or path.endswith("/columns/preview")
        )
        if request.method == "POST" and (
            monitoring_post
            or column_post
            or path == "/api/v1/chat"
            or (path.startswith("/api/v1/conversations/") and path.endswith("/decision"))
        ):
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > REQUEST_BYTES:
                    return error_response(
                        request,
                        422,
                        "column_limit_exceeded"
                        if column_post
                        else "monitoring_limit_exceeded"
                        if monitoring_post
                        else "chat_limit_exceeded",
                        "Column request exceeds byte limit"
                        if column_post
                        else "Monitoring request exceeds byte limit"
                        if monitoring_post
                        else "Conversation request exceeds byte limit",
                    )
                body.extend(chunk)
            request._body = bytes(body)
        status_code = 500
        try:
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = correlation_id
            status_code = response.status_code
            return response
        finally:
            logger.info(
                "Request completed",
                extra={
                    "correlation_id": correlation_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                },
            )

    @app.get("/api/v1/health/live", response_model=LivenessResponse, tags=["health"])
    async def live(request: Request) -> LivenessResponse:
        return LivenessResponse(correlation_id=request.state.correlation_id)

    @app.get(
        "/api/v1/health/ready",
        response_model=ReadinessResponse,
        responses={503: {"model": ErrorResponse}},
        tags=["health"],
    )
    async def ready(request: Request) -> ReadinessResponse:
        checks = await check_readiness(request.app.state.connections, settings)
        if any(status != "up" for status in checks.values()):
            raise ApiError(
                503,
                "dependencies_unavailable",
                "One or more required services are unavailable",
                {"checks": checks},
            )
        return ReadinessResponse(checks=checks, correlation_id=request.state.correlation_id)

    return app
