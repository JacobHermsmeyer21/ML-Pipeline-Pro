import asyncio
import gzip
import json

import httpx
import pytest

from ml_pipeline_pro.errors import ErrorDetail, ErrorResponse
from ml_pipeline_pro.schemas import ModelRecord
from ml_pipeline_pro.tool_schemas import ToolCall, ToolContext
from ml_pipeline_pro.tool_transport import HttpToolTransport
from ml_pipeline_pro.tools import ToolDispatcher


class Chunks(httpx.AsyncByteStream):
    def __init__(self, chunks):
        self.chunks, self.yielded, self.closed = chunks, 0, False

    async def __aiter__(self):
        for chunk in self.chunks:
            self.yielded += 1
            yield chunk

    async def aclose(self):
        self.closed = True


def test_response_cap_counts_decoded_utf8_at_boundary_and_closes_chunked_gzip_streams():
    from ml_pipeline_pro.conversation_schemas import TOOL_BYTES
    from ml_pipeline_pro.tool_transport import ToolTransportError

    base = len(json.dumps({"message": ""}, separators=(",", ":")).encode())
    remaining = TOOL_BYTES - base
    body = json.dumps(
        {"message": "é" * (remaining // 2) + "x" * (remaining % 2)},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    assert len(body) == TOOL_BYTES

    async def run():
        for chunks, headers, accepted in [
            ([body], {}, True),
            ([body, b" ", b"must not be consumed"], {}, False),
            ([gzip.compress(body + b" ")], {"content-encoding": "gzip"}, False),
        ]:
            stream = Chunks(chunks)
            probe = ProbeTransport(httpx.Response(200, headers=headers, stream=stream))
            async with HttpToolTransport(
                "http://api", max_response_bytes=TOOL_BYTES, transport=probe
            ) as transport:
                if accepted:
                    result = await transport.request(
                        "GET",
                        "/api/v1/models",
                        context=ToolContext(project_id="demo"),
                        query=[],
                        body=None,
                    )
                    assert result.payload["message"].startswith("é")
                else:
                    with pytest.raises(ToolTransportError) as caught:
                        await transport.request(
                            "GET",
                            "/api/v1/models",
                            context=ToolContext(project_id="demo"),
                            query=[],
                            body=None,
                        )
                    assert caught.value.code == "tool_response_too_large"
            assert stream.closed and probe.closed
            assert stream.yielded == min(2, len(chunks))

    asyncio.run(run())


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, "128"])
def test_response_cap_rejects_invalid_configuration(limit):
    with pytest.raises(ValueError):
        HttpToolTransport("http://api", max_response_bytes=limit)


KEY = "tool-transport-secret-key"


class ProbeTransport(httpx.AsyncBaseTransport):
    def __init__(self, response):
        self.response = response
        self.requests = []
        self.closed = False

    async def handle_async_request(self, request):
        self.requests.append(request)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    async def aclose(self):
        self.closed = True


def invoke(probe, tool_call=None, execution_context=None):
    async def run():
        async with HttpToolTransport("http://api.example", transport=probe) as transport:
            return await ToolDispatcher(transport).execute(
                tool_call or ToolCall(name="list_models"),
                execution_context
                or ToolContext(project_id="demo", api_key=KEY, correlation_id="transport-test"),
            )

    return asyncio.run(run())


def test_http_client_binds_headers_timeout_query_and_closes():
    probe = ProbeTransport(
        httpx.Response(
            200,
            json={"items": [], "limit": 2, "offset": 1},
            headers={"X-Correlation-ID": "transport-test"},
        )
    )
    result = invoke(probe, ToolCall(name="list_models", arguments={"limit": 2, "offset": 1}))
    assert result.status == "succeeded"
    assert len(probe.requests) == 1
    request = probe.requests[0]
    assert request.method == "GET"
    assert str(request.url) == "http://api.example/api/v1/models?limit=2&offset=1"
    assert request.headers["X-Project-ID"] == "demo"
    assert request.headers["X-API-Key"] == KEY
    assert request.headers["X-Correlation-ID"] == "transport-test"
    assert "Idempotency-Key" not in request.headers
    assert request.extensions["timeout"] == {"connect": 10, "read": 10, "write": 10, "pool": 10}
    assert request.content == b""
    assert probe.closed
    assert KEY not in result.model_dump_json()


def test_submission_uses_bound_key_and_documented_nonbudget_defaults():
    probe = ProbeTransport(
        httpx.Response(
            503,
            json=ErrorResponse(
                error=ErrorDetail(
                    code="queue_unavailable",
                    message="Queue unavailable",
                    correlation_id="transport-test",
                    details={"experiment_id": "saved"},
                )
            ).model_dump(),
        )
    )
    result = invoke(
        probe,
        ToolCall(
            name="create_experiment",
            arguments={
                "dataset_id": "dataset",
                "model_id": "model",
                "config": {"max_runtime_seconds": 17},
            },
        ),
        ToolContext(
            project_id="demo",
            api_key=KEY,
            correlation_id="transport-test",
            allow_mutations=True,
            submission_key="host-action",
        ),
    )
    request = probe.requests[0]
    assert request.method == "POST"
    assert request.headers["Idempotency-Key"] == "host-action"
    body = json.loads(request.content)
    assert body["config"]["max_runtime_seconds"] == 17
    assert body["config"]["epochs"] == 30
    assert "submission_key" not in body
    assert result.error.details["experiment_id"] == "saved"
    assert result.http_status == 503
    assert len(probe.requests) == 1


@pytest.mark.parametrize(
    "response,code",
    [
        (httpx.ReadTimeout(f"unsafe {KEY}"), "tool_timeout"),
        (httpx.ConnectError(f"unsafe {KEY}"), "tool_transport_error"),
        (
            httpx.Response(302, headers={"Location": f"https://{KEY}@other.example"}),
            "tool_invalid_response",
        ),
        (httpx.Response(200, text=f"<html>{KEY}</html>"), "tool_invalid_response"),
        (
            httpx.Response(
                200,
                json={"items": [], "limit": 50, "offset": 0},
                headers={"X-Correlation-ID": "invalid id"},
            ),
            "tool_invalid_response",
        ),
        (httpx.Response(503, json={"error": {"message": KEY}}), "tool_invalid_response"),
        (
            httpx.Response(200, json={"items": [{"password": KEY}], "limit": 50, "offset": 0}),
            "tool_invalid_response",
        ),
        (
            httpx.Response(200, json={"items": [], "limit": 101, "offset": 0}),
            "tool_invalid_response",
        ),
        (
            httpx.Response(201, json={"items": [], "limit": 50, "offset": 0}),
            "tool_invalid_response",
        ),
        (
            httpx.Response(
                200,
                json={
                    "items": [
                        ModelRecord(project_id="foreign", name="classifier").model_dump(mode="json")
                    ],
                    "limit": 50,
                    "offset": 0,
                },
            ),
            "tool_invalid_response",
        ),
    ],
)
def test_transport_and_upstream_failures_are_safe_without_retries_or_redirects(response, code):
    probe = ProbeTransport(response)
    result = invoke(probe)
    assert result.status == "error"
    assert result.error.code == code
    assert result.correlation_id == result.error.correlation_id == "transport-test"
    assert KEY not in result.model_dump_json()
    assert len(probe.requests) == 1
    assert probe.closed


def test_error_and_record_text_redact_bound_credentials_and_connection_secrets():
    error = ErrorResponse(
        error=ErrorDetail(
            code="service_error",
            message=f"Failure {KEY} redis://user:private-password@host",
            correlation_id="transport-test",
            details={"nested": [{"credential": KEY}]},
        )
    )
    result = invoke(ProbeTransport(httpx.Response(503, json=error.model_dump())))
    assert KEY not in result.model_dump_json()
    assert "private-password" not in result.model_dump_json()
    assert result.error.details["nested"][0]["credential"] == "[REDACTED]"
    record = ModelRecord(project_id="demo", name=KEY)
    public = invoke(
        ProbeTransport(httpx.Response(200, json=record.model_dump(mode="json"))),
        ToolCall(name="get_model", arguments={"model_id": record.id}),
    )
    assert public.status == "succeeded"
    assert public.data["name"] == "[REDACTED]"
    assert public.evidence[0].record_id == record.id


def test_error_correlation_mismatch_is_rejected():
    error = ErrorResponse(
        error=ErrorDetail(code="not_found", message="Missing", correlation_id="wrong-correlation")
    )
    result = invoke(ProbeTransport(httpx.Response(404, json=error.model_dump())))
    assert result.error.code == "tool_invalid_response"
    assert result.http_status == 404


def test_unexpected_record_identity_and_private_fields_are_rejected():
    record = ModelRecord(project_id="demo", name="classifier").model_dump(mode="json")
    wrong_id = invoke(
        ProbeTransport(httpx.Response(200, json=record)),
        ToolCall(name="get_model", arguments={"model_id": "requested"}),
    )
    assert wrong_id.error.code == "tool_invalid_response"
    record["worker_token"] = KEY
    extra = invoke(
        ProbeTransport(httpx.Response(200, json=record)),
        ToolCall(name="get_model", arguments={"model_id": record["id"]}),
    )
    assert extra.error.code == "tool_invalid_response"
    assert KEY not in extra.model_dump_json()


@pytest.mark.parametrize("missing", ["id", "created_at", "updated_at"])
def test_upstream_response_never_fabricates_record_identity_or_timestamps(missing):
    record = ModelRecord(project_id="demo", name="classifier").model_dump(mode="json")
    del record[missing]
    probe = ProbeTransport(httpx.Response(200, json={"items": [record], "limit": 50, "offset": 0}))
    result = invoke(probe)
    assert result.status == "error"
    assert result.error.code == "tool_invalid_response"


@pytest.mark.parametrize(
    "origin",
    [
        "ftp://api.example",
        "http://user:password@api.example",
        "http://api.example/api/v1",
        "http://api.example?project=other",
        "http://api.example#fragment",
        "http:///missing-host",
        "http://api.example:invalid",
        "http://[broken",
    ],
)
def test_origin_rejects_credential_path_or_destination_overrides(origin):
    with pytest.raises(ValueError, match="API origin") as exc:
        HttpToolTransport(origin)
    assert "password" not in str(exc.value)


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan"), True, None, "10"])
def test_timeout_must_be_positive_finite_number(timeout):
    with pytest.raises(ValueError, match="timeout"):
        HttpToolTransport("http://api.example", timeout_seconds=timeout)


def test_client_releases_transport_on_exception_and_closed_use_is_safe():
    probe = ProbeTransport(httpx.Response(200, json={"items": [], "limit": 50, "offset": 0}))

    async def run():
        transport = HttpToolTransport("http://api.example", transport=probe)
        with pytest.raises(RuntimeError, match="host failure"):
            async with transport:
                raise RuntimeError("host failure")
        assert probe.closed
        return await ToolDispatcher(transport).execute(
            ToolCall(name="list_models"), ToolContext(project_id="demo")
        )

    result = asyncio.run(run())
    assert result.error.code == "tool_transport_error"
    assert probe.requests == []
