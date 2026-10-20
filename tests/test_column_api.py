"""Column edits must preserve complete data and fitted-transform provenance."""

import csv
import hashlib
import io
import json
from pathlib import Path

import pytest
from pymongo.errors import AutoReconnect

from ml_pipeline_pro import dataset_columns
from ml_pipeline_pro.column_schemas import ColumnEdit
from ml_pipeline_pro.dataset_preparation import transform_rows
from ml_pipeline_pro.errors import ApiError
from ml_pipeline_pro.preparation_files import read_preparation
from ml_pipeline_pro.schemas import DatasetRecord, ExperimentRecord, TrainingConfig
from ml_pipeline_pro.training import train_classifier
from tests.test_dataset_preparation import raw_csv
from tests.test_preparation_api import send


@pytest.fixture
def column_client(tracking_client, app, tmp_path):
    app.state.settings.dataset_upload_enabled = True
    app.state.settings.dataset_root = tmp_path
    app.state.settings.artifact_root = tmp_path / "artifacts"
    return tracking_client


def numeric(client):
    response = client.post(
        "/api/v1/datasets/upload",
        params={"name": "numeric", "version": "v1", "feature_columns": ["feature_1", "feature_2"]},
        content=Path("examples/data/classification.csv").read_bytes(),
        headers={"Content-Type": "text/csv"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def prepared(client, **overrides):
    config = {"name": "raw", "version": "v1", "target_column": "Outcome", **overrides}
    preview = send(client, config=config)
    assert preview.status_code == 200, preview.text
    config["reviewed_sha256"] = preview.json()["preview_sha256"]
    response = send(client, "prepare", config=config)
    assert response.status_code == 201, response.text
    return response.json()


def review(client, parent, drops, version="v2"):
    body = {"version": version, "drop_columns": drops, "source_sha256": parent["sha256"]}
    response = client.post(f"/api/v1/datasets/{parent['id']}/columns/preview", json=body)
    assert response.status_code == 200, response.text
    return {**body, "reviewed_sha256": response.json()["preview_sha256"]}


def save(client, parent, body):
    return client.post(f"/api/v1/datasets/{parent['id']}/columns", json=body)


def rows(record, root):
    return list(csv.DictReader(io.StringIO((root / record["uri"]).read_text())))


@pytest.mark.parametrize("kind", ["numeric", "prepared"])
def test_saved_selection_preserves_every_retained_cell_and_original_version(
    column_client, app, store, tmp_path, kind
):
    parent = numeric(column_client) if kind == "numeric" else prepared(column_client)
    descriptors = column_client.get(f"/api/v1/datasets/{parent['id']}/columns").json()
    drop = descriptors["columns"][0]["name"]
    assert drop == ("feature_1" if kind == "numeric" else "Age years")
    original = (tmp_path / parent["uri"]).read_bytes()
    original_records = len(store.datasets.records)
    body = review(column_client, parent, [drop])
    assert len(store.datasets.records) == original_records
    response = save(column_client, parent, body)
    assert response.status_code == 201, response.text
    child = response.json()
    assert child["id"] != parent["id"]
    assert child["row_counts"] == parent["row_counts"]
    assert child["feature_columns"] == parent["feature_columns"][1:]
    names = [*child["feature_columns"], parent["target_column"], parent["split_column"]]
    assert rows(child, tmp_path) == [
        {key: row[key] for key in names} for row in rows(parent, tmp_path)
    ]
    assert (tmp_path / parent["uri"]).read_bytes() == original
    assert column_client.get(f"/api/v1/datasets/{parent['id']}").json() == parent
    assert save(column_client, parent, body).status_code == 200
    assert save(column_client, parent, body).json() == child
    record = DatasetRecord.model_validate(child)
    recipe = read_preparation(record, app.state.settings)
    if kind == "prepared":
        assert recipe["format_version"] == 2
        assert transform_rows([{"Category": "HIGH"}], recipe) == [[1, 0]]
        assert transform_rows([{"Category": "UNSEEN"}], recipe) == [[0, 0]]
        assert child["preparation"]["source"] == parent["preparation"]["source"]
    else:
        assert recipe is None
    run = ExperimentRecord(
        project_id="demo",
        dataset_id=record.id,
        model_id="model",
        submission_key="selection",
        request_hash="0" * 64,
        config=TrainingConfig(epochs=2),
    )
    result = train_classifier(run, record, "selection", app.state.settings)
    assert "validation_f1" in result.metrics
    import torch

    artifact = next(item for item in result.artifacts if item.name == "model.pt")
    content = (app.state.settings.artifact_root / artifact.uri).read_bytes()
    assert hashlib.sha256(content).hexdigest() == artifact.sha256
    checkpoint = torch.load(io.BytesIO(content), weights_only=True)
    assert checkpoint["feature_columns"] == child["feature_columns"]
    assert checkpoint.get("preparation") == recipe


def test_categorical_group_is_removed_whole_and_target_ids_and_custom_splits_survive(
    column_client, app, tmp_path
):
    config = {
        "name": "custom",
        "version": "v1",
        "target_column": "Outcome",
        "split_column": "partition",
        "label_mapping": {"alpha": 1, "beta": 0},
    }
    source = raw_csv(existing=True)
    preview = send(column_client, content=source, config=config)
    assert preview.status_code == 200
    config["reviewed_sha256"] = preview.json()["preview_sha256"]
    parent = send(column_client, "prepare", content=source, config=config).json()
    child_response = save(column_client, parent, review(column_client, parent, ["Category"]))
    assert child_response.status_code == 201, child_response.text
    child = child_response.json()
    assert child["feature_columns"] == ["feature_0"]
    parent_recipe = read_preparation(DatasetRecord.model_validate(parent), app.state.settings)
    recipe = read_preparation(DatasetRecord.model_validate(child), app.state.settings)
    assert recipe["label_mapping"] == {"alpha": 1, "beta": 0}
    assert recipe["split_sha256"] == parent_recipe["split_sha256"]
    assert recipe["columns"][0] == parent_recipe["columns"][0]
    assert transform_rows([{"Age years": "5"}], recipe) == [[5]]
    assert rows(child, tmp_path) == [
        {name: row[name] for name in ("feature_0", "target", "split")}
        for row in rows(parent, tmp_path)
    ]


@pytest.mark.parametrize(
    "drops",
    [[], ["target"], ["split"], ["absent"], ["feature_1", "feature_1"], ["feature_1", "feature_2"]],
)
def test_invalid_selection_rejects_at_the_requested_boundary(column_client, store, drops):
    parent = numeric(column_client)
    response = column_client.post(
        f"/api/v1/datasets/{parent['id']}/columns/preview",
        json={
            "version": "v2",
            "source_sha256": parent["sha256"],
            "drop_columns": drops,
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] in {"invalid_column_selection", "validation_error"}
    assert len(store.datasets.records) == 1


def test_changed_review_source_and_existing_destination_are_conflicts(
    column_client, store, tmp_path
):
    parent = numeric(column_client)
    body = review(column_client, parent, ["feature_1"])
    assert save(column_client, parent, {**body, "drop_columns": ["feature_2"]}).status_code == 409
    assert save(column_client, parent, {**body, "source_sha256": "0" * 64}).status_code == 409
    assert len(store.datasets.records) == 1
    assert save(column_client, parent, body).status_code == 201
    assert save(column_client, parent, {**body, "drop_columns": ["feature_2"]}).status_code == 409
    (tmp_path / parent["uri"]).write_bytes(b"changed")
    response = column_client.get(f"/api/v1/datasets/{parent['id']}/columns")
    assert (
        response.status_code == 409 and response.json()["error"]["code"] == "dataset_file_conflict"
    )


def test_save_replay_survives_lost_ack_and_parent_removal(column_client, store, monkeypatch):
    parent = prepared(column_client)
    body = review(column_client, parent, ["Category"])
    admit = store.datasets.admit

    async def lose_ack(*args, **kwargs):
        await admit(*args, **kwargs)
        raise AutoReconnect("lost acknowledgement")

    monkeypatch.setattr(store.datasets, "admit", lose_ack)
    assert save(column_client, parent, body).status_code == 503
    assert len(store.datasets.records) == 2
    store.datasets.records.pop(parent["id"])
    response = save(column_client, parent, body)
    assert response.status_code == 200, response.text
    assert response.json()["selection"]["parent_id"] == parent["id"]
    assert len(store.datasets.records) == 1


def test_upload_exclusions_work_before_failing_encoding_and_preserve_bounds(column_client):
    source = raw_csv().decode().splitlines()
    changed = [source[0].replace("Outcome", "Missing,Identifier,Outcome")]
    changed += [
        line.rsplit(",", 1)[0] + f",,id_{i}," + line.rsplit(",", 1)[1]
        for i, line in enumerate(source[1:])
    ]
    content = ("\n".join(changed) + "\n").encode()
    assert send(column_client, content=content).status_code == 422
    config = {
        "name": "raw",
        "version": "v1",
        "target_column": "Outcome",
        "columns": {
            "Missing": {"treatment": "exclude"},
            "Identifier": {"treatment": "exclude"},
        },
    }
    response = send(column_client, content=content, config=config)
    assert response.status_code == 200, response.text
    config["reviewed_sha256"] = response.json()["preview_sha256"]
    assert send(column_client, "prepare", content=content, config=config).status_code == 201
    assert (
        send(
            column_client, content=content.replace(b"id_0,", b"x" * 129 + b","), config=config
        ).status_code
        == 422
    )


def test_access_scope_and_upload_opt_in(column_client, app):
    parent = numeric(column_client)
    path = f"/api/v1/datasets/{parent['id']}/columns"
    body = review(column_client, parent, ["feature_1"])
    column_client.headers["X-Project-ID"] = "other"
    assert column_client.get(path).status_code == 404
    assert save(column_client, parent, body).status_code == 404
    column_client.headers["X-Project-ID"] = "demo"
    app.state.settings.dataset_upload_enabled = False
    assert column_client.get(path).status_code == 404
    assert save(column_client, parent, body).status_code == 404


def test_column_json_exact_byte_limit_and_one_over(column_client):
    from ml_pipeline_pro.conversation_schemas import REQUEST_BYTES

    parent = numeric(column_client)
    body = json.dumps(
        {"version": "v2", "drop_columns": ["feature_1"], "source_sha256": parent["sha256"]}
    ).encode()
    exact = body + b" " * (REQUEST_BYTES - len(body))
    path = f"/api/v1/datasets/{parent['id']}/columns/preview"
    headers = {"Content-Type": "application/json", "X-Correlation-ID": "columns-cap"}
    assert column_client.post(path, content=exact, headers=headers).status_code == 200
    response = column_client.post(path, content=exact + b" ", headers=headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "column_limit_exceeded"
    assert response.headers["X-Correlation-ID"] == "columns-cap"


def test_projection_manifest_limit_and_deadline_reach_the_guard(column_client, app, monkeypatch):
    parent = prepared(column_client)
    record = DatasetRecord.model_validate(parent)
    body = ColumnEdit(version="v2", drop_columns=["Category"], source_sha256=parent["sha256"])
    result = dataset_columns.project_columns(record, body, app.state.settings)
    monkeypatch.setattr(dataset_columns, "MANIFEST_MAX_BYTES", len(result.manifest))
    assert (
        dataset_columns.project_columns(record, body, app.state.settings).manifest
        == result.manifest
    )
    monkeypatch.setattr(dataset_columns, "MANIFEST_MAX_BYTES", len(result.manifest) - 1)
    with pytest.raises(ApiError, match="metadata"):
        dataset_columns.project_columns(record, body, app.state.settings)
    monkeypatch.setattr(dataset_columns, "MANIFEST_MAX_BYTES", len(result.manifest))
    monkeypatch.setattr(dataset_columns, "PREPARATION_SECONDS", -1)
    with pytest.raises(TimeoutError):
        dataset_columns.project_columns(record, body, app.state.settings)


def test_v2_manifest_tamper_is_rejected_at_worker_boundary(column_client, app, tmp_path):
    parent = prepared(column_client)
    child = save(column_client, parent, review(column_client, parent, ["Age years"])).json()
    record = DatasetRecord.model_validate(child)
    recipe = read_preparation(record, app.state.settings)
    recipe["columns"][1]["categories"] = ["tampered"]
    content = json.dumps(recipe).encode()
    path = tmp_path / record.preparation.manifest.uri
    path.write_bytes(content)
    record.preparation.manifest.sha256 = hashlib.sha256(content).hexdigest()
    record.preparation.manifest.size_bytes = len(content)
    from ml_pipeline_pro.datasets import DatasetValidationError

    with pytest.raises(DatasetValidationError, match="metadata"):
        read_preparation(record, app.state.settings)


def test_lifecycle_generation_change_refuses_registration(column_client, store, monkeypatch):
    parent = numeric(column_client)
    body = review(column_client, parent, ["feature_1"])
    count = 0

    async def generation(project):
        nonlocal count
        count += 1
        return count

    monkeypatch.setattr(store.lifecycle, "generation", generation)
    response = save(column_client, parent, body)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "deletion_in_progress"
    assert len(store.datasets.records) == 1


def test_repeated_prepared_edits_keep_frozen_custom_mapping_and_split_membership(
    column_client, app, tmp_path
):
    lines = raw_csv(existing=True).decode().splitlines()
    source = (
        "\n".join(["Extra," + lines[0], *("7," + line for line in lines[1:])]) + "\n"
    ).encode()
    config = {
        "name": "repeated",
        "version": "v1",
        "target_column": "Outcome",
        "split_column": "partition",
        "impute_missing": True,
        "label_mapping": {"alpha": 1, "beta": 0},
        "columns": {
            "Category": {
                "treatment": "mapping",
                "mapping": {"HIGH": 7, "LOW": -2},
                "unknown_value": 3,
            }
        },
    }
    response = send(column_client, content=source, config=config)
    assert response.status_code == 200, response.text
    config["reviewed_sha256"] = response.json()["preview_sha256"]
    parent = send(column_client, "prepare", content=source, config=config).json()
    first_response = save(column_client, parent, review(column_client, parent, ["Extra"]))
    assert first_response.status_code == 201, first_response.text
    first = first_response.json()
    second_response = save(column_client, first, review(column_client, first, ["Age years"], "v3"))
    assert second_response.status_code == 201, second_response.text
    second = second_response.json()
    recipe = read_preparation(DatasetRecord.model_validate(second), app.state.settings)
    original = read_preparation(DatasetRecord.model_validate(parent), app.state.settings)
    assert recipe["columns"][2] == original["columns"][2]
    assert recipe["label_mapping"] == original["label_mapping"]
    assert recipe["split_sha256"] == original["split_sha256"]
    assert transform_rows([{"Category": "HIGH"}, {"Category": "UNSEEN"}], recipe) == [[7], [3]]
    assert rows(second, tmp_path) == [
        {name: row[name] for name in [*second["feature_columns"], "target", "split"]}
        for row in rows(parent, tmp_path)
    ]
