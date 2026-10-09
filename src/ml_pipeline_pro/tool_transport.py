"""Scoped HTTP transport for the existing API, with no automatic retries."""

import math
import re
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Literal, Protocol, Self
from urllib.parse import urlsplit

import httpx

from ml_pipeline_pro.tool_schemas import ToolContext


@dataclass(frozen=True)
class ToolResponse:
    status_code: int
    payload: Any
    correlation_id: str


class ToolTransportError(Exception):
    """Only fixed, credential-free messages cross the tool boundary."""

    def __init__(self, code: str, message: str, status_code: int | None = None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class ToolTransport(Protocol):
    async def request(
        self,
        method: Literal["GET", "POST"],
        path: str,
        *,
        context: ToolContext,
        query: list[tuple[str, str]],
        body: dict[str, Any] | None,
    ) -> ToolResponse: ...


class HttpToolTransport:
    """Owns an AsyncClient; use with ``async with`` to release connections."""

    def __init__(
        self,
        origin: str,
        *,
        timeout_seconds: float = 10,
        transport: httpx.AsyncBaseTransport | None = None,
        max_response_bytes: int | None = None,
    ):
        try:
            parsed = urlsplit(origin)
            valid = (
                parsed.scheme in {"http", "https"}
                and parsed.hostname
                and parsed.username is None
                and parsed.password is None
                and parsed.path in {"", "/"}
                and not parsed.query
                and not parsed.fragment
            )
            _ = parsed.port  # Access validates the port, even if no connection is made.
            if not valid:
                raise ValueError
            base_url = httpx.URL(origin)
        except (ValueError, httpx.InvalidURL):
            raise ValueError(
                "API origin must be HTTP(S) without credentials, path, query or fragment"
            ) from None
        if (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError("HTTP timeout must be positive and finite")
        if max_response_bytes is not None and (
            type(max_response_bytes) is not int or max_response_bytes < 1
        ):
            raise ValueError("Response byte limit must be a positive integer or None")
        self.max_response_bytes = max_response_bytes
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )

    async def __aenter__(self) -> Self:
        await self._client.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self._client.__aexit__(exc_type, exc, tb)

    async def request(
        self,
        method: Literal["GET", "POST"],
        path: str,
        *,
        context: ToolContext,
        query: list[tuple[str, str]],
        body: dict[str, Any] | None,
    ) -> ToolResponse:
        headers = {"X-Project-ID": context.project_id, "X-Correlation-ID": context.correlation_id}
        if context.api_key is not None:
            headers["X-API-Key"] = context.api_key.get_secret_value()
        if body is not None and context.submission_key is not None:
            headers["Idempotency-Key"] = context.submission_key
        try:
            async with self._client.stream(
                method, path, headers=headers, params=query, json=body
            ) as response:
                chunks = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if self.max_response_bytes is not None and size > self.max_response_bytes:
                        raise ToolTransportError(
                            "tool_response_too_large",
                            "API response exceeds the byte limit",
                            response.status_code,
                        )
                    chunks.append(chunk)
                # Keep decoded bytes for the same JSON/error parsing path below.
                response._content = b"".join(chunks)
        except httpx.TimeoutException:
            raise ToolTransportError(
                "tool_timeout", "API request timed out; submission may have been accepted"
            ) from None
        except (httpx.RequestError, RuntimeError):
            raise ToolTransportError(
                "tool_transport_error", "API request could not be completed"
            ) from None
        if 300 <= response.status_code < 400:
            raise ToolTransportError(
                "tool_invalid_response", "API redirects are not supported", response.status_code
            )
        correlation_id = response.headers.get("X-Correlation-ID", context.correlation_id)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", correlation_id):
            raise ToolTransportError(
                "tool_invalid_response",
                "API returned an invalid correlation ID",
                response.status_code,
            )
        try:
            payload = response.json()
        except ValueError:
            raise ToolTransportError(
                "tool_invalid_response",
                "API returned an invalid JSON response",
                response.status_code,
            ) from None
        return ToolResponse(response.status_code, payload, correlation_id)
