"""Measure a saved classifier, declare a seeded delay, and post immutable observations."""

import argparse
import hashlib
import io
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.datasets import load_dataset
from ml_pipeline_pro.schemas import DatasetRecord


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", default="http://127.0.0.1:8000")
    parser.add_argument("--project", default="demo")
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--version-id", required=True)
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--seeded-samples", type=int, default=5)
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/monitoring-demo/workload.json")
    )
    args = parser.parse_args()
    if not 1 <= args.samples <= 100 or not 0 <= args.seeded_samples <= args.samples:
        parser.error("samples must be 1..100 and seeded samples 0..samples")
    headers = {"X-Project-ID": args.project}
    if key := os.getenv("MLPP_API_KEY"):
        headers["X-API-Key"] = key
    with httpx.Client(
        base_url=args.origin, headers=headers, timeout=30, trust_env=False, follow_redirects=False
    ) as client:

        def get(path):
            response = client.get(path)
            response.raise_for_status()
            return response.json()

        version = get(f"/api/v1/models/{args.model_id}/versions/{args.version_id}")
        experiment = get(f"/api/v1/experiments/{version['experiment_id']}")
        assert experiment["status"] == "succeeded" and experiment["test_evaluated"]
        dataset = DatasetRecord.model_validate(get(f"/api/v1/datasets/{experiment['dataset_id']}"))
        loaded = load_dataset(dataset, Settings())
        if loaded.sha256 != dataset.sha256:
            raise ValueError("Dataset changed after registration")
        response = client.get(f"/api/v1/experiments/{experiment['id']}/artifacts/model.pt")
        response.raise_for_status()
        content = response.content
        artifact = version["artifact"]
        if (
            len(content) != artifact["size_bytes"]
            or hashlib.sha256(content).hexdigest() != artifact["sha256"]
        ):
            raise ValueError("Checkpoint hash/size mismatch")
        import torch

        torch.set_num_threads(1)
        checkpoint = torch.load(io.BytesIO(content), weights_only=True)
        model = torch.nn.Sequential(
            torch.nn.Linear(len(dataset.feature_columns), experiment["config"]["hidden_units"]),
            torch.nn.ReLU(),
            torch.nn.Linear(experiment["config"]["hidden_units"], dataset.num_classes),
        )
        model.load_state_dict(checkpoint["state_dict"])
        model.eval()
        # Replay the validation fixture after finalization; no model selection/artifact writes.
        split = loaded.splits["validation"]
        features = (
            torch.tensor(split.features, dtype=torch.float32) - checkpoint["mean"]
        ) / checkpoint["std"]
        with torch.no_grad():
            model(features[:1])  # Warmup excluded from the measured sample timings.
            observations = []
            for index in range(args.samples):
                row = index % len(split.targets)
                seeded = index >= args.samples - args.seeded_samples
                started = time.perf_counter()
                prediction = int(model(features[row : row + 1]).argmax(dim=1).item())
                if seeded:
                    time.sleep(0.15)
                latency = (time.perf_counter() - started) * 1000
                body = {
                    "sample_id": "inference-" + uuid4().hex,
                    "model_version_id": version["id"],
                    "observed_at": datetime.now(UTC).isoformat(),
                    "latency_ms": latency,
                    "prediction_correct": prediction == split.targets[row],
                    "fault": "seeded_latency" if seeded else "none",
                }
                saved = client.post("/api/v1/monitoring/observations", json=body)
                saved.raise_for_status()
                replay = client.post("/api/v1/monitoring/observations", json=body)
                replay.raise_for_status()
                assert replay.json() == saved.json()
                observations.append(saved.json())
    result = {
        "workload": "registered validation fixture replay; finalized checkpoint",
        "artifact_sha256": artifact["sha256"],
        "artifact_size_bytes": artifact["size_bytes"],
        "inference": "CPU, one thread, warmup excluded",
        "injection_seconds": 0.15,
        "observations": observations,
        "same_sample_replay_equal": True,
        "training_artifacts_written": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        f"Recorded {len(observations)} measured inferences; {args.seeded_samples} declared delays."
    )


if __name__ == "__main__":
    main()
