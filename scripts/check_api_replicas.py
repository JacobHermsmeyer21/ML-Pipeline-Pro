"""Force immutable submission replay through each ready model API pod."""

import argparse
import json
import os
import socket
import subprocess
import time
from pathlib import Path

import httpx


def check(kubectl: list[str], smoke: dict, output: Path) -> list[dict]:
    pods = json.loads(
        subprocess.check_output(
            [*kubectl, "-n", "mlpp-demo", "get", "pods", "-l", "app=model-api", "-o", "json"],
            text=True,
        )
    )["items"]
    assert len(pods) == 2
    body = {
        "dataset_id": smoke["dataset"]["id"],
        "model_id": smoke["model"]["id"],
        "config": {"epochs": 5, "max_runtime_seconds": 20},
    }
    identity = smoke["model"]["name"].removeprefix("classifier_")
    headers = {
        "X-Project-ID": smoke["project"],
        "Idempotency-Key": "train_" + identity,
        "X-Correlation-ID": "cross-pod-replay",
    }
    if key := os.getenv("MLPP_API_KEY"):
        headers["X-API-Key"] = key
    observed = []
    output.mkdir(parents=True, exist_ok=True)
    for pod in pods:
        name = pod["metadata"]["name"]
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        with (output / (name + "-forward.log")).open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                [
                    *kubectl,
                    "-n",
                    "mlpp-demo",
                    "port-forward",
                    "pod/" + name,
                    f"{port}:8000",
                    "--address",
                    "127.0.0.1",
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            try:
                with httpx.Client(
                    base_url=f"http://127.0.0.1:{port}",
                    headers=headers,
                    timeout=10,
                    trust_env=False,
                ) as client:
                    for _ in range(30):
                        if process.poll() is not None:
                            raise RuntimeError("Pod-specific forward exited")
                        try:
                            if client.get("/api/v1/health/ready").status_code == 200:
                                break
                        except httpx.TransportError:
                            pass
                        time.sleep(1)
                    else:
                        raise TimeoutError("Individual model API did not become ready")
                    response = client.post("/api/v1/experiments", json=body)
                    response.raise_for_status()
                    assert response.json()["id"] == smoke["training"]["id"]
                    observed.append(
                        {
                            "pod": name,
                            "status": response.status_code,
                            "experiment_id": response.json()["id"],
                        }
                    )
            finally:
                process.terminate()
                process.wait(timeout=10)
    (output / "replicas.json").write_text(json.dumps(observed, indent=2) + "\n", encoding="utf-8")
    return observed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kubeconfig", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--smoke", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    check(
        ["kubectl", "--kubeconfig", args.kubeconfig, "--context", "kind-" + args.name],
        json.loads(args.smoke.read_text()),
        args.output,
    )
    print("Identical submission replayed through both individual model API pods.")
