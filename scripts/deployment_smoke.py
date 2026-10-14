"""Real deployment workflow: register, train/tune, inspect artifacts, record monitoring."""

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx


def run(origin: str, project: str) -> dict:
    identity = uuid4().hex[:12]
    headers = {"X-Project-ID": project, "X-Correlation-ID": "deployment-smoke"}
    if key := os.getenv("MLPP_API_KEY"):
        headers["X-API-Key"] = key
    with httpx.Client(
        base_url=origin, headers=headers, timeout=20, trust_env=False, follow_redirects=False
    ) as client:

        def request(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            assert response.headers["X-Correlation-ID"] == "deployment-smoke"
            return response.json()

        for path, own in (
            ("/openapi.json", "/api/v1/experiments"),
            ("/tuning/openapi.json", "/api/v1/tuning-jobs"),
            ("/monitoring/openapi.json", "/api/v1/monitoring/observations"),
        ):
            assert own in request("GET", path)["paths"]
        dataset = request(
            "POST",
            "/api/v1/datasets",
            json={
                "name": "data_" + identity,
                "version": "v1",
                "uri": "classification.csv",
                "feature_columns": ["feature_1", "feature_2"],
            },
        )
        model = request("POST", "/api/v1/models", json={"name": "classifier_" + identity})
        body = {
            "dataset_id": dataset["id"],
            "model_id": model["id"],
            "config": {"epochs": 5, "max_runtime_seconds": 20},
        }
        submission = {"Idempotency-Key": "train_" + identity}
        experiment = request("POST", "/api/v1/experiments", json=body, headers=submission)
        for _ in range(10):
            assert (
                request("POST", "/api/v1/experiments", json=body, headers=submission)["id"]
                == experiment["id"]
            )
        conflict = client.post(
            "/api/v1/experiments", json={**body, "config": {"epochs": 6}}, headers=submission
        )
        assert conflict.status_code == 409

        def wait(path):
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                value = request("GET", path)
                if value["status"] in {"succeeded", "failed", "cancelled"}:
                    assert value["status"] == "succeeded", value.get("error_summary")
                    return value
                time.sleep(1)
            raise TimeoutError("Worker did not finish bounded demo")

        experiment = wait("/api/v1/experiments/" + experiment["id"])
        version = request(
            "POST",
            f"/api/v1/models/{model['id']}/versions",
            json={"version": "v1", "experiment_id": experiment["id"]},
        )
        tuning_body = {
            **body,
            "objective_metric": "validation_f1",
            "limits": {"max_trials": 3, "max_runtime_seconds": 60},
        }
        tuning = request(
            "POST",
            "/api/v1/tuning-jobs",
            json=tuning_body,
            headers={"Idempotency-Key": "tune_" + identity},
        )
        tuning = wait("/api/v1/tuning-jobs/" + tuning["id"])
        trials = request("GET", f"/api/v1/tuning-jobs/{tuning['id']}/trials")
        assert tuning["completed_trials"] == 3 and len(trials["items"]) == 3
        sample = {
            "sample_id": "smoke_" + identity,
            "model_version_id": version["id"],
            "observed_at": datetime.now(UTC).isoformat(),
            "latency_ms": 150,
            "fault": "seeded_latency",
        }
        # A synthetic telemetry fixture for routing, separate from measured inference producer.
        observed = request("POST", "/api/v1/monitoring/observations", json=sample)
        assert request("POST", "/api/v1/monitoring/observations", json=sample) == observed
        summary = request("GET", f"/api/v1/monitoring/model-versions/{version['id']}/summary")
        assert (
            summary["issue"] == "latency_threshold_exceeded" and summary["labeled_accuracy"] is None
        )
        foreign = client.get(
            f"/api/v1/monitoring/model-versions/{version['id']}/summary",
            headers={"X-Project-ID": "foreign"},
        )
        assert foreign.status_code in {403, 404}
        return {
            "origin": origin,
            "project": project,
            "training": experiment,
            "model": model,
            "dataset": dataset,
            "version": version,
            "tuning": tuning,
            "trials": trials,
            "monitoring_summary": summary,
            "telemetry_fixture_synthetic": True,
            "submission_replays": 10,
            "changed_submission_status": conflict.status_code,
            "foreign_status": foreign.status_code,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", default="http://127.0.0.1:8000")
    parser.add_argument("--project", default="demo")
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/deployment-validation/smoke.json")
    )
    args = parser.parse_args()
    result = run(args.origin, args.project)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("Three-domain training/tuning/version/monitoring/replay smoke passed.")
