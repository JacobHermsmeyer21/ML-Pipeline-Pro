"""FastAPI entry point. Run with uvicorn ml_pipeline_pro.main:create_app --factory."""

import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, Request
from pydantic import BaseModel
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from ml_pipeline_pro import __version__
from ml_pipeline_pro.api import router
from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.connections import check_readiness, open_connections
from ml_pipeline_pro.errors import ApiError, ErrorResponse, install_error_handlers
from ml_pipeline_pro.logging import configure_logging

logger = logging.getLogger(__name__)
_CORRELATION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"
    correlation_id: str


class ReadinessResponse(BaseModel):
    status: Literal["ready"] = "ready"
    checks: dict[str, str]
    correlation_id: str


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings)
        async with open_connections(settings) as connections:
            app.state.connections = connections
            logger.info("API started")
            try:
                yield
            finally:
                logger.info("API stopping")

    app = FastAPI(
        title="ML Pipeline Pro",
        description="Project-scoped registration for reproducible classification experiments.",
        version=__version__,
        lifespan=lifespan,
        responses={422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    )
    app.state.settings = settings
    install_error_handlers(app)
    app.include_router(router)

    @app.middleware("http")
    async def correlate_request(request: Request, call_next: RequestResponseEndpoint) -> Response:
        supplied_id = request.headers.get("X-Correlation-ID", "")
        correlation_id = supplied_id if _CORRELATION_ID.fullmatch(supplied_id) else str(uuid4())
        request.state.correlation_id = correlation_id
        started = perf_counter()
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
