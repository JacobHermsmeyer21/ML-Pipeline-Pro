"""Exercise the rendered laptop nginx with failed DNS and refused upstream TCP."""

import argparse
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx

from ml_pipeline_pro.laptop_deployment import render_laptop_profile


def check(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    render_laptop_profile(root, output / "profile")
    identity = "mlpp-gateway-check-" + uuid4().hex[:12]
    image = "nginx:1.28-alpine"
    containers = []
    network = None
    report = {
        "started_utc": datetime.now(UTC).isoformat(),
        "image": image,
        "network_name": identity,
        "phases": [],
        "model_calls": 0,
        "scope": "Only nginx and a sleeping nginx-image process; no domain/model runtime.",
    }

    def command(parts):
        return subprocess.check_output(parts, text=True, stderr=subprocess.STDOUT, timeout=40)

    def create(parts):
        container = command(["docker", "create", "--pull=never", *parts]).strip()
        containers.append(container)
        command(["docker", "start", container])
        return container

    try:
        report["image_id"] = json.loads(command(["docker", "image", "inspect", image]))[0]["Id"]
        network = command(["docker", "network", "create", identity]).strip()
        gateway = create(
            [
                "--name",
                identity + "-gateway",
                "--network",
                identity,
                "--publish",
                "127.0.0.1::8000",
                "--mount",
                f"type=bind,source={(output / 'profile/gateway.conf').resolve()},"
                "target=/etc/nginx/nginx.conf,readonly",
                image,
            ]
        )
        port = command(["docker", "port", gateway, "8000/tcp"]).strip().split(":")[-1]
        with httpx.Client(
            base_url="http://127.0.0.1:" + port,
            trust_env=False,
            follow_redirects=False,
            timeout=40,
            headers={"X-Correlation-ID": "laptop-gateway-check"},
        ) as client:
            for _ in range(30):
                try:
                    response = client.get("/gateway-live", timeout=2)
                    response.raise_for_status()
                    break
                except httpx.HTTPError:
                    time.sleep(0.2)
            else:
                raise TimeoutError("Local nginx liveness unavailable")

            def observe(phase):
                started = time.monotonic()
                local = client.get("/gateway-live", timeout=5)
                local.raise_for_status()
                assert local.json() == {"status": "alive"}
                assert local.headers["X-Correlation-ID"] == "laptop-gateway-check"
                local_seconds = time.monotonic() - started
                statuses = {}
                for path in ["/api/v1/health/ready", "/api/v1/health/live", "/gateway-live/"]:
                    response = client.get(path)
                    assert response.status_code == 503
                    error = response.json()["error"]
                    assert error["code"] == "service_unavailable"
                    assert error["correlation_id"] == response.headers["X-Correlation-ID"]
                    assert error["correlation_id"] == "laptop-gateway-check"
                    statuses[path] = response.status_code
                invalid = client.get("/gateway-live", headers={"X-Correlation-ID": "invalid:input"})
                assert invalid.status_code == 200
                assert invalid.headers["X-Correlation-ID"] != "invalid:input"
                report["phases"].append(
                    {
                        "phase": phase,
                        "local_status": local.status_code,
                        "local_elapsed_seconds": local_seconds,
                        "upstream_statuses": statuses,
                        "correlation_headers_verified": True,
                    }
                )

            observe("upstream_dns_unavailable")
            logs = command(["docker", "logs", gateway])
            assert "could not be resolved" in logs
            (output / "dns-failure.log").write_text(logs, encoding="utf-8")
            create(
                [
                    "--name",
                    identity + "-backend",
                    "--network",
                    identity,
                    "--network-alias",
                    "model-api",
                    "--entrypoint",
                    "sleep",
                    image,
                    "300",
                ]
            )
            # Let the actual configured five-second DNS cache expire before TCP evidence.
            time.sleep(6)
            observe("upstream_tcp_refused")
            logs = command(["docker", "logs", gateway])
            assert "connect() failed" in logs and "Connection refused" in logs
            (output / "tcp-failure.log").write_text(logs, encoding="utf-8")
        report["passed"] = True
        return report
    except Exception as exc:
        report["failure_type"] = type(exc).__name__
        for index, container in enumerate(containers):
            (output / f"failure-container-{index}.log").write_text(
                command(["docker", "logs", container]), encoding="utf-8"
            )
            inspected = json.loads(command(["docker", "inspect", container]))[0]
            (output / f"failure-container-{index}.json").write_text(
                json.dumps(
                    {"state": inspected["State"], "ports": inspected["NetworkSettings"]["Ports"]},
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        raise
    finally:
        report["ended_utc"] = datetime.now(UTC).isoformat()
        (output / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        for container in reversed(containers):
            command(["docker", "rm", "--force", container])
        if network is not None:
            command(["docker", "network", "rm", network])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/laptop-gateway-check"))
    args = parser.parse_args()
    print(json.dumps(check(args.output), indent=2))
