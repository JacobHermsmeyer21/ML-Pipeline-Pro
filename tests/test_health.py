from uuid import UUID

import pytest
from fastapi.testclient import TestClient


def test_liveness_does_not_contact_dependencies(client, fake_connections):
    fake_connections.mongo.admin.error = ConnectionError("mongodb unavailable")
    fake_connections.redis.error = ConnectionError("redis unavailable")

    response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["correlation_id"] == response.headers["X-Correlation-ID"]
    assert fake_connections.mongo.admin.calls == 0
    assert fake_connections.redis.calls == 0


def test_readiness_checks_both_dependencies(client, fake_connections):
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json()["checks"] == {"mongodb": "up", "redis": "up"}
    assert fake_connections.mongo.admin.calls == 1
    assert fake_connections.redis.calls == 1


@pytest.mark.parametrize("failed", ["mongodb", "redis", "both"])
def test_readiness_reports_outages_without_exposing_credentials(client, fake_connections, failed):
    secret = "mongodb://user:private-password@host:27017"
    if failed in {"mongodb", "both"}:
        fake_connections.mongo.admin.error = ConnectionError(secret)
    if failed in {"redis", "both"}:
        fake_connections.redis.error = ConnectionError(secret)

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "dependencies_unavailable"
    assert error["correlation_id"] == response.headers["X-Correlation-ID"]
    checks = error["details"]["checks"]
    assert checks["mongodb"] == ("down" if failed in {"mongodb", "both"} else "up")
    assert checks["redis"] == ("down" if failed in {"redis", "both"} else "up")
    assert "private-password" not in response.text


def test_readiness_times_out_a_hung_dependency(client, fake_connections):
    fake_connections.redis.delay = 1

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["error"]["details"]["checks"] == {"mongodb": "up", "redis": "down"}


def test_request_id_is_reused(client):
    response = client.get("/api/v1/health/live", headers={"X-Correlation-ID": "test-request-42"})

    assert response.headers["X-Correlation-ID"] == "test-request-42"
    assert response.json()["correlation_id"] == "test-request-42"


@pytest.mark.parametrize("supplied_id", ["", "x" * 65, "unsafe token", "☃"])
def test_invalid_request_ids_are_replaced(client, supplied_id):
    # HTTP header values are bytes; the non-ASCII case arrives as Latin-1 text.
    response = client.get(
        "/api/v1/health/live", headers={"X-Correlation-ID": supplied_id.encode("utf-8")}
    )

    assert UUID(response.headers["X-Correlation-ID"])


def test_connections_are_closed_on_shutdown(app, fake_connections):
    with TestClient(app) as client:
        assert client.get("/api/v1/health/live").status_code == 200
        assert not fake_connections.closed
    assert fake_connections.closed


def test_openapi_documents_readiness_failure(client):
    specification = client.get("/openapi.json").json()

    assert "503" in specification["paths"]["/api/v1/health/ready"]["get"]["responses"]
