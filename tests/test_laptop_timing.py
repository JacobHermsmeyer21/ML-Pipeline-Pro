import asyncio
import json
import logging
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from examples import midterm_walkthrough
from examples.midterm_walkthrough import timed_ai_post
from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.conversation_schemas import ChatRequest
from ml_pipeline_pro.conversation_service import ConversationService
from ml_pipeline_pro.conversation_timing import timed_boundary, timing_profile
from ml_pipeline_pro.errors import ApiError
from ml_pipeline_pro.laptop_deployment import render_laptop_profile
from ml_pipeline_pro.tool_schemas import ToolContext
from tests.conversation_memory import MemoryConversations
from tests.test_conversation_service import RecordsTransport, ScriptedModel, call, reply


def test_laptop_profile_is_explicit_and_default_settings_stay_unchanged(monkeypatch):
    defaults = Settings(_env_file=None, **timing_profile("default").settings_overrides())
    assert (defaults.chat_model_timeout_seconds, defaults.chat_timeout_seconds) == (20, 60)
    settings = Settings(_env_file=None, **timing_profile("laptop-five-minute").settings_overrides())
    assert (settings.chat_model_timeout_seconds, settings.chat_timeout_seconds) == (240, 270)
    assert settings.chat_action_timeout_seconds == defaults.chat_action_timeout_seconds == 30
    assert settings.chat_max_model_calls == defaults.chat_max_model_calls == 5
    assert settings.chat_max_output_tokens == defaults.chat_max_output_tokens == 1024
    monkeypatch.setenv("MLPP_CHAT_TIMEOUT_SECONDS", "100")
    assert (
        Settings(
            _env_file=None, **timing_profile("default").settings_overrides()
        ).chat_timeout_seconds
        == 100
    )
    with pytest.raises(ValueError, match="Unknown"):
        timing_profile("unlimited")


@pytest.mark.parametrize("field", ["chat_timeout_seconds", "chat_model_timeout_seconds"])
@pytest.mark.parametrize("value", [0, -1, 301, float("nan"), float("inf")])
def test_approved_ceiling_remains_finite_and_bounded(field, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})


def test_exact_approved_ceiling_is_accepted_without_extending_actions():
    settings = Settings(_env_file=None, chat_timeout_seconds=300, chat_model_timeout_seconds=300)
    assert settings.chat_model_timeout_seconds == settings.chat_timeout_seconds == 300
    assert settings.chat_action_timeout_seconds == 30


def test_laptop_multiple_model_calls_share_one_turn_timeout(monkeypatch):
    async def run():
        seen = []
        real_timeout = asyncio.timeout
        turn_timer = None

        def shortened(seconds):
            nonlocal turn_timer
            seen.append(seconds)
            if seconds == 270:
                turn_timer = real_timeout(None)
                return turn_timer
            return real_timeout(1)

        monkeypatch.setattr(asyncio, "timeout", shortened)

        async def first(_):
            return call("list_models", limit=50, offset=0)

        cancelled = []

        async def second(_):
            try:
                turn_timer.reschedule(asyncio.get_running_loop().time())
                await asyncio.sleep(1)
                return reply()
            finally:
                cancelled.append(True)

        model = ScriptedModel(first, second)
        store = MemoryConversations()
        config = Settings(
            _env_file=None,
            chat_enabled=True,
            **timing_profile("laptop-five-minute").settings_overrides(),
        )
        service = ConversationService(
            config,
            store,
            model,
            RecordsTransport({"/api/v1/models": {"items": [], "limit": 50, "offset": 0}}),
        )
        with pytest.raises(ApiError) as caught:
            await service.chat(
                ToolContext(project_id="demo"),
                ChatRequest(request_id="expiry", message="Read", expected_revision=0),
            )
        assert caught.value.code == "chat_timeout"
        assert seen == [270, 240, 240]
        assert cancelled == [True] and len(model.messages) == 2

    asyncio.run(run())


def test_rendered_laptop_manifest_preserves_replicas_routing_and_retry_policy(tmp_path):
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(render_laptop_profile(root, tmp_path).read_text())
    canonical = json.loads((root / "deploy/kubernetes/stack.json").read_text())
    by_name = {(i["kind"], i["metadata"]["name"]): i for i in manifest["items"]}
    for name in ["model-api", "monitoring-api"]:
        deployment = by_name[("Deployment", name)]
        env = deployment["spec"]["template"]["spec"]["containers"][0]["env"]
        values = {e["name"]: e.get("value") for e in env}
        assert values["MLPP_CHAT_MODEL_TIMEOUT_SECONDS"] == "240"
        assert values["MLPP_CHAT_TIMEOUT_SECONDS"] == "270"
        assert values["MLPP_CHAT_PROTOCOL"] == "guided"
    assert by_name[("Deployment", "model-api")]["spec"]["replicas"] == 2
    for item in canonical["items"]:
        if item["kind"] == "Deployment" and item["metadata"]["name"] in {
            "worker",
            "scheduler",
            "tuning-api",
        }:
            assert by_name[(item["kind"], item["metadata"]["name"])] == item
    gateway = by_name[("ConfigMap", "gateway-config")]["data"]["nginx.conf"]
    assert "proxy_read_timeout 310s;" in gateway
    assert "proxy_next_upstream off;" in gateway
    assert "kube-dns.kube-system.svc.cluster.local" in gateway
    for domain in ("model-api", "tuning-api", "monitoring-api"):
        assert f"http://{domain}.mlpp-demo.svc.cluster.local:8000" in gateway
        assert f"http://{domain}:8000" not in gateway
    assert "X-Correlation-ID $correlation_id" in gateway
    for path in ["/api/v1/tuning-jobs", "/api/v1/monitoring", "/tuning/", "/monitoring/"]:
        assert path in gateway


def test_walkthrough_records_failed_response_and_uses_selected_client_wait(tmp_path):
    timeouts = []

    def handler(request):
        timeouts.append(request.extensions["timeout"]["read"])
        return httpx.Response(504, json={"error": {"code": "chat_timeout"}})

    result = {}
    with httpx.Client(
        base_url="http://localhost", transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(httpx.HTTPStatusError):
            timed_ai_post(
                client,
                "/api/v1/chat",
                profile=timing_profile("laptop-five-minute"),
                result=result,
                output=tmp_path / "result.json",
            )
    retained = json.loads((tmp_path / "result.json").read_text())["ai_requests"][0]
    assert timeouts == [300]
    assert retained["status_code"] == 504 and retained["elapsed_seconds"] >= 0
    assert retained["failure_type"] == "HTTPStatusError"


def test_boundary_logs_preserve_cancellation_without_exception_or_payload(caplog):
    with caplog.at_level(logging.INFO, logger="ml_pipeline_pro.conversation_timing"):
        with pytest.raises(asyncio.CancelledError):
            with timed_boundary("model_inference", "fixture"):
                raise asyncio.CancelledError("must-not-log")
    assert "event=start" in caplog.text and "outcome=cancelled" in caplog.text
    assert "must-not-log" not in caplog.text
    assert caplog.records[-1].duration_ms >= 0


def test_walkthrough_rejects_late_success_and_retains_elapsed_failure(tmp_path, monkeypatch):
    from types import SimpleNamespace

    ticks = iter([0, 301, 301])
    monkeypatch.setattr(midterm_walkthrough, "time", SimpleNamespace(monotonic=lambda: next(ticks)))
    with httpx.Client(
        base_url="http://localhost",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"status": "completed"})
        ),
    ) as client:
        with pytest.raises(AssertionError, match="exceeded"):
            timed_ai_post(
                client,
                "/api/v1/chat",
                profile=timing_profile("laptop-five-minute"),
                result={},
                output=tmp_path / "late.json",
            )
    attempt = json.loads((tmp_path / "late.json").read_text())["ai_requests"][0]
    assert attempt["status_code"] == 200
    assert attempt["elapsed_seconds"] == 301 and attempt["failure_type"] == "AssertionError"
