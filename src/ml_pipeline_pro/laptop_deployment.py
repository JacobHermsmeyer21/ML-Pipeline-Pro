"""Render the opt-in laptop deployment from canonical gateway/AI manifests."""

import json
from pathlib import Path

from ml_pipeline_pro.conversation_timing import DIAGNOSTIC_PROFILE, timing_profile


def render_laptop_profile(
    root: Path, output: Path, *, profile_name: str = "laptop-five-minute"
) -> Path:
    if profile_name not in {"laptop-five-minute", DIAGNOSTIC_PROFILE}:
        raise ValueError("Choose an explicit laptop deployment profile")
    profile = timing_profile(profile_name)
    gateway = (root / "deploy/gateway.conf").read_text(encoding="utf-8")
    original = "proxy_read_timeout 130s;"
    if gateway.count(original) != 1:
        raise ValueError("Canonical gateway timeout changed; review laptop rendering")
    gateway = gateway.replace(original, "proxy_read_timeout 310s;")
    anchor = "        location = /gateway-unavailable {"
    if gateway.count(anchor) != 1:
        raise ValueError("Canonical gateway locations changed; review laptop rendering")
    gateway = gateway.replace(
        anchor,
        "        location = /gateway-live {\n"
        "            default_type application/json;\n"
        '            return 200 \'{"status":"alive"}\';\n'
        "        }\n" + anchor,
    )
    manifest = json.loads((root / "deploy/kubernetes/stack.json").read_text())
    patch = json.loads((root / "deploy/kubernetes/local-ai-patch.json").read_text())
    local = patch["spec"]["template"]["spec"]
    for item in manifest["items"]:
        if item["kind"] == "ConfigMap" and item["metadata"]["name"] == "gateway-config":
            kubernetes_gateway = gateway.replace(
                "resolver 127.0.0.11 valid=5s ipv6=off;",
                "resolver kube-dns.kube-system.svc.cluster.local valid=5s ipv6=off;",
            )
            for domain in ("model-api", "tuning-api", "monitoring-api"):
                kubernetes_gateway = kubernetes_gateway.replace(
                    f"http://{domain}:8000", f"http://{domain}.mlpp-demo.svc.cluster.local:8000"
                )
            item["data"]["nginx.conf"] = kubernetes_gateway
        if item["kind"] != "Deployment":
            continue
        name = item["metadata"]["name"]
        if profile_name == DIAGNOSTIC_PROFILE and name in {
            "gateway",
            "model-api",
            "tuning-api",
            "monitoring-api",
        }:
            for container in item["spec"]["template"]["spec"]["containers"]:
                for probe in ("startupProbe", "readinessProbe", "livenessProbe"):
                    container.pop(probe, None)
        elif name == "gateway":
            container = item["spec"]["template"]["spec"]["containers"][0]
            container["livenessProbe"]["httpGet"]["path"] = "/gateway-live"
        if name not in {"model-api", "monitoring-api"}:
            continue
        spec = item["spec"]["template"]["spec"]
        spec.setdefault("volumes", []).extend(local["volumes"])
        container = next(c for c in spec["containers"] if c["name"] == name)
        ai = local["containers"][0]
        overrides = {entry["name"]: entry for entry in ai["env"]}
        overrides.update(
            {
                "MLPP_CHAT_MODEL_TIMEOUT_SECONDS": {
                    "name": "MLPP_CHAT_MODEL_TIMEOUT_SECONDS",
                    "value": "none"
                    if profile.model_seconds is None
                    else str(profile.model_seconds),
                },
                "MLPP_CHAT_TIMEOUT_SECONDS": {
                    "name": "MLPP_CHAT_TIMEOUT_SECONDS",
                    "value": "none" if profile.turn_seconds is None else str(profile.turn_seconds),
                },
            }
        )
        if profile_name == DIAGNOSTIC_PROFILE:
            overrides["MLPP_CHAT_UNBOUNDED_DIAGNOSTIC"] = {
                "name": "MLPP_CHAT_UNBOUNDED_DIAGNOSTIC",
                "value": "true",
            }
        container["env"] = [
            e for e in container.get("env", []) if e["name"] not in overrides
        ] + list(overrides.values())
        container.setdefault("volumeMounts", []).extend(ai["volumeMounts"])
    manifest["items"].append(json.loads((root / "deploy/kubernetes/ollama-local.json").read_text()))
    output.mkdir(parents=True, exist_ok=True)
    (output / "gateway.conf").write_text(gateway, encoding="utf-8")
    target = output / "stack.json"
    target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return target
