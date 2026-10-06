import hashlib
from pathlib import Path

import pytest
from pydantic import SecretStr
from pymongo.errors import AutoReconnect


def test_dataset_registration_records_real_content_hash_and_split_counts(
    tracking_client, dataset_body
):
    response = tracking_client.post("/api/v1/datasets", json=dataset_body)

    assert response.status_code == 201, response.text
    record = response.json()
    assert record["project_id"] == "demo"
    assert (
        record["sha256"]
        == hashlib.sha256(Path("examples/data/classification.csv").read_bytes()).hexdigest()
    )
    assert record["row_counts"] == {"train": 80, "validation": 20, "test": 20}
    assert record["num_classes"] == 2
    assert record["schema_version"] == 1
    assert tracking_client.get(f"/api/v1/datasets/{record['id']}").json() == record


def test_dataset_registration_rejects_duplicate_version(tracking_client, dataset_body):
    assert tracking_client.post("/api/v1/datasets", json=dataset_body).status_code == 201
    duplicate = tracking_client.post("/api/v1/datasets", json=dataset_body)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "record_conflict"


def test_dataset_hash_mismatch_does_not_insert(tracking_client, dataset_body):
    response = tracking_client.post(
        "/api/v1/datasets", json={**dataset_body, "expected_sha256": "0" * 64}
    )
    assert response.status_code == 409
    assert tracking_client.get("/api/v1/datasets").json()["items"] == []


@pytest.mark.parametrize(
    "uri", ["../outside.csv", "/absolute.csv", "https://host/data.csv", "a.txt"]
)
def test_dataset_references_are_bounded_to_local_csv_paths(tracking_client, dataset_body, uri):
    response = tracking_client.post("/api/v1/datasets", json={**dataset_body, "uri": uri})
    assert response.status_code == 422


def test_missing_dataset_file_has_an_actionable_error(tracking_client, dataset_body):
    response = tracking_client.post("/api/v1/datasets", json={**dataset_body, "uri": "missing.csv"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_dataset"


def test_model_registration_and_cross_project_isolation(tracking_client):
    created = tracking_client.post("/api/v1/models", json={"name": "classifier"})
    assert created.status_code == 201
    record = created.json()
    assert record["framework"] == "pytorch"
    assert record["architecture"] == "mlp"
    foreign = tracking_client.get(
        f"/api/v1/models/{record['id']}", headers={"X-Project-ID": "other"}
    )
    assert foreign.status_code == 404
    assert (
        tracking_client.get("/api/v1/models", headers={"X-Project-ID": "other"}).json()["items"]
        == []
    )
    assert tracking_client.post("/api/v1/models", json={"name": "classifier"}).status_code == 409
    assert (
        tracking_client.post(
            "/api/v1/models", json={"name": "classifier"}, headers={"X-Project-ID": "other"}
        ).status_code
        == 201
    )


def test_dataset_reads_are_project_scoped(tracking_client, dataset_body):
    record = tracking_client.post("/api/v1/datasets", json=dataset_body).json()
    response = tracking_client.get(
        f"/api/v1/datasets/{record['id']}", headers={"X-Project-ID": "other"}
    )
    assert response.status_code == 404
    assert (
        tracking_client.get("/api/v1/datasets", headers={"X-Project-ID": "other"}).json()["items"]
        == []
    )


def test_model_lists_are_paginated(tracking_client):
    for index in range(3):
        assert (
            tracking_client.post("/api/v1/models", json={"name": f"model_{index}"}).status_code
            == 201
        )
    response = tracking_client.get("/api/v1/models?limit=1&offset=1")
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert response.json()["limit"] == 1
    assert response.json()["offset"] == 1
    assert tracking_client.get("/api/v1/models?limit=101").status_code == 422
    assert tracking_client.get("/api/v1/models?offset=-1").status_code == 422


def test_project_selection_is_required(client, store):
    response = client.post("/api/v1/models", json={"name": "classifier"})
    assert response.status_code == 422
    assert store.models.records == {}


def test_configured_project_keys_are_enforced_before_storage_access(app, client, store):
    app.state.settings.project_api_keys = {"demo": SecretStr("test-key-with-16-characters")}
    for headers in (
        {"X-Project-ID": "demo"},
        {"X-Project-ID": "demo", "X-API-Key": "incorrect"},
        {"X-Project-ID": "other", "X-API-Key": "test-key-with-16-characters"},
    ):
        assert (
            client.post("/api/v1/models", json={"name": "classifier"}, headers=headers).status_code
            == 403
        )
    assert store.models.records == {}
    assert (
        client.post(
            "/api/v1/models",
            json={"name": "classifier"},
            headers={"X-Project-ID": "demo", "X-API-Key": "test-key-with-16-characters"},
        ).status_code
        == 201
    )


def test_storage_outage_returns_503_without_database_credentials(tracking_client, store):
    store.models.error = AutoReconnect("mongodb://user:private-password@localhost")
    response = tracking_client.post("/api/v1/models", json={"name": "classifier"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "storage_unavailable"
    assert "private-password" not in response.text
