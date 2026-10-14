"""All-nine midterm workflow; local model inference and reviewable outputs, no code execution."""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", default="http://127.0.0.1:8000")
    parser.add_argument("--project", default="demo")
    parser.add_argument("--output", type=Path, default=Path("artifacts/midterm-walkthrough"))
    parser.add_argument(
        "--confirm-demo-proposal",
        action="store_true",
        help="Explicitly approve this bounded test proposal; Python remains unexecuted",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            "scripts/deployment_smoke.py",
            "--origin",
            args.origin,
            "--project",
            args.project,
            "--output",
            str(args.output / "backend.json"),
        ],
        check=True,
    )
    backend = json.loads((args.output / "backend.json").read_text())
    headers = {"X-Project-ID": args.project}
    if key := os.getenv("MLPP_API_KEY"):
        headers["X-API-Key"] = key
    result = {"backend": backend, "code_execution": False, "dialogue": []}
    with httpx.Client(
        base_url=args.origin, headers=headers, timeout=90, trust_env=False, follow_redirects=False
    ) as client:

        def chat(request_id, message, previous=None):
            body = {
                "request_id": backend["training"]["id"] + "-" + request_id,
                "message": message,
                "expected_revision": previous["revision"] if previous else 0,
            }
            if previous:
                body["conversation_id"] = previous["conversation_id"]
            response = client.post("/api/v1/chat", json=body)
            response.raise_for_status()
            turn = response.json()
            result["dialogue"].append(turn)
            (args.output / "results.json").write_text(json.dumps(result, indent=2) + "\n")
            return turn, body

        inspection, _ = chat(
            "inspect",
            f"Inspect experiment {backend['training']['id']}. Return a verified "
            "metrics.validation_f1 fact and guide my next pipeline step in one sentence.",
        )
        assert inspection["status"] == "completed" and inspection["facts"]
        assert any(fact["record_id"] == backend["training"]["id"] for fact in inspection["facts"])
        prompt = (
            f"Compare {backend['training']['id']} and {backend['tuning']['best_experiment_id']} "
            "by validation_f1, then propose tuning "
            f"dataset {backend['dataset']['id']} with model {backend['model']['id']}. "
            "Use validation history to guide your proposal. Per-trial runtime is 10 seconds, "
            "objective validation_f1, maximum 2 trials and 40 seconds total. Do not submit it."
        )
        tuning, body = chat("suggest", prompt, inspection)
        action = tuning["pending_action"]
        assert tuning["status"] == "awaiting_confirmation" and action is not None
        assert action["status"] == "pending_confirmation"
        assert action["tool"]["name"] == "create_tuning_job"
        arguments = action["tool"]["arguments"]
        assert arguments["dataset_id"] == backend["dataset"]["id"]
        assert arguments["model_id"] == backend["model"]["id"]
        assert arguments["config"]["max_runtime_seconds"] == 10
        assert arguments["limits"]["max_trials"] == 2
        assert arguments["limits"]["max_runtime_seconds"] == 40
        assert arguments["objective_metric"] == "validation_f1"
        assert any(item["status"] == "succeeded" for item in tuning["tool_results"])
        replay = client.post("/api/v1/chat", json=body)
        replay.raise_for_status()
        assert replay.json() == tuning
        result["saved_proposal_replay_equal"] = True
        decision_path = (
            f"/api/v1/conversations/{tuning['conversation_id']}/actions/"
            f"{action['action_id']}/decision"
        )
        decision = client.post(
            decision_path,
            json={
                "decision": "approve" if args.confirm_demo_proposal else "reject",
                "arguments_hash": action["arguments_hash"],
            },
        )
        decision.raise_for_status()
        result["explicit_test_decision"] = decision.json()
        if args.confirm_demo_proposal:
            domain_id = decision.json()["outcome"]["data"]["id"]
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                job = client.get("/api/v1/tuning-jobs/" + domain_id).json()
                if job["status"] in {"succeeded", "failed", "cancelled"}:
                    assert job["status"] == "succeeded"
                    result["confirmed_tuning"] = job
                    break
                time.sleep(1)
            else:
                raise TimeoutError("Confirmed test tuning did not finish")
        draft, draft_body = chat(
            "python", "Generate Python listing experiments, limit 50, offset 0. Do not execute."
        )
        assert draft["snippet"]["status"] == "validated" and draft["snippet"]["review_required"]
        assert client.post("/api/v1/chat", json=draft_body).json() == draft
        result["draft_replay_equal"] = True
        result["history"] = client.get("/api/v1/conversations/" + tuning["conversation_id"]).json()
    subprocess.run(
        [
            sys.executable,
            "examples/monitor_workload.py",
            "--origin",
            args.origin,
            "--project",
            args.project,
            "--model-id",
            backend["model"]["id"],
            "--version-id",
            backend["version"]["id"],
            "--output",
            str(args.output / "workload.json"),
        ],
        check=True,
    )
    with httpx.Client(base_url=args.origin, headers=headers, timeout=90, trust_env=False) as client:
        diagnosis = client.post(
            f"/api/v1/monitoring/model-versions/{backend['version']['id']}/diagnosis"
        )
        diagnosis.raise_for_status()
        result["monitoring"] = diagnosis.json()
        assert "inspect_seeded_delay" in result["monitoring"]["generated_advice"]["proposed_checks"]
    (args.output / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("Real dialogue/history/proposal/decision/draft/monitoring walkthrough passed.")


if __name__ == "__main__":
    main()
