import asyncio
import hashlib
import io
import json
import threading
from types import SimpleNamespace

import pytest
from fastapi import Response
from pydantic import SecretStr
from pymongo.errors import AutoReconnect

from ml_pipeline_pro import preparation_api
from ml_pipeline_pro.preparation_files import read_preparation
from ml_pipeline_pro.schemas import DatasetRecord, ExperimentRecord, TrainingConfig
from ml_pipeline_pro.training import train_classifier
from tests.test_dataset_preparation import raw_csv


@pytest.fixture
def preparation_client(tracking_client, app, tmp_path):
    app.state.settings.dataset_upload_enabled = True
    app.state.settings.dataset_root = tmp_path
    app.state.settings.artifact_root = tmp_path / "artifacts"
    return tracking_client


def send(client, endpoint="preview", *, content=None, config=None, **kwargs):
    return client.post(
        "/api/v1/datasets/" + endpoint,
        files={
            "file": ("raw.csv", raw_csv() if content is None else content, "text/csv"),
            "settings": (
                None,
                json.dumps(config or {"name": "raw", "version": "v1", "target_column": "Outcome"}),
            ),
        },
        headers={"X-Correlation-ID": "prepare-test"},
        **kwargs,
    )


def reviewed(client, **overrides):
    config = {"name": "raw", "version": "v1", "target_column": "Outcome", **overrides}
    preview = send(client, config=config)
    assert preview.status_code == 200, preview.text
    config["reviewed_sha256"] = preview.json()["preview_sha256"]
    return config


def test_preview_requires_no_registration_and_stale_encoding_cannot_be_saved(
    preparation_client, store, tmp_path
):
    config = reviewed(preparation_client)
    assert not store.datasets.records and not list(tmp_path.rglob("*.*"))
    config["columns"] = {"Category": {"treatment": "exclude"}}
    stale = send(preparation_client, "prepare", config=config)
    assert (
        stale.status_code == 409 and stale.json()["error"]["code"] == "preparation_review_required"
    )
    assert not store.datasets.records
    # Native coordination files must remain stable; rejected preparation still
    # leaves no source, canonical, manifest or private staging data behind.
    files = [path for path in tmp_path.rglob("*") if path.is_file()]
    assert files == [tmp_path / "artifacts/.control/demo/publication.lock"]
    assert files[0].stat().st_size == 0


def test_reviewed_preparation_is_immutable_replayable_and_trains_with_saved_transform(
    preparation_client, app, tmp_path
):
    config = reviewed(
        preparation_client,
        columns={"Category": {"treatment": "mapping", "mapping": {"HIGH": 7, "LOW": -2}}},
        label_mapping={"alpha": 1, "beta": 0},
    )
    response = send(preparation_client, "prepare", config=config)
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved["row_counts"] == {"train": 140, "validation": 30, "test": 30}
    assert saved["preparation"]["source"]["sha256"] == hashlib.sha256(raw_csv()).hexdigest()
    assert send(preparation_client, "prepare", config=config).json() == saved
    assert send(preparation_client, "prepare", config=config).status_code == 200
    dataset = DatasetRecord.model_validate(saved)
    recipe = read_preparation(dataset, app.state.settings)
    assert recipe["label_mapping"] == {"alpha": 1, "beta": 0}
    run = ExperimentRecord(
        project_id="demo",
        dataset_id=dataset.id,
        model_id="model",
        submission_key="test",
        request_hash="0" * 64,
        config=TrainingConfig(epochs=2),
    )
    result = train_classifier(run, dataset, "prepared", app.state.settings)
    import torch

    checkpoint = torch.load(
        io.BytesIO((tmp_path / "artifacts" / result.artifacts[0].uri).read_bytes()),
        weights_only=True,
    )
    assert checkpoint["preparation"] == recipe
    assert "validation_f1" in result.metrics
    assert not list(tmp_path.rglob("staging_*"))


def test_recipe_changes_conflict_even_when_prepared_output_matches(preparation_client):
    first = reviewed(preparation_client)
    assert send(preparation_client, "prepare", config=first).status_code == 201
    explicit = reviewed(preparation_client, columns={"Category": {"treatment": "one_hot"}})
    assert send(preparation_client, "prepare", config=explicit).status_code == 409


def test_preparation_disabled_auth_and_project_scope(preparation_client, app):
    app.state.settings.dataset_upload_enabled = False
    assert send(preparation_client).status_code == 404
    app.state.settings.dataset_upload_enabled = True
    saved = send(preparation_client, "prepare", config=reviewed(preparation_client)).json()
    preparation_client.headers["X-Project-ID"] = "other"
    assert preparation_client.get("/api/v1/datasets/" + saved["id"]).status_code == 404
    app.state.settings.project_api_keys = {"other": SecretStr("test-secret-key-long-enough")}
    assert send(preparation_client).status_code == 403


def test_ambiguous_insert_retains_published_files_for_same_request_recovery(
    preparation_client, store, tmp_path, monkeypatch
):
    config = reviewed(preparation_client)
    insert = store.datasets.insert

    async def lose_ack(record):
        await insert(record)
        raise AutoReconnect("lost acknowledgement")

    monkeypatch.setattr(store.datasets, "insert", lose_ack)
    assert send(preparation_client, "prepare", config=config).status_code == 503
    assert len(list(tmp_path.rglob("*.csv"))) == 2
    assert len(list(tmp_path.rglob("*.preparation.json"))) == 1
    assert not list(tmp_path.rglob("staging_*"))
    assert send(preparation_client, "prepare", config=config).status_code == 200


def test_actual_raw_settings_and_envelope_caps(preparation_client, app, monkeypatch):
    # Padding keeps canonical output below the raw cap, reaching raw reception.
    source = raw_csv() + b"\n" * 5000
    app.state.settings.dataset_max_bytes = len(source)
    assert send(preparation_client, content=source).status_code == 200
    assert send(preparation_client, content=source + b"\n").status_code == 413
    app.state.settings.dataset_max_bytes = 10_000_000
    exact = json.dumps({"name": "raw", "version": "v1", "target_column": "Outcome"})
    monkeypatch.setattr(preparation_api, "SETTINGS_MAX_BYTES", len(exact.encode()))
    assert send(preparation_client).status_code == 200
    monkeypatch.setattr(preparation_api, "SETTINGS_MAX_BYTES", len(exact.encode()) - 1)
    assert send(preparation_client).status_code == 413
    # Independently reach the receive guard, without trusting a false length header.
    response = preparation_client.post(
        "/api/v1/datasets/preview",
        headers={"Content-Type": "multipart/form-data; boundary=x", "Content-Length": "1"},
        content=iter([b"x" * 10_065_537]),
    )
    assert response.status_code == 413


def test_truncated_duplicate_and_unknown_parts_and_invalid_json_are_rejected(
    preparation_client, tmp_path
):
    for body in [
        b'--x\r\nContent-Disposition: form-data; name="file"\r\n\r\nraw',
        b'--x\r\nContent-Disposition: form-data; name="extra"\r\n\r\nraw\r\n--x--\r\n',
    ]:
        result = preparation_client.post(
            "/api/v1/datasets/preview",
            headers={"Content-Type": "multipart/form-data; boundary=x"},
            content=body,
        )
        assert result.status_code == 422, result.text
    duplicate = preparation_client.post(
        "/api/v1/datasets/preview",
        files=[("file", ("a.csv", raw_csv())), ("file", ("b.csv", raw_csv()))],
    )
    assert duplicate.status_code == 422
    assert (
        preparation_client.post(
            "/api/v1/datasets/preview",
            files={"file": ("a.csv", raw_csv()), "settings": (None, '{"name":"a","name":"b"}')},
        ).status_code
        == 422
    )
    assert not list(tmp_path.rglob("staging_*"))


def test_source_and_manifest_tampering_are_detected(preparation_client, app, tmp_path):
    config = reviewed(preparation_client)
    saved = DatasetRecord.model_validate(send(preparation_client, "prepare", config=config).json())
    source = tmp_path / saved.preparation.source.uri
    source.write_bytes(source.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="verification"):
        read_preparation(saved, app.state.settings)
    source.write_bytes(raw_csv())
    manifest = tmp_path / saved.preparation.manifest.uri
    manifest.write_bytes(manifest.read_bytes().replace(b"one_hot", b"numeric"))
    with pytest.raises(ValueError, match="verification"):
        read_preparation(saved, app.state.settings)


def test_wrong_media_type_is_explicit(preparation_client):
    assert preparation_client.post("/api/v1/datasets/preview", content=b"raw").status_code == 415


def test_multipart_overhead_cap_and_preparation_deadline(preparation_client, monkeypatch):
    import httpx

    settings = json.dumps({"name": "raw", "version": "v1", "target_column": "Outcome"})
    source = raw_csv()
    request = httpx.Request(
        "POST",
        "http://test/api/v1/datasets/preview",
        files={"file": ("original.csv", source), "settings": (None, settings)},
    )
    content = request.read()
    overhead = len(content) - len(source) - len(settings.encode())
    monkeypatch.setattr(preparation_api, "OVERHEAD_MAX_BYTES", overhead)
    assert (
        preparation_client.post(
            "/api/v1/datasets/preview",
            content=content,
            headers={"Content-Type": request.headers["content-type"]},
        ).status_code
        == 200
    )
    monkeypatch.setattr(preparation_api, "OVERHEAD_MAX_BYTES", overhead - 1)
    assert (
        preparation_client.post(
            "/api/v1/datasets/preview",
            content=content,
            headers={"Content-Type": request.headers["content-type"]},
        ).status_code
        == 413
    )
    monkeypatch.setattr(preparation_api, "OVERHEAD_MAX_BYTES", overhead)
    monkeypatch.setattr(preparation_api, "PREPARATION_SECONDS", -1)
    assert send(preparation_client).status_code == 408


@pytest.mark.parametrize("cancellations", [1, 2])
def test_cancelled_multipart_parse_finishes_before_staging_cleanup(
    app, store, tmp_path, monkeypatch, cancellations
):
    import httpx

    app.state.settings.dataset_root = tmp_path
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original_parse = preparation_api.parse_multipart
    observed_paths = []

    def blocking_parse(envelope, raw, *args):
        observed_paths.extend([envelope, raw])
        entered.set()
        assert release.wait(5)
        assert envelope.is_file() and raw.is_file()
        result = original_parse(envelope, raw, *args)
        finished.set()
        return result

    monkeypatch.setattr(preparation_api, "parse_multipart", blocking_parse)
    request = httpx.Request(
        "POST",
        "http://test",
        files={
            "file": ("a.csv", raw_csv()),
            "settings": (
                None,
                json.dumps({"name": "raw", "version": "v1", "target_column": "Outcome"}),
            ),
        },
    )
    content = request.read()

    async def stream():
        yield content

    async def scenario():
        task = asyncio.create_task(
            preparation_api._prepare(
                SimpleNamespace(app=app, headers=request.headers, stream=stream),
                "demo",
                store,
                Response(),
                register=False,
            )
        )
        assert await asyncio.to_thread(entered.wait, 5)
        try:
            for _ in range(cancellations):
                task.cancel()
                await asyncio.sleep(0.01)
                assert not task.done() and all(path.is_file() for path in observed_paths)
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert finished.is_set()

    asyncio.run(scenario())
    assert not list(tmp_path.rglob("staging_*"))
