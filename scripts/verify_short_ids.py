"""Opt-in short-ID browser, real-worker and local-Qwen acceptance on an isolated stack."""

import argparse
import asyncio
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import httpx
from playwright.sync_api import expect, sync_playwright

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.connections import open_connections
from ml_pipeline_pro.conversation_qwen_counter import JSON_TOOLS_TAG, QwenConversationModel
from ml_pipeline_pro.conversation_schemas import TOOL_BYTES, ChatRequest
from ml_pipeline_pro.conversation_service import ConversationService
from ml_pipeline_pro.conversation_store import ConversationStore
from ml_pipeline_pro.tool_schemas import ToolContext
from ml_pipeline_pro.tool_transport import HttpToolTransport


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--mongodb-uri", required=True)
    parser.add_argument("--redis-url", required=True)
    parser.add_argument("--tokenizer", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--browser", default="C:/Program Files/Google/Chrome/Application/chrome.exe"
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    project = "short_ids_" + uuid4().hex[:12]
    report = {
        "project": project,
        "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source_sha256": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(Path("src/ml_pipeline_pro").rglob("*"))
            if path.is_file() and "__pycache__" not in path.parts
        },
        "checks": [],
        "runs": [],
        "turns": [],
    }
    report_path = args.output / "result.json"
    started = time.monotonic()
    try:
        with httpx.Client(
            base_url=args.origin + "/api/v1",
            headers={"X-Project-ID": project},
            timeout=30,
            trust_env=False,
        ) as client:
            content = Path("examples/data/classification.csv").read_bytes()
            response = client.post(
                "/datasets/upload",
                params=[
                    ("name", "short_ids"),
                    ("version", "v1"),
                    ("feature_columns", "feature_1"),
                    ("feature_columns", "feature_2"),
                ],
                content=content,
                headers={"Content-Type": "text/csv"},
            )
            assert response.status_code == 201, response.text
            dataset = response.json()
            response = client.post("/models", json={"name": "short_id_classifier"})
            assert response.status_code == 201, response.text
            model = response.json()
            for number in (1, 2):
                body = {
                    "dataset_id": dataset["id"],
                    "model_id": model["id"],
                    "config": {"epochs": 2, "max_runtime_seconds": 30},
                }
                headers = {"Idempotency-Key": f"short-{number}"}
                response = client.post("/experiments", json=body, headers=headers)
                assert response.status_code == 202, response.text
                original = response.json()
                assert original["short_id"] == f"e{number}"
                assert (
                    client.post("/experiments", json=body, headers=headers).json()["id"]
                    == original["id"]
                )
                deadline = time.monotonic() + 120
                run = original
                while run["status"] in {"queued", "running"} and time.monotonic() < deadline:
                    time.sleep(0.2)
                    response = client.get(f"/experiments/e{number}")
                    assert response.status_code == 200, response.text
                    run = response.json()
                assert run["status"] == "succeeded", run
                assert client.get("/experiments/" + run["id"]).json() == run
                for artifact in run["artifacts"]:
                    response = client.get(f"/experiments/e{number}/artifacts/{artifact['name']}")
                    assert response.status_code == 200, response.text
                    assert len(response.content) == artifact["size_bytes"]
                    assert hashlib.sha256(response.content).hexdigest() == artifact["sha256"]
                report["runs"].append(run)
            comparison = client.get(
                "/experiments/compare", params=[("experiment_id", "e1"), ("experiment_id", "e2")]
            )
            assert comparison.status_code == 200, comparison.text
            response = client.post(
                f"/models/{model['id']}/versions", json={"version": "v1", "experiment_id": "e1"}
            )
            assert response.status_code == 201, response.text
            assert response.json()["experiment_id"] == report["runs"][0]["id"]
            report["checks"].append(
                "Two real worker runs; alias/full reads, same-key replay, comparison, "
                "artifact hashes and version registration"
            )

            async def local_model_gate():
                settings = Settings(
                    _env_file=None,
                    openai_api_key=None,
                    chat_backend="ollama",
                    chat_enabled=True,
                    chat_protocol="guided",
                    chat_model=JSON_TOOLS_TAG,
                    chat_tokenizer_path=args.tokenizer,
                    chat_api_origin=args.origin,
                    chat_timeout_seconds=120,
                    chat_model_timeout_seconds=60,
                    mongodb_uri=args.mongodb_uri,
                    redis_url=args.redis_url,
                )
                model = QwenConversationModel(settings, args.tokenizer)
                try:
                    async with (
                        open_connections(settings) as connections,
                        HttpToolTransport(args.origin, max_response_bytes=TOOL_BYTES) as transport,
                    ):
                        database = connections.mongo.get_database(settings.mongodb_database)
                        store = ConversationStore(database, settings)
                        service = ConversationService(settings, store, model, transport)
                        context = ToolContext(project_id=project)
                        prompts = [
                            "Inspect experiment e1. Return a verified metrics.validation_f1 fact "
                            "and guide my next step in one sentence.",
                            "Compare e1 and e2 by validation F1. Return verified "
                            "metrics.validation_f1 facts for both records and identify the winner.",
                        ]
                        for index, prompt in enumerate(prompts):
                            body = ChatRequest(
                                request_id=f"live-{index}", message=prompt, expected_revision=0
                            )
                            turn = await service.chat(context, body)
                            report["turns"].append(turn.model_dump(mode="json"))
                            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
                            assert turn.status == "completed", turn.model_dump(mode="json")
                            assert turn.short_id == f"c{index + 1}"
                            expected = {r["id"] for r in report["runs"][: index + 1]}
                            assert {
                                f.record_id
                                for f in turn.facts
                                if f.field == "metrics.validation_f1"
                            } == expected
                            assert await service.chat(context, body) == turn
                            assert (
                                await store.history(project, turn.short_id)
                            ).conversation_id == turn.conversation_id
                            assert (await store.history(project, turn.conversation_id)).turns == [
                                turn
                            ]
                        report["checks"].append(
                            "Pinned local Qwen alias inspection/comparison, canonical facts, "
                            "c1/c2 history and exact offline replay"
                        )
                finally:
                    await model.close()

            asyncio.run(local_model_gate())
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path=args.browser, headless=True)
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(args.origin + "/dashboard/")
                page.locator("#connection-open").click()
                page.locator("#connection-project").fill(project)
                page.locator("#connection-form button[type=submit]").click()
                expect(page.locator("#runs-body")).to_contain_text("e1")
                expect(page.locator("#runs-body")).to_contain_text("e2")
                page.evaluate(
                    """({project, ids}) => {
                    sessionStorage.setItem(`mlpp:${project}:conversations`, JSON.stringify(ids));
                    sessionStorage.setItem(`mlpp:${project}:conversation`, JSON.stringify(ids[0]));
                }""",
                    {"project": project, "ids": [t["conversation_id"] for t in report["turns"]]},
                )
                page.reload()
                expect(
                    page.locator("#conversation-select option").filter(has_text="Conversation c1")
                ).to_have_count(1)
                expect(
                    page.locator("#conversation-select option").filter(has_text="Conversation c2")
                ).to_have_count(1)
                expect(page.locator("#chat-messages .facts-list")).to_contain_text("e1")
                page.locator("#runs-body tr").filter(has_text="e1").get_by_role(
                    "button", name="View"
                ).click()
                expect(page.locator("#run-detail")).to_contain_text("Experiment e1")
                expect(page.locator("#run-detail")).to_contain_text(report["runs"][0]["id"])
                page.get_by_role("button", name="Ask agent about this run").click()
                expect(page.locator("#chat-input")).to_have_value(
                    re.compile(r"Inspect experiment e1\.")
                )
                page.get_by_role("button", name="Compare validation results").click()
                expect(page.locator("#review-content")).to_contain_text("e1")
                expect(page.locator("#review-content")).to_contain_text("e2")
                page.locator("#review-dialog").get_by_role(
                    "button", name="Back", exact=True
                ).click()
                page.screenshot(path=str(args.output / "short-ids.png"), full_page=True)
                page.reload()
                expect(page.locator("#conversation-select")).to_have_value(
                    report["turns"][0]["conversation_id"]
                )
                expect(
                    page.locator("#conversation-select option").filter(has_text="Conversation c1")
                ).to_have_count(1)
                assert errors == [], errors
                browser.close()
                report["checks"].append(
                    "Chrome run/detail/comparison/fact labels, alias prompt, "
                    "conversation migration from saved UUIDs and reload persistence"
                )
        report["status"] = "passed"
    except BaseException as exc:
        report["status"] = "failed"
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        report["elapsed_seconds"] = time.monotonic() - started
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
