"""Real hosted model + ASGI HTTP routes + isolated Mongo/Redis/domain worker.

Creates only its uniquely named project's small classification demo. Python drafts
are never executed. Exact bounded training approval is checked before dispatch.
"""

import argparse
import asyncio
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx

from evaluations.openai_runner import LEDGER
from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.conversation_openai import OpenAIConversationModel
from ml_pipeline_pro.main import create_app, create_monitoring_app
from ml_pipeline_pro.openai_test_budget import MODEL, OpenAITestBudget


async def run(args, report, budget):
    project = "openai-live-" + uuid4().hex[:12]
    report["project"] = project
    settings = Settings(
        chat_enabled=True,
        chat_backend="openai",
        chat_model=MODEL,
        chat_protocol="native",
        chat_tokenizer_path=None,
        chat_unbounded_diagnostic=False,
        chat_model_timeout_seconds=20,
        chat_timeout_seconds=60,
        mongodb_uri="mongodb://127.0.0.1:37017/?directConnection=true",
        redis_url="redis://127.0.0.1:16379/0",
        chat_api_origin=args.origin,
        project_api_keys={},
    )
    app = create_app(
        settings,
        chat_model_factory=lambda cfg: OpenAIConversationModel(
            cfg, budget=budget, observer=report["provider_requests"].append
        ),
    )
    monitoring_app = create_monitoring_app(
        settings,
        chat_model_factory=lambda cfg: OpenAIConversationModel(
            cfg, budget=budget, observer=report["provider_requests"].append
        ),
    )
    headers = {"X-Project-ID": project, "X-Correlation-ID": "openai-live-walkthrough"}
    async with httpx.AsyncClient(
        base_url=args.origin, headers=headers, timeout=30, trust_env=False
    ) as domain:

        async def api(method, path, **kwargs):
            result = await domain.request(method, "/api/v1" + path, **kwargs)
            result.raise_for_status()
            return result.json()

        async def wait_experiment(identity):
            for _ in range(90):
                record = await api("GET", "/experiments/" + identity)
                if record["status"] in {"succeeded", "failed", "cancelled"}:
                    assert record["status"] == "succeeded"
                    return record
                await asyncio.sleep(1)
            raise TimeoutError("Bounded training did not complete")

        dataset = await api(
            "POST",
            "/datasets",
            json={
                "name": project,
                "version": "v1",
                "uri": "classification.csv",
                "feature_columns": ["feature_1", "feature_2"],
            },
        )
        model = await api("POST", "/models", json={"name": project})
        initial = await api(
            "POST",
            "/experiments",
            headers={"Idempotency-Key": project + "-seed"},
            json={
                "dataset_id": dataset["id"],
                "model_id": model["id"],
                "config": {"epochs": 5, "max_runtime_seconds": 20},
            },
        )
        initial = await wait_experiment(initial["id"])
        report.update(dataset=dataset, model=model, seed_experiment=initial)
        async with (
            app.router.lifespan_context(app),
            monitoring_app.router.lifespan_context(monitoring_app),
        ):
            async with (
                httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://agent",
                    headers=headers,
                    timeout=90,
                ) as client,
                httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=monitoring_app),
                    base_url="http://monitoring",
                    headers=headers,
                    timeout=90,
                ) as monitoring_client,
            ):

                async def agent(method, path, **kwargs):
                    target = monitoring_client if path.startswith("/monitoring/") else client
                    response = await target.request(method, "/api/v1" + path, **kwargs)
                    response.raise_for_status()
                    return response.json()

                async def chat(name, message):
                    body = {"request_id": name, "expected_revision": 0, "message": message}
                    turn = await agent("POST", "/chat", json=body)
                    report["turns"].append(turn)
                    reserved = budget.reserved
                    assert await agent("POST", "/chat", json=body) == turn
                    assert budget.reserved == reserved
                    history = await agent("GET", "/conversations/" + turn["conversation_id"])
                    assert history["turns"][0] == turn
                    return turn

                inspected = await chat(
                    "inspect",
                    f"Inspect experiment {initial['id']}. Return a verified "
                    "metrics.validation_f1 fact and next-step guidance.",
                )
                assert inspected["status"] == "completed"
                assert any(
                    f["record_id"] == initial["id"]
                    and f["field"] == "metrics.validation_f1"
                    and f["value"] == initial["metrics"]["validation_f1"]
                    for f in inspected["facts"]
                )
                proposed = await chat(
                    "training",
                    f"Prepare training dataset {dataset['id']} model {model['id']}, "
                    "epochs 5, max_runtime_seconds 20. Return a proposal for "
                    "confirmation, do not submit yet.",
                )
                assert proposed["status"] == "awaiting_confirmation"
                action = proposed["pending_action"]
                assert action["tool"]["name"] == "create_experiment"
                values = action["tool"]["arguments"]
                assert values["dataset_id"] == dataset["id"] and values["model_id"] == model["id"]
                assert (
                    values["config"]["epochs"] == 5
                    and values["config"]["max_runtime_seconds"] == 20
                )
                decision_path = (
                    f"/conversations/{proposed['conversation_id']}"
                    f"/actions/{action['action_id']}/decision"
                )
                decision = {"decision": "approve", "arguments_hash": action["arguments_hash"]}
                reserved = budget.reserved
                accepted = await agent("POST", decision_path, json=decision)
                assert accepted["status"] == "succeeded" and budget.reserved == reserved
                assert await agent("POST", decision_path, json=decision) == accepted
                trained_id = accepted["outcome"]["data"]["id"]
                trained = await wait_experiment(trained_id)
                report["confirmed_action"], report["trained_experiment"] = accepted, trained
                jobs_before = await api("GET", "/tuning-jobs")
                tuning = await chat(
                    "tuning",
                    f"Compare experiments {initial['id']} and {trained_id} by validation_f1, "
                    f"then propose tuning dataset {dataset['id']} model {model['id']}. "
                    "Per-trial runtime 10 seconds, objective validation_f1, maximum 2 trials "
                    "and total 40 seconds. Do not submit it.",
                )
                assert tuning["status"] == "awaiting_confirmation"
                values = tuning["pending_action"]["tool"]["arguments"]
                assert tuning["pending_action"]["tool"]["name"] == "create_tuning_job"
                assert values["objective_metric"] == "validation_f1"
                assert values["config"]["max_runtime_seconds"] == 10
                assert values["limits"] == {
                    "max_trials": 2,
                    "max_runtime_seconds": 40,
                    "concurrency": 1,
                }
                assert await api("GET", "/tuning-jobs") == jobs_before
                draft = await chat(
                    "draft",
                    "Generate Python listing experiments, limit 50, offset 0. "
                    "Return a draft without submitting or executing anything.",
                )
                assert draft["snippet"]["status"] == "validated" and draft["pending_action"] is None
                version = await api(
                    "POST",
                    f"/models/{model['id']}/versions",
                    json={"version": "v1", "experiment_id": trained_id},
                )
                for number in range(3):
                    await agent(
                        "POST",
                        "/monitoring/observations",
                        json={
                            "sample_id": project + str(number),
                            "model_version_id": version["id"],
                            "observed_at": datetime.now(UTC).isoformat(),
                            "latency_ms": 150,
                            "fault": "seeded_latency",
                        },
                    )
                diagnosis = await agent(
                    "POST", f"/monitoring/model-versions/{version['id']}/diagnosis"
                )
                assert (
                    diagnosis["review_required"] is True and diagnosis["automatic_changes"] is False
                )
                assert set(diagnosis["generated_advice"]["observation_ids"]) <= set(
                    diagnosis["measurements"]["observation_ids"]
                )
                report["diagnosis"] = diagnosis
                foreign = await client.get(
                    "/api/v1/conversations/" + draft["conversation_id"],
                    headers={"X-Project-ID": "foreign"},
                )
                assert foreign.status_code == 404
                empty_version = await api(
                    "POST",
                    f"/models/{model['id']}/versions",
                    json={"version": "v2", "experiment_id": initial["id"]},
                )
                reserved = budget.reserved
                empty = await monitoring_client.post(
                    f"/api/v1/monitoring/model-versions/{empty_version['id']}/diagnosis"
                )
                assert empty.status_code == 409 and budget.reserved == reserved
                report["empty_diagnosis_status"] = empty.status_code
                report["passed"] = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", default="http://127.0.0.1:18000")
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/openai-provider/http-walkthrough.json")
    )
    args = parser.parse_args()
    if os.getenv("MLPP_RUN_OPENAI_EVAL") != "1":
        parser.error(
            "Set MLPP_RUN_OPENAI_EVAL=1; this workflow makes paid calls "
            "and confirms bounded training"
        )
    report = {
        "source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "working_tree": True,
        "utc_started": datetime.now(UTC).isoformat(),
        "transport": "ASGI HTTP routes; real MongoDB/Redis and external domain HTTP/worker",
        "observations": "declared synthetic seeded delay, not measured latency",
        "passed": False,
        "turns": [],
        "provider_requests": [],
        "code_execution": False,
    }
    with OpenAITestBudget(LEDGER) as budget:
        try:
            asyncio.run(run(args, report, budget))
        except Exception as exc:
            report["failure_type"] = type(exc).__name__
            report["error_code"] = getattr(exc, "code", None)
        finally:
            report["estimated_reserved_usd"] = str(budget.reserved)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"Real-ID hosted HTTP walkthrough passed={report['passed']}; "
        f"estimated reservations ${budget.reserved}"
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
