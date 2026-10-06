"""Consistent, correlation-aware API errors."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError, PyMongoError
from starlette.exceptions import HTTPException

logger = logging.getLogger(__name__)


class ErrorDetail(BaseModel):
    code: str
    message: str
    correlation_id: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    correlation_id = request.state.correlation_id
    payload = ErrorResponse(
        error=ErrorDetail(
            code=code, message=message, correlation_id=correlation_id, details=details
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(exclude_none=True),
        headers={**(headers or {}), "X-Correlation-ID": correlation_id},
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DuplicateKeyError)
    async def handle_duplicate(request: Request, exc: DuplicateKeyError) -> JSONResponse:
        return error_response(
            request, 409, "record_conflict", "A record with this identity already exists"
        )

    @app.exception_handler(PyMongoError)
    async def handle_storage_error(request: Request, exc: PyMongoError) -> JSONResponse:
        logger.warning(
            "Storage operation failed", extra={"correlation_id": request.state.correlation_id}
        )
        return error_response(
            request, 503, "storage_unavailable", "Metadata storage is unavailable"
        )

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return error_response(request, exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(HTTPException)
    async def handle_http_error(request: Request, exc: HTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return error_response(request, exc.status_code, code, message, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        fields = [
            {"location": ".".join(map(str, error["loc"])), "type": error["type"]}
            for error in exc.errors()
        ]
        return error_response(
            request, 422, "validation_error", "Request validation failed", {"fields": fields}
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "Unhandled request error",
            exc_info=(type(exc), exc, exc.__traceback__),
            extra={"correlation_id": request.state.correlation_id},
        )
        return error_response(request, 500, "internal_error", "An unexpected error occurred")
