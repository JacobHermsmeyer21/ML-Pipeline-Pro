import asyncio
import hashlib
import threading
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import SecretStr
from pymongo.errors import AutoReconnect, DuplicateKeyError
from starlette.requests import ClientDisconnect

from ml_pipeline_pro import dataset_uploads
from ml_pipeline_pro.dataset_files import check_dataset_scope, publish_dataset
from ml_pipeline_pro.errors import ApiError

CSV = Path("examples/data/classification.csv").read_bytes()
PARAMS = [
    ("name", "uploaded"),
    ("version", "v1"),
    ("feature_columns", "feature_1"),
    ("feature_columns", "feature_2"),
]


@pytest.fixture
def upload_client(tracking_client, app, tmp_path):
    app.state.settings.dataset_upload_enabled = True
    app.state.settings.dataset_root = tmp_path
    return tracking_client


def send(client, content=CSV, params=PARAMS, **kwargs):
    return client.post(
        "/api/v1/datasets/upload",
        params=params,
        content=content,
        headers={"Content-Type": "text/csv", "X-Correlation-ID": "upload-test", **kwargs},
    )


def test_upload_registers_original_contract_and_same_bytes_replay(upload_client, tmp_path):
    first = send(upload_client)
    assert first.status_code == 201, first.text
    saved = first.json()
    assert saved["row_counts"] == {"train": 80, "validation": 20, "test": 20}
    assert saved["sha256"] == hashlib.sha256(CSV).hexdigest()
    assert (
        datetime.fromisoformat(saved["created_at"].replace("Z", "+00:00")).microsecond % 1000 == 0
    )
    assert saved["uri"] == f"uploads/demo/{saved['sha256']}.csv"
    assert (tmp_path / saved["uri"]).read_bytes() == CSV
    assert send(upload_client).status_code == 200
    assert send(upload_client).json() == saved
    assert not list(tmp_path.rglob("staging_*"))


def test_changed_content_and_metadata_do_not_replace_registered_file(upload_client, tmp_path):
    first = send(upload_client).json()
    different = CSV.replace(b"feature_1,feature_2", b"feature_2,feature_1")
    assert send(upload_client, different).status_code == 409
    duplicate_features = [(k, v) for k, v in PARAMS if k != "feature_columns"]
    duplicate_features += [("feature_columns", "feature_1")]
    assert send(upload_client, params=duplicate_features).status_code == 409
    assert (tmp_path / first["uri"]).read_bytes() == CSV
    assert not list(tmp_path.rglob("staging_*"))


def test_matching_prior_local_registration_is_replayed_without_changing_its_uri(
    upload_client, tmp_path
):
    (tmp_path / "original.csv").write_bytes(CSV)
    original = upload_client.post(
        "/api/v1/datasets",
        json={
            "name": "uploaded",
            "version": "v1",
            "uri": "original.csv",
            "feature_columns": ["feature_1", "feature_2"],
        },
    )
    assert original.status_code == 201
    uploaded = send(upload_client)
    assert uploaded.status_code == 200 and uploaded.json() == original.json()
    (tmp_path / "original.csv").write_bytes(CSV + b"invalid\n")
    assert send(upload_client).status_code == 409


@pytest.mark.parametrize("length_header", [None, "1", "999999999"])
def test_actual_stream_limit_is_enforced_independently_of_declared_length(
    upload_client, app, tmp_path, length_header
):
    app.state.settings.dataset_max_bytes = len(CSV)
    headers = {} if length_header is None else {"Content-Length": length_header}
    assert send(upload_client, iter([CSV[:20], CSV[20:]]), **headers).status_code == 201
    too_large = send(upload_client, iter([CSV, b"\n"]), **headers)
    assert too_large.status_code == 413
    assert too_large.json()["error"]["correlation_id"] == "upload-test"
    assert not list(tmp_path.rglob("staging_*"))


@pytest.mark.parametrize("content", [b"not,csv\n", CSV.replace(b"train", b"other"), b"\xff\xff"])
def test_invalid_csv_never_publishes_a_file(upload_client, tmp_path, content):
    response = send(upload_client, content)
    assert response.status_code == 422
    assert not list(tmp_path.rglob("*.csv"))


def test_conflicting_columns_and_wrong_media_type_are_explicit(upload_client, tmp_path):
    response = send(upload_client, params=PARAMS + [("target_column", "feature_1")])
    assert response.status_code == 422
    assert not list(tmp_path.rglob("*.csv"))
    assert send(upload_client, **{"Content-Type": "application/json"}).status_code == 415


def test_disabled_upload_and_authentication_reject_before_consuming_body(
    tracking_client, app, store, tmp_path
):
    app.state.settings.dataset_root = tmp_path
    assert send(tracking_client).status_code == 404
    app.state.settings.dataset_upload_enabled = True
    app.state.settings.project_api_keys = {"demo": SecretStr("test-secret-key-long-enough")}
    assert send(tracking_client).status_code == 403
    assert not list(tmp_path.rglob("*")) and not store.datasets.records


def test_foreign_projects_cannot_register_uploaded_paths_or_read_records(upload_client, tmp_path):
    saved = send(upload_client).json()
    upload_client.headers["X-Project-ID"] = "other"
    denied = upload_client.post(
        "/api/v1/datasets",
        json={
            "name": "steal",
            "version": "v1",
            "uri": saved["uri"],
            "feature_columns": ["feature_1", "feature_2"],
        },
    )
    assert denied.status_code == 404
    assert upload_client.get("/api/v1/datasets/" + saved["id"]).status_code == 404
    own = send(upload_client)
    assert own.status_code == 201 and own.json()["uri"].startswith("uploads/other/")
    assert own.json()["id"] != saved["id"]


def test_scope_catches_a_symlink_alias(upload_client, app, tmp_path):
    saved = send(upload_client).json()
    alias = tmp_path / "alias.csv"
    alias.symlink_to(tmp_path / saved["uri"])
    with pytest.raises(ApiError) as error:
        check_dataset_scope("alias.csv", "other", app.state.settings)
    assert error.value.status_code == 404


def test_concurrent_publish_never_overwrites_a_matching_blob(tmp_path):
    directory = tmp_path / "demo"
    directory.mkdir()
    digest = hashlib.sha256(CSV).hexdigest()
    paths = [directory / f"stage_{i}.csv" for i in range(2)]
    for path in paths:
        path.write_bytes(CSV)

    async def run():
        return await asyncio.gather(
            *[
                asyncio.to_thread(publish_dataset, path, directory, digest, len(CSV))
                for path in paths
            ]
        )

    assert len(set(asyncio.run(run()))) == 1
    target = directory / f"{digest}.csv"
    assert target.read_bytes() == CSV
    target.write_bytes(b"x" * len(CSV))
    with pytest.raises(ApiError):
        publish_dataset(paths[0], directory, digest, len(CSV))
    assert target.read_bytes() == b"x" * len(CSV)


def test_ambiguous_database_insert_keeps_the_published_file_for_safe_replay(
    upload_client, store, tmp_path, monkeypatch
):
    original = store.datasets.insert

    async def uncertain(record):
        await original(record)
        raise AutoReconnect("lost acknowledgement")

    monkeypatch.setattr(store.datasets, "insert", uncertain)
    response = send(upload_client)
    assert response.status_code == 503
    assert len(store.datasets.records) == 1
    record = next(iter(store.datasets.records.values()))
    assert (tmp_path / record.uri).read_bytes() == CSV
    monkeypatch.setattr(store.datasets, "insert", original)
    assert send(upload_client).json()["id"] == record.id


def test_duplicate_insert_race_resolves_to_the_published_identity(
    upload_client, store, monkeypatch
):
    original = store.datasets.insert

    async def competing(record):
        saved = record.model_copy(update={"id": "other-writer"})
        await original(saved)
        raise DuplicateKeyError("another request won")

    monkeypatch.setattr(store.datasets, "insert", competing)
    response = send(upload_client)
    assert response.status_code == 200 and response.json()["id"] == "other-writer"
    assert len(store.datasets.records) == 1


def test_receive_timeout_and_disconnect_are_distinct_and_bounded(monkeypatch):
    async def slow():
        await asyncio.sleep(1)
        yield b"bytes"

    async def disconnected():
        raise ClientDisconnect()
        yield b""

    monkeypatch.setattr(dataset_uploads, "UPLOAD_RECEIVE_SECONDS", 0.01)

    async def run(stream, expected):
        with pytest.raises(ApiError) as caught:
            await dataset_uploads._receive(
                SimpleNamespace(stream=stream), SimpleNamespace(write=None), 20
            )
        assert caught.value.status_code == expected

    asyncio.run(run(slow, 408))
    asyncio.run(run(disconnected, 400))


@pytest.mark.parametrize("cancellations", [1, 2])
def test_file_io_waits_for_owned_write_before_propagating_cancellation(cancellations):
    began = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    def write():
        began.set()
        release.wait(2)
        finished.set()

    async def run():
        task = asyncio.create_task(dataset_uploads._file_io(write))
        await asyncio.to_thread(began.wait, 2)
        try:
            for _ in range(cancellations):
                task.cancel()
                await asyncio.sleep(0.01)
                assert not task.done()
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert finished.is_set()

    asyncio.run(run())
