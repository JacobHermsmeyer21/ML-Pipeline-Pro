import hashlib
import io
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import httpx
import pytest

from tests.integration.helpers import api_base_url
from tests.integration.test_experiments import cleanup
from tests.test_dataset_preparation import raw_csv

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("MLPP_RUN_INTEGRATION") != "1", reason="Requires real services"),
]


def upload(client, endpoint, source, settings):
    return client.post(
        "/datasets/" + endpoint,
        files={
            "file": ("original.csv", source, "text/csv"),
            "settings": (None, json.dumps(settings)),
        },
    )


@pytest.mark.skipif(
    os.getenv("MLPP_RUN_WORKER_INTEGRATION") != "1", reason="Requires serial worker"
)
def test_reviewed_raw_preparation_replays_concurrently_and_trains_with_verified_provenance():
    project = "prepare_" + uuid4().hex
    source = raw_csv()
    config = {
        "name": "raw",
        "version": "v1",
        "target_column": "Outcome",
        "columns": {"Category": {"treatment": "mapping", "mapping": {"HIGH": 5, "LOW": -1}}},
        "label_mapping": {"alpha": 1, "beta": 0},
    }
    try:
        with httpx.Client(
            base_url=api_base_url(), headers={"X-Project-ID": project}, timeout=90
        ) as client:
            preview = upload(client, "preview", source, config)
            assert preview.status_code == 200, preview.text
            config["reviewed_sha256"] = preview.json()["preview_sha256"]

            def prepare():
                with httpx.Client(
                    base_url=api_base_url(), headers={"X-Project-ID": project}, timeout=90
                ) as other:
                    return upload(other, "prepare", source, config)

            with ThreadPoolExecutor(max_workers=2) as pool:
                responses = list(pool.map(lambda _: prepare(), range(2)))
            assert sorted(r.status_code for r in responses) == [200, 201], [
                r.text for r in responses
            ]
            saved = responses[0].json()
            assert responses[1].json() == saved
            assert saved["preparation"]["source"]["sha256"] == hashlib.sha256(source).hexdigest()
            assert saved["row_counts"] == {"train": 140, "validation": 30, "test": 30}
            assert client.get("/datasets").json()["items"] == [saved]
            model_response = client.post("/models", json={"name": "prepared_classifier"})
            assert model_response.status_code == 201, model_response.text
            model = model_response.json()
            body = {"dataset_id": saved["id"], "model_id": model["id"], "config": {"epochs": 3}}
            submitted = client.post(
                "/experiments", json=body, headers={"Idempotency-Key": "prepared-training"}
            )
            assert submitted.status_code == 202, submitted.text
            identity = submitted.json()["id"]
            replay = client.post(
                "/experiments", json=body, headers={"Idempotency-Key": "prepared-training"}
            )
            assert replay.json()["id"] == identity
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                run = client.get("/experiments/" + identity).json()
                if run["status"] not in {"queued", "running"}:
                    break
                time.sleep(0.2)
            assert run["status"] == "succeeded", run
            contents = {}
            for artifact in run["artifacts"]:
                response = client.get(f"/experiments/{identity}/artifacts/{artifact['name']}")
                assert response.status_code == 200
                assert len(response.content) == artifact["size_bytes"]
                assert hashlib.sha256(response.content).hexdigest() == artifact["sha256"]
                contents[artifact["name"]] = response.content
            recipe = json.loads(contents["manifest.json"])["preparation"]
            assert recipe["columns"][1]["mapping"] == {"HIGH": 5, "LOW": -1}
            assert recipe["label_mapping"] == {"alpha": 1, "beta": 0}
            import torch

            assert (
                torch.load(io.BytesIO(contents["model.pt"]), weights_only=True)["preparation"]
                == recipe
            )
            denied = client.get(
                "/datasets/" + saved["id"], headers={"X-Project-ID": project + "_other"}
            )
            assert denied.status_code == 404
    finally:
        cleanup(project)


def test_real_gateway_raw_byte_cap_and_stale_review():
    project = "prepare_limit_" + uuid4().hex
    config = {"name": "raw", "version": "v1", "target_column": "Outcome"}
    source = raw_csv()
    exact = source + b"\n" * (10_000_000 - len(source))
    try:
        with httpx.Client(
            base_url=api_base_url(),
            headers={"X-Project-ID": project, "X-Correlation-ID": "preparation-real-cap"},
            timeout=90,
        ) as client:
            accepted = upload(client, "preview", exact, config)
            assert accepted.status_code == 200, accepted.text
            rejected = upload(client, "preview", exact + b"\n", config)
            assert rejected.status_code == 413, rejected.text
            assert rejected.json()["error"]["correlation_id"] == "preparation-real-cap"
            assert rejected.headers["X-Correlation-ID"] == "preparation-real-cap"
            config["reviewed_sha256"] = accepted.json()["preview_sha256"]
            config["seed"] = 99
            stale = upload(client, "prepare", exact, config)
            assert (
                stale.status_code == 409
                and stale.json()["error"]["code"] == "preparation_review_required"
            )
            assert client.get("/datasets").json()["items"] == []
    finally:
        cleanup(project)
