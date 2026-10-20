from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr

from ml_pipeline_pro.deletion_api import get_deletion_store
from ml_pipeline_pro.deletion_schemas import DeletionCounts, DeletionPreview, DeletionResult
from ml_pipeline_pro.errors import ApiError
from ml_pipeline_pro.main import create_model_app, create_monitoring_app, create_tuning_app


@pytest.fixture
def deletion_service(app):
    preview = DeletionPreview(
        kind="datasets",
        record_id="record",
        name="fixture",
        version="v1",
        preview_sha256="a" * 64,
        counts=DeletionCounts(datasets=1),
        active_jobs=0,
    )
    receipt = DeletionResult(
        operation_id="operation",
        kind="datasets",
        record_id="record",
        status="complete",
        counts=preview.counts,
        created_at=datetime.now(UTC),
    )
    service = SimpleNamespace(
        preview=AsyncMock(return_value=preview),
        delete=AsyncMock(return_value=receipt),
        get=AsyncMock(return_value=receipt),
    )
    app.dependency_overrides[get_deletion_store] = lambda: service
    return service


def test_preview_delete_and_status_have_typed_scoped_contracts(client, deletion_service):
    client.headers.update({"X-Project-ID": "demo", "X-Correlation-ID": "deletion-contract"})
    preview = client.get("/api/v1/datasets/record/deletion-preview")
    assert preview.status_code == 200 and preview.json()["counts"]["datasets"] == 1
    assert preview.headers["X-Correlation-ID"] == "deletion-contract"
    body = {"preview_sha256": preview.json()["preview_sha256"]}
    assert client.request("DELETE", "/api/v1/datasets/record", json=body).status_code == 422
    assert (
        client.request(
            "DELETE",
            "/api/v1/datasets/record",
            json={**body, "cascade": True},
            headers={"Idempotency-Key": "intent"},
        ).status_code
        == 422
    )
    deletion_service.delete.assert_not_awaited()
    erased = client.request(
        "DELETE", "/api/v1/datasets/record", json=body, headers={"Idempotency-Key": "intent"}
    )
    assert erased.status_code == 200 and erased.json()["status"] == "complete"
    assert client.get("/api/v1/deletions/operation").json() == erased.json()


def test_deletion_requires_project_access_before_any_storage_action(app, client, deletion_service):
    app.state.settings.project_api_keys = {"demo": SecretStr("deletion-fixture-key")}
    response = client.get(
        "/api/v1/datasets/record/deletion-preview", headers={"X-Project-ID": "demo"}
    )
    assert response.status_code == 403
    response = client.request(
        "DELETE",
        "/api/v1/models/record",
        json={"preview_sha256": "a" * 64},
        headers={"X-Project-ID": "demo", "Idempotency-Key": "intent"},
    )
    assert response.status_code == 403
    assert (
        client.get("/api/v1/deletions/operation", headers={"X-Project-ID": "demo"}).status_code
        == 403
    )
    deletion_service.preview.assert_not_awaited()
    deletion_service.delete.assert_not_awaited()
    deletion_service.get.assert_not_awaited()


def test_blocker_error_remains_correlated_and_does_not_claim_completion(client, deletion_service):
    deletion_service.delete.side_effect = ApiError(
        409, "deletion_blocked", "Wait for jobs to finish", {"active_jobs": 2}
    )
    response = client.request(
        "DELETE",
        "/api/v1/datasets/record",
        json={"preview_sha256": "a" * 64},
        headers={
            "X-Project-ID": "demo",
            "Idempotency-Key": "intent",
            "X-Correlation-ID": "blocked-deletion",
        },
    )
    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "deletion_blocked",
        "message": "Wait for jobs to finish",
        "correlation_id": "blocked-deletion",
        "details": {"active_jobs": 2},
    }
    assert response.headers["X-Correlation-ID"] == "blocked-deletion"


def test_model_service_exposes_explicit_deletion_routes_only():
    paths = create_model_app().openapi()["paths"]
    assert "delete" in paths["/api/v1/datasets/{dataset_id}"]
    assert "delete" in paths["/api/v1/models/{model_id}"]
    assert "/api/v1/deletions/{operation_id}" in paths
    assert "/api/v1/{kind}/{record_id}" not in paths
    for factory in (create_tuning_app, create_monitoring_app):
        assert "/api/v1/deletions/{operation_id}" not in factory().openapi()["paths"]
