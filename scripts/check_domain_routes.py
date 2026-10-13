"""Read-only checks against the running independent APIs through the gateway."""

import argparse
import json
import os
from pathlib import Path

import httpx

from ml_pipeline_pro.errors import ErrorResponse


def check(origin: str, project: str, *, tuning_unavailable: bool = False) -> dict:
    headers = {"X-Project-ID": project, "X-Correlation-ID": "domain-route-check"}
    if key := os.getenv("MLPP_API_KEY"):
        headers["X-API-Key"] = key
    with httpx.Client(base_url=origin, headers=headers, timeout=10, trust_env=False) as client:
        models = client.get("/openapi.json")
        models.raise_for_status()
        assert "/api/v1/experiments" in models.json()["paths"]
        assert "/api/v1/tuning-jobs" not in models.json()["paths"]
        if not tuning_unavailable:
            tuning = client.get("/tuning/openapi.json")
            tuning.raise_for_status()
            assert "/api/v1/tuning-jobs" in tuning.json()["paths"]
            assert "/api/v1/experiments" not in tuning.json()["paths"]
        path = "/api/v1/tuning-jobs/route-check-missing"
        result = client.get(path)
        error = ErrorResponse.model_validate(result.json()).error
        assert result.status_code == (503 if tuning_unavailable else 404)
        assert error.code == (
            "service_unavailable" if tuning_unavailable else "tuning_job_not_found"
        )
        assert error.correlation_id == result.headers["X-Correlation-ID"] == "domain-route-check"
        invalid = client.get(path, headers={"X-Correlation-ID": "invalid:correlation"})
        invalid_error = ErrorResponse.model_validate(invalid.json()).error
        assert invalid_error.correlation_id == invalid.headers["X-Correlation-ID"]
        assert invalid_error.correlation_id != "invalid:correlation"
        model_error = client.get("/api/v1/models/route-check-missing")
        assert model_error.status_code == 404
        assert ErrorResponse.model_validate(model_error.json()).error.code == "model_not_found"
    return {
        "origin": origin,
        "model_routes_owned": True,
        "tuning_routes_owned": not tuning_unavailable,
        "tuning_status": result.status_code,
        "tuning_error": error.code,
        "correlations_verified": True,
        "read_only": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", default="http://127.0.0.1:8000")
    parser.add_argument("--project", default="demo")
    parser.add_argument("--tuning-unavailable", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    observed = check(args.origin, args.project, tuning_unavailable=args.tuning_unavailable)
    rendered = json.dumps(observed, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)
