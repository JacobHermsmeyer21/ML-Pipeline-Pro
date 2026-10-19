import hashlib
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from tests.integration.helpers import api_base_url
from tests.integration.test_experiments import cleanup

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("MLPP_RUN_INTEGRATION") != "1", reason="Requires real MongoDB and Redis"
    ),
]
CSV = Path("examples/data/classification.csv").read_bytes()
PARAMS = [
    ("name", "uploaded"),
    ("version", "v1"),
    ("feature_columns", "feature_1"),
    ("feature_columns", "feature_2"),
]


@pytest.mark.skipif(
    os.getenv("MLPP_RUN_WORKER_INTEGRATION") != "1", reason="Requires queued worker integration"
)
def test_concurrent_csv_upload_is_scoped_replayable_and_readable_by_serial_worker():
    project = "upload_" + uuid4().hex

    def upload():
        with httpx.Client(base_url=api_base_url(), timeout=30) as client:
            return client.post(
                "/datasets/upload",
                params=PARAMS,
                content=CSV,
                headers={"X-Project-ID": project, "Content-Type": "text/csv"},
            )

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: upload(), range(2)))
        assert sorted(item.status_code for item in responses) == [200, 201], [
            r.text for r in responses
        ]
        record = responses[0].json()
        assert responses[1].json() == record
        assert record["sha256"] == hashlib.sha256(CSV).hexdigest()
        assert record["row_counts"] == {"train": 80, "validation": 20, "test": 20}
        with httpx.Client(
            base_url=api_base_url(), headers={"X-Project-ID": project}, timeout=30
        ) as client:
            changed = client.post(
                "/datasets/upload",
                params=PARAMS,
                content=CSV.replace(b"feature_1,feature_2", b"feature_2,feature_1"),
                headers={"Content-Type": "text/csv"},
            )
            assert changed.status_code == 409
            stolen = client.post(
                "/datasets",
                headers={"X-Project-ID": project + "_other"},
                json={
                    "name": "stolen",
                    "version": "v1",
                    "uri": record["uri"],
                    "feature_columns": ["feature_1", "feature_2"],
                },
            )
            assert stolen.status_code == 404
            model = client.post("/models", json={"name": "uploaded_classifier"})
            assert model.status_code == 201
            body = {
                "dataset_id": record["id"],
                "model_id": model.json()["id"],
                "config": {"epochs": 5, "max_runtime_seconds": 20},
            }
            first = client.post(
                "/experiments", json=body, headers={"Idempotency-Key": "uploaded-training"}
            )
            assert first.status_code == 202
            identity = first.json()["id"]
            replay = client.post(
                "/experiments", json=body, headers={"Idempotency-Key": "uploaded-training"}
            )
            assert replay.json()["id"] == identity
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                run = client.get("/experiments/" + identity).json()
                if run["status"] not in {"queued", "running"}:
                    break
                time.sleep(0.3)
            assert run["status"] == "succeeded", run
            assert "validation_f1" in run["metrics"]
            for artifact in run["artifacts"]:
                downloaded = client.get(f"/experiments/{identity}/artifacts/{artifact['name']}")
                assert downloaded.status_code == 200
                assert len(downloaded.content) == artifact["size_bytes"]
                assert hashlib.sha256(downloaded.content).hexdigest() == artifact["sha256"]
    finally:
        cleanup(project)
        cleanup(project + "_other")


def test_actual_gateway_upload_byte_boundary_and_correlated_errors():
    project = "upload_limit_" + uuid4().hex
    exact = CSV + b"\n" * (10_000_000 - len(CSV))
    try:
        with httpx.Client(
            base_url=api_base_url(),
            headers={
                "X-Project-ID": project,
                "Content-Type": "text/csv",
                "X-Correlation-ID": "upload-real-limit",
            },
            timeout=45,
        ) as client:
            accepted = client.post("/datasets/upload", params=PARAMS, content=exact)
            assert accepted.status_code == 201, accepted.text
            assert accepted.json()["sha256"] == hashlib.sha256(exact).hexdigest()
            rejected = client.post("/datasets/upload", params=PARAMS, content=exact + b"\n")
            assert rejected.status_code == 413, rejected.text
            assert rejected.headers["X-Correlation-ID"] == "upload-real-limit"
            assert rejected.json()["error"]["correlation_id"] == "upload-real-limit"
    finally:
        cleanup(project)
