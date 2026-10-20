"""Opt-in hosted semantic gates using original scenarios and one $2 test ledger."""

import argparse
import asyncio
import json
import os
import platform
import subprocess
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from evaluations.test_conversation_model import PROMPTS, FixtureTransport, check_case
from evaluations.test_snippet_model import CASES, check_snippet_case
from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.conversation_openai import OpenAIConversationModel
from ml_pipeline_pro.conversation_schemas import ChatRequest, fingerprint
from ml_pipeline_pro.conversation_service import ConversationService
from ml_pipeline_pro.conversation_timing import timing_profile
from ml_pipeline_pro.openai_test_budget import MODEL, OpenAITestBudget
from ml_pipeline_pro.tool_schemas import ToolContext
from tests.conversation_memory import MemoryConversations
from tests.test_conversation_service import RecordsTransport as EmptyTransport

LEDGER = Path("artifacts/openai-provider/live-budget.json")


class ObservedModel:
    def __init__(self, model, report):
        self.model, self.report = model, report
        self.provenance = model.provenance

    async def _call(self, messages, *, snippet=False):
        started = time.monotonic()
        item = {"stage": "snippet" if snippet else "conversation"}
        self.report["calls"].append(item)
        try:
            method = self.model.generate_snippet if snippet else self.model.generate
            step = await method(messages)
            item["step"] = self.model._safe(step.model_dump(mode="json"))
            return step
        finally:
            item["elapsed_seconds"] = time.monotonic() - started

    async def generate(self, messages):
        return await self._call(messages)

    async def generate_snippet(self, messages):
        return await self._call(messages, snippet=True)


async def evaluate(args, report, budget):
    settings = Settings(
        chat_enabled=True,
        chat_backend="openai",
        chat_model=MODEL,
        chat_protocol="native",
        chat_tokenizer_path=None,
        chat_unbounded_diagnostic=False,
        chat_model_timeout_seconds=20,
        chat_timeout_seconds=60,
    )
    profile = timing_profile("default")
    async with OpenAIConversationModel(
        settings, budget=budget, observer=report["provider_requests"].append
    ) as model:
        report["model_provenance"] = model.provenance
        observed = ObservedModel(model, report)
        for suite in ("conversation", "snippets", "monitoring"):
            if args.suite not in {"all", suite}:
                continue
            suite_deadline = time.monotonic() + (
                profile.dialogue_suite_seconds
                if suite == "conversation"
                else profile.snippet_suite_seconds
            )
            if suite == "monitoring":
                cases = {
                    "normal": {
                        "observation_ids": ["obs-normal"],
                        "issue": "none",
                        "sample_count": 20,
                        "mean_latency_ms": 2,
                        "partial": False,
                    },
                    "partial": {
                        "observation_ids": ["obs-partial"],
                        "issue": "latency_threshold_exceeded",
                        "sample_count": 100,
                        "mean_latency_ms": 150,
                        "partial": True,
                    },
                }
            else:
                cases = PROMPTS if suite == "conversation" else CASES
            for name, prompt in cases.items():
                item = {"suite": suite, "scenario": name, "input_hash": fingerprint(prompt)}
                report["cases"].append(item)
                started = time.monotonic()
                try:
                    assert suite_deadline - started >= settings.chat_model_timeout_seconds
                    async with asyncio.timeout(min(60, suite_deadline - started)):
                        if suite == "monitoring":
                            step = await model.generate_monitoring(
                                [{"role": "user", "content": json.dumps(prompt)}]
                            )
                            assert step.advice.observation_ids
                            assert set(step.advice.observation_ids) <= set(
                                prompt["observation_ids"]
                            )
                            item["step"] = model._safe(step.model_dump(mode="json"))
                        else:
                            transport = (
                                FixtureTransport()
                                if suite == "conversation"
                                else EmptyTransport({})
                            )
                            store = MemoryConversations()
                            service = ConversationService(settings, store, observed, transport)
                            request = ChatRequest(
                                request_id=name, expected_revision=0, message=prompt
                            )
                            turn = await service.chat(ToolContext(project_id="demo"), request)
                            item["turn"] = model._safe(turn.model_dump(mode="json"))
                            if suite == "conversation":
                                check_case(name, turn, transport)
                            else:
                                check_snippet_case(name, turn, transport, backend="openai")
                            calls_before = len(report["calls"])
                            replay = await service.chat(ToolContext(project_id="demo"), request)
                            assert replay == turn and len(report["calls"]) == calls_before
                    assert time.monotonic() - started <= profile.client_seconds
                    item["passed"] = True
                except Exception as exc:
                    item["passed"] = False
                    item["failure_type"] = type(exc).__name__
                    item["error_code"] = getattr(exc, "code", None)
                finally:
                    item["elapsed_seconds"] = time.monotonic() - started
                    report["estimated_reserved_usd"] = str(budget.reserved)
                    args.output.parent.mkdir(parents=True, exist_ok=True)
                    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
                if budget.reserved >= Decimal("1.89"):
                    return


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suite", choices=("all", "conversation", "snippets", "monitoring"), default="all"
    )
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/openai-provider/live-results.json")
    )
    args = parser.parse_args()
    if os.getenv("MLPP_RUN_OPENAI_EVAL") != "1":
        parser.error("Set MLPP_RUN_OPENAI_EVAL=1; this gate makes paid external calls")
    report = {
        "source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "working_tree": True,
        "utc_started": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "source_hashes": {
            str(p): fingerprint(p.read_text(encoding="utf-8"))
            for p in sorted(Path("src/ml_pipeline_pro").glob("*.py"))
        },
        "metrics_origin": "synthetic fixtures, not measured training results",
        "pricing_basis": "approved conservative estimate; counting tariff unconfirmed",
        "human_quality_review_required": True,
        "code_execution": False,
        "calls": [],
        "provider_requests": [],
        "cases": [],
    }
    with OpenAITestBudget(LEDGER) as budget:
        asyncio.run(evaluate(args, report, budget))
    expected = {"conversation": 10, "snippets": 7, "monitoring": 2, "all": 19}[args.suite]
    passed = sum(item["passed"] for item in report["cases"])
    print(f"Hosted scenarios: {passed}/{expected}; estimated reservations ${budget.reserved}")
    return 0 if len(report["cases"]) == expected and passed == expected else 1


if __name__ == "__main__":
    raise SystemExit(main())
