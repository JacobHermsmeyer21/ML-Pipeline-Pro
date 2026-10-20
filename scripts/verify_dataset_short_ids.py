"""Opt-in d1/d2 local-Qwen, exact-action, worker and Chrome acceptance."""

import argparse
import asyncio
import hashlib
import json
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import httpx
from playwright.sync_api import expect, sync_playwright

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.connections import open_connections
from ml_pipeline_pro.conversation_actions import ConversationActions
from ml_pipeline_pro.conversation_qwen_counter import JSON_TOOLS_TAG, QwenConversationModel
from ml_pipeline_pro.conversation_schemas import TOOL_BYTES, ActionDecision, ChatRequest
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
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    project = "dataset_ids_" + uuid4().hex[:12]
    report = {
        "project": project,
        "turns": [],
        "checks": [],
        "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source_sha256": {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in Path("src/ml_pipeline_pro").rglob("*")
            if p.is_file() and "__pycache__" not in p.parts
        },
    }
    started = time.monotonic()
    try:
        with httpx.Client(
            base_url=args.origin + "/api/v1",
            headers={"X-Project-ID": project},
            timeout=30,
            trust_env=False,
        ) as client:
            content = Path("examples/data/classification.csv").read_bytes()
            datasets = []
            for number in (1, 2):
                response = client.post(
                    "/datasets/upload",
                    params=[
                        ("name", "alias_data"),
                        ("version", f"v{number}"),
                        ("feature_columns", "feature_1"),
                        ("feature_columns", "feature_2"),
                    ],
                    content=content,
                    headers={"Content-Type": "text/csv"},
                )
                assert response.status_code == 201, response.text
                dataset = response.json()
                assert dataset["short_id"] == f"d{number}"
                assert client.get("/datasets/" + dataset["short_id"]).json() == dataset
                datasets.append(dataset)
            response = client.post("/models", json={"name": "alias_classifier"})
            assert response.status_code == 201, response.text
            classifier = response.json()
            report["datasets"] = datasets

            async def gate():
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
                        store = ConversationStore(
                            connections.mongo.get_database(settings.mongodb_database), settings
                        )
                        service = ConversationService(settings, store, model, transport)
                        context = ToolContext(project_id=project)
                        for number, dataset in enumerate(datasets, 1):
                            body = ChatRequest(
                                request_id=f"inspect-{number}",
                                expected_revision=0,
                                message=f"Inspect dataset d{number}. Return verified "
                                "row_counts.train and row_counts.validation facts.",
                            )
                            turn = await service.chat(context, body)
                            report["turns"].append(turn.model_dump(mode="json"))
                            assert turn.status == "completed", turn.model_dump(mode="json")
                            actual = {
                                f.field: f.value for f in turn.facts if f.record_id == dataset["id"]
                            }
                            assert (
                                actual["row_counts.train"] == 80
                                and actual["row_counts.validation"] == 20
                            )
                            assert await service.chat(context, body) == turn
                        proposal = await service.chat(
                            context,
                            ChatRequest(
                                request_id="propose",
                                expected_revision=0,
                                message="Prepare training for dataset d1 with model "
                                f"{classifier['id']}. "
                                "Per-trial runtime is 10 seconds. Do not submit it yet.",
                            ),
                        )
                        report["turns"].append(proposal.model_dump(mode="json"))
                        assert proposal.status == "awaiting_confirmation", proposal.model_dump(
                            mode="json"
                        )
                        action = proposal.pending_action
                        assert action.tool.arguments["dataset_id"] == "d1"

                        class Capture:
                            async def request(self, method, path, **kwargs):
                                if method == "POST":
                                    report["submitted_action"] = {
                                        "path": path,
                                        "body": kwargs["body"],
                                    }
                                    assert kwargs["body"]["dataset_id"] == "d1"
                                return await transport.request(method, path, **kwargs)

                        decisions = ConversationActions(settings, store, Capture())
                        decision = ActionDecision(
                            decision="approve", arguments_hash=action.arguments_hash
                        )
                        approved = await decisions.decide(
                            context, proposal.conversation_id, action.action_id, decision
                        )
                        assert approved.status == "succeeded", approved.model_dump(mode="json")
                        assert approved.arguments_hash == action.arguments_hash
                        assert approved.outcome.data["dataset_id"] == datasets[0]["id"]
                        assert (
                            await decisions.decide(
                                context, proposal.conversation_id, action.action_id, decision
                            )
                            == approved
                        )
                        report["action"] = approved.model_dump(mode="json")
                        report["checks"].append(
                            "Real local Qwen understands d1 and d2; facts cite canonical datasets; "
                            "d1 proposal arguments/hash remain exact through approval and replay"
                        )
                        return approved.outcome.data["id"]
                finally:
                    await model.close()

            experiment = asyncio.run(gate())
            deadline = time.monotonic() + 120
            while True:
                response = client.get("/experiments/" + experiment)
                assert response.status_code == 200, response.text
                run = response.json()
                if run["status"] not in {"queued", "running"} or time.monotonic() > deadline:
                    break
                time.sleep(0.2)
            assert run["status"] == "succeeded" and run["dataset_id"] == datasets[0]["id"], run
            assert len(client.get("/experiments").json()["items"]) == 1
            for artifact in run["artifacts"]:
                response = client.get(f"/experiments/{experiment}/artifacts/{artifact['name']}")
                assert response.status_code == 200, response.text
                assert len(response.content) == artifact["size_bytes"]
                assert hashlib.sha256(response.content).hexdigest() == artifact["sha256"]
            report["run"] = run
            report["checks"].append(
                "One real approved worker run, canonical dataset reference "
                "and verified artifact hashes"
            )
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",
                    headless=True,
                )
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(args.origin + "/dashboard/")
                page.locator("#connection-open").click()
                page.locator("#connection-project").fill(project)
                page.locator("#connection-form button[type=submit]").click()
                expect(
                    page.locator("#training-dataset option").filter(has_text="d1")
                ).to_have_count(1)
                expect(
                    page.locator("#training-dataset option").filter(has_text="d2")
                ).to_have_count(1)
                page.locator("#training-dataset").select_option(datasets[0]["id"])
                page.locator('[data-prompt="inspect"]').first.click()
                assert page.locator("#chat-input").input_value().startswith("Inspect dataset d1.")
                page.locator('.nav-item[data-view="datasets"]').click()
                expect(page.locator("#datasets-list")).to_contain_text("d1")
                expect(page.locator("#datasets-list")).to_contain_text("d2")
                expect(page.locator("#datasets-list")).to_contain_text(datasets[0]["id"])
                page.reload()
                expect(
                    page.locator("#training-dataset option").filter(has_text="d1")
                ).to_have_count(1)
                page.locator('.nav-item[data-view="datasets"]').click()
                page.screenshot(path=str(args.output / "datasets.png"), full_page=True)
                assert errors == [], errors
                browser.close()
                report["checks"].append(
                    "Chrome cards, selectors, d1 starter prompt and reload persistence"
                )
            report["status"] = "passed"
    except BaseException as exc:
        report["status"] = "failed"
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        report["elapsed_seconds"] = time.monotonic() - started
        (args.output / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
