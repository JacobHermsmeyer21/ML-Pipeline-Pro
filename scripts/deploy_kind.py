"""Create an isolated single-node test cluster and exercise the actual deployment."""

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", default="kind")
    parser.add_argument("--kubectl", default="kubectl")
    parser.add_argument("--name", default="mlpp-demo-" + uuid4().hex[:8])
    parser.add_argument("--output", type=Path, default=Path("artifacts/kubernetes-validation"))
    parser.add_argument("--port", type=int, default=18000)
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()
    if not args.name.startswith("mlpp-") or not args.name.replace("-", "").isalnum():
        parser.error("Use an explicitly named mlpp-* test cluster")
    if not 1024 <= args.port <= 65535:
        parser.error("port must be 1024..65535")
    args.output.mkdir(parents=True, exist_ok=True)
    kubeconfig = args.output.resolve() / "kubeconfig"
    created = False
    forwarded = None

    def command(parts, name):
        with (args.output / (name + ".log")).open("w", encoding="utf-8") as log:
            subprocess.run(parts, stdout=log, stderr=subprocess.STDOUT, check=True)

    kubectl = [args.kubectl, "--kubeconfig", str(kubeconfig), "--context", "kind-" + args.name]
    try:
        # kind rejects an occupied name; never delete an existing cluster to make room.
        command(
            [
                args.kind,
                "create",
                "cluster",
                "--name",
                args.name,
                "--kubeconfig",
                str(kubeconfig),
                "--wait",
                "120s",
            ],
            "create",
        )
        created = True
        command(
            [args.kind, "load", "docker-image", "ml-pipeline-pro:midterm", "--name", args.name],
            "load",
        )
        command([*kubectl, "apply", "-f", "deploy/kubernetes/stack.json"], "apply")
        manifest = json.loads(Path("deploy/kubernetes/stack.json").read_text())
        for item in manifest["items"]:
            if item["kind"] == "Deployment":
                name = item["metadata"]["name"]
                command(
                    [
                        *kubectl,
                        "-n",
                        "mlpp-demo",
                        "rollout",
                        "status",
                        "deployment/" + name,
                        "--timeout=180s",
                    ],
                    "rollout-" + name,
                )
        command([*kubectl, "-n", "mlpp-demo", "get", "pods", "-o", "json"], "pods")
        pods = json.loads((args.output / "pods.log").read_text())
        assert (
            len([pod for pod in pods["items"] if pod["metadata"]["labels"]["app"] == "model-api"])
            == 2
        )
        assert (
            len([pod for pod in pods["items"] if pod["metadata"]["labels"]["app"] == "worker"]) == 1
        )
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", args.port))
        with (args.output / "forward.log").open("w", encoding="utf-8") as log:
            forwarded = subprocess.Popen(
                [
                    *kubectl,
                    "-n",
                    "mlpp-demo",
                    "port-forward",
                    "service/gateway",
                    f"{args.port}:8000",
                    "--address",
                    "127.0.0.1",
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            origin = f"http://127.0.0.1:{args.port}"
            for _ in range(30):
                if forwarded.poll() is not None:
                    raise RuntimeError("Isolated port forward exited")
                try:
                    response = httpx.get(origin + "/api/v1/health/ready", timeout=2)
                    if response.status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                time.sleep(1)
            else:
                raise TimeoutError("Gateway did not become ready")
            command(
                [
                    sys.executable,
                    "scripts/deployment_smoke.py",
                    "--origin",
                    origin,
                    "--output",
                    str(args.output / "smoke.json"),
                ],
                "smoke",
            )
            command(
                [
                    sys.executable,
                    "scripts/check_api_replicas.py",
                    "--kubeconfig",
                    str(kubeconfig),
                    "--name",
                    args.name,
                    "--smoke",
                    str(args.output / "smoke.json"),
                    "--output",
                    str(args.output / "replicas"),
                ],
                "replicas",
            )
        report = {
            "cluster": args.name,
            "namespace": "mlpp-demo",
            "model_api_replicas": 2,
            "worker_replicas": 1,
            "worker_concurrency": 1,
            "smoke": "passed",
            "images": [
                {
                    "pod": pod["metadata"]["name"],
                    "image": status["image"],
                    "image_id": status.get("imageID"),
                }
                for pod in pods["items"]
                for status in pod["status"].get("containerStatuses", [])
            ],
        }
        (args.output / "results.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        print(
            "Kubernetes rollout and three-domain smoke passed; two model APIs, one serial worker."
        )
    except Exception:
        # Retain the failing boundary before optional cleanup removes the cluster.
        # These reads exclude Secret values and kubeconfig credentials.
        if created:
            diagnostics = [
                ("pods", ["get", "pods", "-o", "wide"]),
                ("events", ["get", "events", "--sort-by=.metadata.creationTimestamp"]),
                *[
                    (name, ["logs", "deployment/" + name, "--tail=60"])
                    for name in ("mongo", "model-api", "worker", "gateway")
                ],
            ]
            for name, parts in diagnostics:
                with (args.output / ("failure-" + name + ".log")).open(
                    "w", encoding="utf-8"
                ) as log:
                    try:
                        subprocess.run(
                            [*kubectl, "-n", "mlpp-demo", *parts],
                            stdout=log,
                            stderr=subprocess.STDOUT,
                            timeout=15,
                            check=False,
                        )
                    except (OSError, subprocess.TimeoutExpired) as exc:
                        log.write("Diagnostic unavailable: " + type(exc).__name__ + "\n")
        raise
    finally:
        if forwarded is not None:
            forwarded.terminate()
            forwarded.wait(timeout=10)
        if created and args.cleanup:
            command([args.kind, "delete", "cluster", "--name", args.name], "cleanup")


if __name__ == "__main__":
    main()
