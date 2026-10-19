"""Explicit diagnostic opt-in, unlimited waits and preserved normal deployments."""

import asyncio
import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from examples.midterm_walkthrough import timed_ai_post
from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.conversation_schemas import ChatRequest
from ml_pipeline_pro.conversation_service import ConversationService
from ml_pipeline_pro.conversation_store import TurnClaim
from ml_pipeline_pro.conversation_timing import DIAGNOSTIC_PROFILE, timing_profile
from ml_pipeline_pro.laptop_deployment import render_laptop_profile
from ml_pipeline_pro.tool_schemas import ToolContext
from tests.conversation_memory import MemoryConversations
from tests.test_conversation_ollama import Runtime, settings
from tests.test_conversation_service import RecordsTransport, ScriptedModel, reply


def diagnostic_settings(**changes):
    return Settings(
        _env_file=None,
        chat_enabled=True,
        **(timing_profile(DIAGNOSTIC_PROFILE).settings_overrides() | changes),
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"chat_timeout_seconds": None},
        {"chat_model_timeout_seconds": None},
        {"chat_unbounded_diagnostic": True},
        {"chat_unbounded_diagnostic": True, "chat_timeout_seconds": None},
        {"chat_unbounded_diagnostic": True, "chat_model_timeout_seconds": None},
        {
            "chat_unbounded_diagnostic": True,
            "chat_timeout_seconds": None,
            "chat_model_timeout_seconds": None,
            "environment": "production",
            "project_api_keys": {"diagnostic": "fixture-long-project-key"},
        },
        {
            "chat_unbounded_diagnostic": True,
            "chat_timeout_seconds": 0,
            "chat_model_timeout_seconds": None,
        },
    ],
)
def test_invalid_or_partial_diagnostic_configuration_is_rejected(changes):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **changes)


def test_diagnostic_env_nulls_are_explicit_and_finite_profiles_are_preserved(monkeypatch):
    monkeypatch.setenv("MLPP_CHAT_UNBOUNDED_DIAGNOSTIC", "true")
    monkeypatch.setenv("MLPP_CHAT_TIMEOUT_SECONDS", "none")
    monkeypatch.setenv("MLPP_CHAT_MODEL_TIMEOUT_SECONDS", "none")
    config = Settings(_env_file=None)
    assert config.chat_timeout_seconds is config.chat_model_timeout_seconds is None
    for name, expected in [("default", (20, 60, 90)), ("laptop-five-minute", (240, 270, 300))]:
        profile = timing_profile(name)
        assert (profile.model_seconds, profile.turn_seconds, profile.client_seconds) == expected


def test_unmarked_null_claim_is_rejected_and_expiry_uses_saved_claim_mode():
    now = datetime.now(UTC)
    with pytest.raises(ValueError):
        TurnClaim(None, "owner", None, False)
    finite = TurnClaim(None, "owner", now + timedelta(seconds=1), False)
    unbounded = TurnClaim(None, "owner", None, False, "diagnostic_unbounded")
    assert finite.expired(now + timedelta(seconds=301))
    assert not unbounded.expired(now + timedelta(days=10))


def test_unbounded_host_finishes_after_300_seconds_and_replays_without_generation(monkeypatch):
    real_timeout = asyncio.timeout
    timers = []

    def observed_timeout(delay):
        timers.append(delay)
        return real_timeout(delay)

    monkeypatch.setattr(asyncio, "timeout", observed_timeout)

    async def run():
        start = datetime.now(UTC)
        clock = [start]

        class SlowModel(ScriptedModel):
            async def generate(self, messages):
                clock[0] = start + timedelta(seconds=601)
                return await super().generate(messages)

        model = SlowModel(reply(message="Observed answer"))
        store = MemoryConversations()
        service = ConversationService(
            diagnostic_settings(), store, model, RecordsTransport({}), clock=lambda: clock[0]
        )
        context = ToolContext(project_id="diagnostic")
        request = ChatRequest(request_id="long", message="Guide me", expected_revision=0)
        result = await service.chat(context, request)
        assert result.status == "completed"
        claim = store.claims[result.turn_id]
        assert claim.timeout_mode == "diagnostic_unbounded" and claim.deadline is None
        assert await service.chat(context, request) == result
        assert len(model.messages) == 1

    asyncio.run(run())
    assert timers and all(delay is None for delay in timers)


def test_unbounded_snippet_admission_uses_saved_mode_after_300_seconds():
    from tests.test_snippet_generation import Generator

    async def run():
        start = datetime.now(UTC)
        clock = [start]

        class SlowGenerator(Generator):
            async def generate(self, messages):
                clock[0] = start + timedelta(seconds=601)
                return await super().generate(messages)

        model = SlowGenerator()
        service = ConversationService(
            diagnostic_settings(),
            MemoryConversations(),
            model,
            RecordsTransport({}),
            clock=lambda: clock[0],
        )
        result = await service.chat(
            ToolContext(project_id="diagnostic"),
            ChatRequest(request_id="snippet", message="Generate Python", expected_revision=0),
        )
        assert result.status == "completed" and result.snippet.status == "validated"
        assert result.snippet.review_required and result.pending_action is None
        model.generate_snippet.assert_awaited_once()

    asyncio.run(run())


def test_diagnostic_sdk_sends_no_http_deadline():
    async def run():
        runtime = Runtime()
        config = settings(
            chat_unbounded_diagnostic=True,
            chat_timeout_seconds=None,
            chat_model_timeout_seconds=None,
        )
        async with runtime.model(config) as model:
            await model.generate([{"role": "user", "content": "Guide me"}])
        assert runtime.requests
        assert all(
            all(value is None for value in req.extensions["timeout"].values())
            for req in runtime.requests
        )

    asyncio.run(run())


def test_diagnostic_client_records_late_reply_without_a_bounded_acceptance(tmp_path, monkeypatch):
    ticks = iter([0.0, 601.0])
    monkeypatch.setattr("examples.midterm_walkthrough.time.monotonic", lambda: next(ticks))

    def handler(request):
        assert all(value is None for value in request.extensions["timeout"].values())
        return httpx.Response(200, json={"status": "completed"})

    result = {"bounded_profile_acceptance": False}
    with httpx.Client(
        base_url="http://localhost", transport=httpx.MockTransport(handler)
    ) as client:
        timed_ai_post(
            client,
            "/api/v1/chat",
            profile=timing_profile(DIAGNOSTIC_PROFILE),
            result=result,
            output=tmp_path / "result.json",
        )
    assert result["ai_requests"][0]["elapsed_seconds"] == 601
    assert result["bounded_profile_acceptance"] is False


def test_only_diagnostic_application_probes_are_removed(tmp_path):
    root = Path(__file__).resolve().parents[1]
    canonical = json.loads((root / "deploy/kubernetes/stack.json").read_text())
    normal = json.loads(render_laptop_profile(root, tmp_path / "normal").read_text())
    diagnostic = json.loads(
        render_laptop_profile(
            root, tmp_path / "diagnostic", profile_name=DIAGNOSTIC_PROFILE
        ).read_text()
    )
    expected = copy.deepcopy(normal)
    for item in expected["items"]:
        if item["kind"] != "Deployment":
            continue
        name = item["metadata"]["name"]
        for container in item["spec"]["template"]["spec"]["containers"]:
            if name in {"gateway", "model-api", "tuning-api", "monitoring-api"}:
                for probe in ["readinessProbe", "startupProbe", "livenessProbe"]:
                    container.pop(probe, None)
            if name in {"model-api", "monitoring-api"}:
                for entry in container["env"]:
                    if entry["name"] in {
                        "MLPP_CHAT_TIMEOUT_SECONDS",
                        "MLPP_CHAT_MODEL_TIMEOUT_SECONDS",
                    }:
                        entry["value"] = "none"
                container["env"].append({"name": "MLPP_CHAT_UNBOUNDED_DIAGNOSTIC", "value": "true"})
    assert diagnostic == expected
    assert json.loads((root / "deploy/kubernetes/stack.json").read_text()) == canonical
