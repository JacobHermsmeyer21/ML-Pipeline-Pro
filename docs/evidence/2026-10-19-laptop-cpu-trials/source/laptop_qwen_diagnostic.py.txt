"""Opt-in first-step diagnostic, separate from application acceptance gates."""

import argparse
import asyncio
import ctypes
import hashlib
import json
import platform
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from evaluations.qwen_counter import create_counter
from evaluations.test_conversation_model import PROMPTS, FixtureTransport
from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.conversation_ollama import OllamaConversationModel, _json_object
from ml_pipeline_pro.conversation_qwen_counter import JSON_TOOLS_TAG
from ml_pipeline_pro.conversation_schemas import RECORD_BYTES, ChatRequest, fingerprint
from ml_pipeline_pro.conversation_service import ConversationService
from ml_pipeline_pro.tool_schemas import ToolContext
from tests.conversation_memory import MemoryConversations

ORIGIN = "http://127.0.0.1:11434"
WALL_SECONDS = 480
WARMUP_SECONDS = 120


class Captured(BaseException):
    """Stop before dispatch; bypass host error handling without repairing output."""


def config():
    # Ignore operator chat overrides as well as .env; this is a fixed diagnostic.
    return Settings(
        _env_file=None,
        chat_enabled=True,
        chat_model=JSON_TOOLS_TAG,
        chat_protocol="guided",
        chat_model_origin=ORIGIN,
        chat_context_tokens=8192,
        chat_max_output_tokens=1024,
        chat_model_timeout_seconds=20,
        chat_timeout_seconds=60,
    )


async def host_messages(settings):
    class FirstCall:
        provenance = {}

        async def generate(self, messages):
            self.messages = messages
            raise Captured

    first = FirstCall()
    transport = FixtureTransport()
    service = ConversationService(settings, MemoryConversations(), first, transport)
    try:
        await service.chat(
            ToolContext(project_id="demo"),
            ChatRequest(
                request_id="read_guidance", message=PROMPTS["read_guidance"], expected_revision=0
            ),
        )
    except Captured:
        pass
    else:
        raise ValueError("Host did not reach the first model boundary")
    if transport.calls:
        raise ValueError("Unexpected tool execution")
    return first.messages


async def capture(settings, messages, metadata, counter):
    bodies = []

    async def handle(request):
        if request.url.path == "/api/chat":
            bodies.append(request.content)
            # A synthetic reply lets the SDK finish without exception wrapping.
            # It is never diagnostic evidence or sent to the real runtime.
            return httpx.Response(
                200,
                json={
                    "model": settings.chat_model,
                    "done": True,
                    "done_reason": "stop",
                    "message": {
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
                    "prompt_eval_count": 0,
                    "eval_count": 0,
                },
            )
        return httpx.Response(200, json=metadata[request.url.path])

    async with OllamaConversationModel(
        settings,
        count_input_tokens=counter,
        async_transport=httpx.MockTransport(handle),
        sync_transport=httpx.MockTransport(lambda _: (_ for _ in ()).throw(AssertionError())),
    ) as model:
        provenance = dict(model.provenance)
        await model.generate(messages)
        if len(bodies) != 1:
            raise ValueError("Expected one captured SDK request")
    return bodies[0], provenance


async def bounded_post(client, path, body, seconds):
    return await bounded_request(client, "POST", path, body, seconds)


async def bounded_request(client, method, path, body=b"", seconds=20):
    """Bound the entire response, including a stalled or oversized body; no retry."""
    started = time.monotonic()
    async with asyncio.timeout(seconds):
        async with client.stream(
            method, path, content=body, headers={"content-type": "application/json"}
        ) as response:
            response.raise_for_status()
            chunks, size = [], 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > RECORD_BYTES:
                    raise ValueError("Response exceeds record byte limit")
                chunks.append(chunk)
    return b"".join(chunks), time.monotonic() - started


async def validate_response(settings, messages, metadata, counter, expected_body, raw):
    requests = []

    async def handle(request):
        if request.url.path == "/api/chat":
            requests.append(request.content)
            return httpx.Response(200, content=raw)
        return httpx.Response(200, json=metadata[request.url.path])

    async with OllamaConversationModel(
        settings, count_input_tokens=counter, async_transport=httpx.MockTransport(handle)
    ) as model:
        step = await model.generate(messages)
    if requests != [expected_body]:
        raise ValueError("Validation SDK request differs from measured payload")
    if step.call is None or step.call.name != "get_experiment":
        raise ValueError("Expected original get_experiment read")
    if step.call.arguments != {"experiment_id": "exp-low"}:
        raise ValueError("Incorrect scoped inspection arguments")
    data = _json_object(raw.decode())
    if data["prompt_eval_count"] != counter(json.loads(expected_body)):
        raise ValueError("Runtime/tokenizer prompt count mismatch")
    return step.model_dump(mode="json")


def timings(raw):
    data = _json_object(raw.decode())
    result = {}
    for key in ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration"):
        value = data.get(key)
        if type(value) is not int or value < 0:
            raise ValueError("Invalid nanosecond timing")
        result[key + "_seconds"] = value / 1_000_000_000
    for key in ("prompt_eval_count", "eval_count"):
        value = data.get(key)
        if type(value) is not int or value < 0:
            raise ValueError("Invalid token count")
        result[key] = value
    return result


def resources():
    """Small Windows API observations; unavailable data stays explicit."""
    if platform.system() != "Windows":
        return {"unavailable": True}

    class Memory(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong)
            for name in (
                "total",
                "available",
                "page_total",
                "page_available",
                "vtotal",
                "vfree",
                "ext",
            )
        ]

    memory = Memory()
    memory.length = ctypes.sizeof(memory)
    idle, kernel, user = (ctypes.c_ulonglong() for _ in range(3))
    api = ctypes.windll.kernel32
    if not api.GlobalMemoryStatusEx(ctypes.byref(memory)) or not api.GetSystemTimes(
        ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
    ):
        return {"unavailable": True}
    return {
        "monotonic_seconds": time.monotonic(),
        "physical_total_bytes": memory.total,
        "physical_available_bytes": memory.available,
        "commit_limit_bytes": memory.page_total,
        "commit_available_bytes": memory.page_available,
        "cpu_idle_100ns": idle.value,
        "cpu_kernel_100ns": kernel.value,
        "cpu_user_100ns": user.value,
    }


async def sample_until_cancelled(samples):
    while True:
        samples.append(resources())
        await asyncio.sleep(5)


async def run(output, machine, *, transport=None):
    if "Ryzen 3 3350U" not in machine.get("cpu", "") or "Acer" not in machine.get(
        "manufacturer", ""
    ):
        raise ValueError("Presentation laptop identity not verified; stop")
    output.mkdir(parents=True, exist_ok=False)
    revision = await asyncio.to_thread(
        subprocess.check_output, ["git", "rev-parse", "HEAD"], text=True
    )
    working_tree = await asyncio.to_thread(
        subprocess.check_output, ["git", "status", "--porcelain"], text=True
    )
    source = await asyncio.to_thread(Path(__file__).read_bytes)
    report = {
        "started_utc": datetime.now(UTC).isoformat(),
        "source_revision": revision.strip(),
        "working_tree": working_tree,
        "script_sha256": hashlib.sha256(source).hexdigest(),
        "machine": {
            key: machine.get(key)
            for key in (
                "cpu",
                "cores",
                "logical_processors",
                "manufacturer",
                "model",
                "physical_memory_bytes",
                "gpu",
                "power_plan",
            )
        },
        "platform": platform.platform(),
        "python": platform.python_version(),
        "scenario": "read_guidance",
        "budget": {"inference_seconds": WALL_SECONDS, "warmup_seconds": WARMUP_SECONDS},
        "application_acceptance": "not evaluated",
        "diagnostic_status": "failed",
        "phase": "preflight",
        "inference_requests": 0,
        "resource_samples": [],
        "cache_conditions": "Explicit warmup only; existing runtime prefix cache not cleared",
        "runner_activity_after_cancellation": (
            "unknown; do not issue another request without inspection"
        ),
    }
    settings = config()
    try:
        async with httpx.AsyncClient(
            base_url=ORIGIN,
            timeout=httpx.Timeout(480, connect=5),
            trust_env=False,
            follow_redirects=False,
            transport=transport or httpx.AsyncHTTPTransport(retries=0),
        ) as client:
            metadata = {}
            for path in ("/api/tags", "/api/show", "/api/version"):
                raw, _ = await bounded_request(
                    client,
                    "POST" if path == "/api/show" else "GET",
                    path,
                    json.dumps({"model": settings.chat_model}).encode()
                    if path == "/api/show"
                    else b"",
                )
                metadata[path] = _json_object(raw.decode())
            # A metadata-only prepare supplies the pinned counter's provenance.
            async with OllamaConversationModel(
                settings,
                async_transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, json=metadata[request.url.path])
                ),
            ) as model:
                counter = create_counter(model.provenance)
            messages = await host_messages(settings)
            body, provenance = await capture(settings, messages, metadata, counter)
            payload = json.loads(body)
            if payload["options"]["num_ctx"] != 8192 or payload["options"]["num_predict"] != 1024:
                raise ValueError("Unexpected SDK token bounds")
            report.update(
                provenance=provenance,
                counter_identity=counter.identity,
                request_sha256=hashlib.sha256(body).hexdigest(),
                request_fingerprint=fingerprint(payload),
                admitted_input_tokens=counter(payload),
            )
            (output / "request.json").write_bytes(body)
            raw, _ = await bounded_request(client, "GET", "/api/ps")
            report["loaded_before_warmup"] = _json_object(raw.decode())
            warm = json.dumps(
                {
                    "model": settings.chat_model,
                    "keep_alive": "10m",
                    "stream": False,
                    "options": {"num_ctx": 8192},
                }
            ).encode()
            report["phase"] = "warmup"
            warm_started = time.monotonic()
            try:
                warm_raw, _ = await bounded_post(client, "/api/generate", warm, WARMUP_SECONDS)
            finally:
                report["warmup_seconds"] = time.monotonic() - warm_started
            (output / "warmup.json").write_bytes(warm_raw)
            if _json_object(warm_raw.decode()).get("done") is not True:
                raise ValueError("Warmup did not complete")
            raw, _ = await bounded_request(client, "GET", "/api/ps")
            loaded = _json_object(raw.decode())
            report["loaded_after_warmup"] = loaded
            if len(loaded["models"]) != 1 or any(
                loaded["models"][0].get(key) != value
                for key, value in {
                    "name": settings.chat_model,
                    "digest": provenance["artifact_digest"],
                    "context_length": 8192,
                }.items()
            ):
                raise ValueError("Expected one resident model with context 8192")
            report["phase"] = "inference"
            report["inference_requests"] = 1
            sampler = asyncio.create_task(sample_until_cancelled(report["resource_samples"]))
            started = time.monotonic()
            try:
                raw, elapsed = await bounded_post(client, "/api/chat", body, WALL_SECONDS)
                report["inference_wall_seconds"] = elapsed
            finally:
                report["inference_wall_seconds"] = time.monotonic() - started
                sampler.cancel()
                await asyncio.gather(sampler, return_exceptions=True)
            (output / "response.json").write_bytes(raw)
            report["eventual_response"] = True
            report["phase"] = "validation"
            report["timings"] = timings(raw)
            report["validated_step"] = await validate_response(
                settings, messages, metadata, counter, body, raw
            )
            report["semantic_valid"] = True
            raw, _ = await bounded_request(client, "GET", "/api/ps")
            report["loaded_after_response"] = _json_object(raw.decode())
            report["runner_activity_after_cancellation"] = (
                "not cancelled; complete response received"
            )
            report["diagnostic_status"] = "passed"
            report["phase"] = "complete"
    except Exception as exc:
        report["diagnostic_status"] = "failed"
        report["error_type"] = type(exc).__name__
        report.setdefault("semantic_valid", False)
        report.setdefault("eventual_response", False)
    finally:
        report["finished_utc"] = datetime.now(UTC).isoformat()
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-laptop-diagnostic", action="store_true", required=True)
    parser.add_argument("--machine-info", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = asyncio.run(
        run(args.output, json.loads(args.machine_info.read_text(encoding="utf-8-sig")))
    )
    print(
        json.dumps(
            {
                key: report.get(key)
                for key in (
                    "diagnostic_status",
                    "inference_wall_seconds",
                    "semantic_valid",
                    "error_type",
                    "timings",
                )
            },
            indent=2,
        )
    )
    return 0 if report["diagnostic_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
