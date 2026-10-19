import asyncio
import json

import httpx
import pytest

from evaluations import laptop_qwen_diagnostic as diagnostic
from evaluations.laptop_qwen_diagnostic import (
    bounded_post,
    capture,
    config,
    host_messages,
    timings,
    validate_response,
)
from evaluations.test_conversation_model import PROMPTS
from ml_pipeline_pro.conversation_model import ConversationModelError
from tests.test_conversation_ollama import SHOW, TAG, chat_response, settings


def metadata():
    return {
        "/api/tags": {"models": [{"name": TAG, "digest": "a" * 64}]},
        "/api/show": SHOW,
        "/api/version": {"version": "0.0.fixture"},
    }


def test_capture_uses_original_host_fixture_and_sdk_payload_without_dispatch():
    async def run():
        messages = await host_messages(config())
        assert messages[-1] == {"role": "user", "content": PROMPTS["read_guidance"]}
        counted = []
        body, _ = await capture(
            settings(chat_protocol="guided"),
            messages,
            metadata(),
            lambda payload: counted.append(payload) or 42,
        )
        payload = json.loads(body)
        assert counted == [payload]
        assert payload["options"]["num_ctx"] == 8192
        assert payload["options"]["num_predict"] == 1024
        assert payload["tools"] == [] and payload["stream"] is False
        assert payload["format"]

    asyncio.run(run())


def test_response_reuses_strict_adapter_and_expected_read_without_execution():
    async def run():
        cfg = settings(chat_protocol="guided", chat_enabled=True)
        messages = await host_messages(cfg)
        body, _ = await capture(cfg, messages, metadata(), lambda _: 42)
        valid = {"call": {"name": "get_experiment", "arguments": {"experiment_id": "exp-low"}}}
        raw = json.dumps(chat_response(message={"role": "assistant", "content": json.dumps(valid)}))
        step = await validate_response(cfg, messages, metadata(), lambda _: 42, body, raw.encode())
        assert step["call"] == valid["call"]
        for envelope in (
            {"call": {"name": "get_experiment", "arguments": {"experiment_id": "other"}}},
            {
                "call": {
                    "name": "get_experiment",
                    "arguments": {"experiment_id": "exp-low", "extra": 1},
                }
            },
            {"reply": {"message": "No read", "citations": [], "facts": []}},
            {"call": valid["call"], "extra": True},
        ):
            bad = json.dumps(
                chat_response(message={"role": "assistant", "content": json.dumps(envelope)})
            )
            with pytest.raises((ValueError, ConversationModelError)):
                await validate_response(cfg, messages, metadata(), lambda _: 42, body, bad.encode())
        for changes in ({"done_reason": "length"}, {"eval_count": 1025}, {"prompt_eval_count": 43}):
            bad = json.dumps(
                chat_response(
                    message={"role": "assistant", "content": json.dumps(valid)}, **changes
                )
            )
            with pytest.raises((ValueError, ConversationModelError)):
                await validate_response(cfg, messages, metadata(), lambda _: 42, body, bad.encode())

    asyncio.run(run())


class StalledBody(httpx.AsyncByteStream):
    closed = False

    async def __aiter__(self):
        yield b"{"
        await asyncio.sleep(10)

    async def aclose(self):
        self.closed = True


def test_wall_timeout_closes_stalled_response_and_never_retries():
    async def run():
        calls = []
        stream = StalledBody()

        def handle(request):
            calls.append(request)
            return httpx.Response(200, stream=stream)

        async with httpx.AsyncClient(
            base_url="http://127.0.0.1:11434", transport=httpx.MockTransport(handle)
        ) as client:
            with pytest.raises(TimeoutError):
                await bounded_post(client, "/api/chat", b"exact request", 0.03)
        assert len(calls) == 1 and calls[0].content == b"exact request"
        assert stream.closed and client.is_closed

    asyncio.run(run())


@pytest.mark.parametrize("mode", ["success", "http_error", "oversized"])
def test_transport_preserves_bytes_and_does_not_retry_errors(mode):
    async def run():
        calls = []

        def handle(request):
            calls.append(request)
            return httpx.Response(
                503 if mode == "http_error" else 200,
                content=b"x" * (300_000 if mode == "oversized" else 10),
            )

        async with httpx.AsyncClient(
            base_url="http://127.0.0.1:11434", transport=httpx.MockTransport(handle)
        ) as client:
            if mode == "success":
                raw, seconds = await bounded_post(client, "/api/chat", b"exact", 1)
                assert raw == b"x" * 10 and 0 <= seconds < 1
            else:
                with pytest.raises((httpx.HTTPStatusError, ValueError)):
                    await bounded_post(client, "/api/chat", b"exact", 1)
        assert len(calls) == 1 and calls[0].content == b"exact"

    asyncio.run(run())


def test_duration_units_and_counts_remain_separate():
    raw = json.dumps(
        {
            "total_duration": 4_000_000_000,
            "load_duration": 1_000_000_000,
            "prompt_eval_duration": 2_000_000_000,
            "eval_duration": 1_000_000_000,
            "prompt_eval_count": 42,
            "eval_count": 18,
        }
    ).encode()
    result = timings(raw)
    assert result["total_duration_seconds"] == 4
    assert result["prompt_eval_duration_seconds"] == 2
    assert result["prompt_eval_count"] == 42


@pytest.mark.parametrize("failure", [None, "preflight", "warmup", "residency", "after_response"])
def test_complete_diagnostic_sends_one_exact_inference_and_stops_on_setup_failure(
    monkeypatch, tmp_path, failure
):
    cfg = settings(chat_enabled=True, chat_protocol="guided")
    monkeypatch.setattr(diagnostic, "config", lambda: cfg)

    class Counter:
        identity = {"fixture": True}

        def __call__(self, _):
            return 42

    monkeypatch.setattr(diagnostic, "create_counter", lambda _: Counter())
    calls, ps_calls = [], []

    def handle(request):
        calls.append(request)
        path = request.url.path
        if path in metadata():
            return httpx.Response(503 if failure == "preflight" else 200, json=metadata()[path])
        if path == "/api/ps":
            ps_calls.append(True)
            if failure == "after_response" and len(ps_calls) == 3:
                return httpx.Response(503)
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "other" if failure == "residency" else TAG,
                            "digest": "a" * 64,
                            "context_length": 8192,
                            "size_vram": 0,
                        }
                    ]
                },
            )
        if path == "/api/generate":
            assert json.loads(request.content) == {
                "model": TAG,
                "keep_alive": "10m",
                "stream": False,
                "options": {"num_ctx": 8192},
            }
            return httpx.Response(200, json={"done": failure != "warmup"})
        assert path == "/api/chat"
        assert request.content == (tmp_path / "run/request.json").read_bytes()
        return httpx.Response(
            200,
            json=chat_response(
                message={
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "call": {
                                "name": "get_experiment",
                                "arguments": {"experiment_id": "exp-low"},
                            }
                        }
                    ),
                },
                total_duration=4_000_000_000,
                load_duration=1_000_000_000,
                prompt_eval_duration=2_000_000_000,
                eval_duration=1_000_000_000,
            ),
        )

    report = asyncio.run(
        diagnostic.run(
            tmp_path / "run",
            {"cpu": "Ryzen 3 3350U", "manufacturer": "Acer"},
            transport=httpx.MockTransport(handle),
        )
    )
    expected = 1 if failure in (None, "after_response") else 0
    assert sum(request.url.path == "/api/chat" for request in calls) == expected
    assert report["inference_requests"] == expected
    assert report["diagnostic_status"] == ("passed" if failure is None else "failed")
    assert (tmp_path / "run/result.json").is_file()
    assert all(
        request.url.path
        in {"/api/tags", "/api/show", "/api/version", "/api/ps", "/api/generate", "/api/chat"}
        for request in calls
    )


def test_wrong_machine_stops_before_transport_or_output(tmp_path):
    with pytest.raises(ValueError, match="laptop identity"):
        asyncio.run(diagnostic.run(tmp_path / "run", {"cpu": "different machine"}))
    assert not (tmp_path / "run").exists()
