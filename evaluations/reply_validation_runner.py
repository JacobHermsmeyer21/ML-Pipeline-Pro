"""Opt-in, capped experiment-inspection reproduction; never submits domain work."""

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import httpx

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.conversation_openai import OpenAIConversationModel
from ml_pipeline_pro.main import create_model_app
from ml_pipeline_pro.openai_test_budget import MODEL, OpenAITestBudget, TestAuthorization

ROOT = Path("artifacts/agent-reply-validation")
LEDGER = ROOT / "live-budget.json"
EXPERIMENT = "508815fb-1652-475e-aba9-c68281270704"
PROMPT = (
    f"Inspect experiment {EXPERIMENT}. what other facts can you give me about this run? "
    "what could i tune to increase the f1 score?"
)
AUTHORIZATION = TestAuthorization(Decimal("0.25"), Decimal("0.23"))


def phase_passed(phase, attempts):
    return phase == "baseline" or (
        len(attempts) == 3 and all(item.get("acceptance_passed") is True for item in attempts)
    )


def save(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


async def run(args, report, budget):
    settings = Settings().model_copy(
        update={
            "chat_enabled": True,
            "chat_backend": "openai",
            "chat_protocol": "native",
            "chat_model": MODEL,
            "chat_api_origin": args.origin,
        }
    )
    headers = {"X-Project-ID": "demo"}
    if "demo" in settings.project_api_keys:
        headers["X-API-Key"] = settings.project_api_keys["demo"].get_secret_value()
    app = create_model_app(
        settings,
        chat_model_factory=lambda cfg: OpenAIConversationModel(
            cfg, budget=budget, observer=report["provider_requests"].append
        ),
    )
    async with httpx.AsyncClient(
        base_url=args.origin, headers=headers, timeout=30, trust_env=False
    ) as domain:
        record_response = await domain.get("/api/v1/experiments/" + EXPERIMENT)
        record_response.raise_for_status()
        record = record_response.json()
    report["experiment_id"] = EXPERIMENT
    report["validation_f1"] = record["metrics"]["validation_f1"]
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://agent", headers=headers
        ) as client:
            for number in range(len(report["attempts"]), 2 if args.phase == "baseline" else 3):
                correlation = "reply-validation-" + uuid4().hex
                body = {"request_id": str(uuid4()), "message": PROMPT, "expected_revision": 0}
                report["attempts"].append({"number": number + 1, "correlation_id": correlation})
                save(args.output, report)
                response = await client.post(
                    "/api/v1/chat", json=body, headers={"X-Correlation-ID": correlation}
                )
                response.raise_for_status()
                turn = response.json()
                item = report["attempts"][-1]
                item.update(
                    conversation_id=turn["conversation_id"],
                    request_id=turn["request_id"],
                    turn_id=turn["turn_id"],
                    status=turn["status"],
                    error=turn["error"],
                    facts=turn["facts"],
                    evidence=turn["evidence"],
                    message=turn["message"],
                    model_provenance=turn["model_provenance"],
                    has_action=turn["pending_action"] is not None,
                )
                if turn["status"] == "failed":
                    # Only the fixed error metadata is retained from a rejected reply.
                    item.pop("message")
                reserved, calls = budget.reserved, len(report["provider_requests"])
                replay = await client.post("/api/v1/chat", json=body)
                history = await client.get("/api/v1/conversations/" + turn["conversation_id"])
                assert replay.status_code == history.status_code == 200
                assert replay.json() == turn == history.json()["turns"][0]
                assert reserved == budget.reserved and calls == len(report["provider_requests"])
                item["replay_equal_without_inference"] = True
                assert turn["pending_action"] is None and turn["snippet"] is None
                if args.phase == "acceptance":
                    assert turn["status"] == "completed"
                    facts = {
                        f["field"]: f["value"]
                        for f in turn["facts"]
                        if f["record_id"] == EXPERIMENT
                    }
                    assert facts["metrics.validation_f1"] == record["metrics"]["validation_f1"]
                    assert any(f.startswith("config.") for f in facts)
                    for field, value in facts.items():
                        actual = record
                        for part in field.split("."):
                            actual = actual[part]
                        assert value == actual
                    item["acceptance_passed"] = True
                report["estimated_reserved_usd"] = str(budget.reserved)
                save(args.output, report)
    report["passed"] = phase_passed(args.phase, report["attempts"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=("baseline", "acceptance"))
    parser.add_argument("--origin", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--resume", action="store_true", help="Preserve and append reviewed phase attempts"
    )
    args = parser.parse_args()
    if os.getenv("MLPP_RUN_OPENAI_EVAL") != "1":
        parser.error("Set MLPP_RUN_OPENAI_EVAL=1 to authorize the already approved paid test")
    args.output = ROOT / (args.phase + ".json")
    report = {
        "source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source_hashes": {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [*Path("src/ml_pipeline_pro").glob("conversation*.py"), Path(__file__)]
        },
        "started_utc": datetime.now(UTC).isoformat(),
        "phase": args.phase,
        "transport": "ASGI HTTP routes, real MongoDB/Redis, domain HTTP read",
        "passed": False,
        "attempts": [],
        "provider_requests": [],
    }
    with OpenAITestBudget(LEDGER, authorization=AUTHORIZATION) as budget:
        # Report admission and reload share the ledger's exclusive process lock.
        if args.output.exists() and not args.resume:
            parser.error(
                "Phase report already exists; preserve attempts and review before rerunning"
            )
        if args.resume:
            if not args.output.exists():
                parser.error("No existing phase to resume")
            previous = json.loads(args.output.read_text(encoding="utf-8"))
            limit = 2 if args.phase == "baseline" else 3
            if previous.get("phase") != args.phase or len(previous["attempts"]) >= limit:
                parser.error("Phase mismatch or attempt limit already reached")
            # Keep each revision's provenance, all failures and the same ledger.
            previous.setdefault("resumes", []).append(
                {key: report[key] for key in ("source_revision", "source_hashes", "started_utc")}
            )
            previous["passed"] = False
            report = previous
        save(args.output, report)
        try:
            asyncio.run(run(args, report, budget))
        except Exception:
            report["failure"] = "runner_or_acceptance_failed"
        finally:
            report["estimated_reserved_usd"] = str(budget.reserved)
            save(args.output, report)
    print(f"{args.phase}: passed={report['passed']}; reserved=${report['estimated_reserved_usd']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
