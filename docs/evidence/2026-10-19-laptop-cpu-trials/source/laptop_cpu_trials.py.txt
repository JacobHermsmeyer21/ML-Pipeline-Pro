"""Approved, serial CPU-laptop profiling and request-local thread experiments."""

import argparse
import asyncio
import hashlib
import json
import platform
import re
import statistics
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from evaluations import laptop_qwen_diagnostic as diagnostic
from evaluations.qwen_counter import create_counter
from ml_pipeline_pro.conversation_ollama import OllamaConversationModel

TOTAL_SECONDS = 3600
TRIAL_RESERVE = 660
MAX_REQUESTS = 16
RUNNER_LOG = Path(".tools/test-prerequisites/ollama-stderr.log")


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def candidate_payload(body, threads):
    payload = json.loads(body)
    if threads not in (None, 2, 3, 4):
        raise ValueError("Unsupported thread candidate")
    if "num_thread" in payload["options"]:
        raise ValueError("Baseline already specifies threads")
    if threads is not None:
        payload["options"]["num_thread"] = threads
    return json.dumps(payload, separators=(",", ":")).encode()


def runner_settings(log):
    threads = re.findall(r"system_info: n_threads = (\d+) \(n_threads_batch = (\d+)\)", log)
    batches = re.findall(r"llama_context: n_batch\s*= (\d+)", log)
    micro = re.findall(r"llama_context: n_ubatch\s*= (\d+)", log)
    if not threads or not batches or not micro:
        raise ValueError("Effective inference settings unavailable")
    return {
        "threads": int(threads[-1][0]),
        "threads_batch": int(threads[-1][1]),
        "batch": int(batches[-1]),
        "micro_batch": int(micro[-1]),
    }


def eligible_response(raw, log):
    response = json.loads(raw)
    cached = response.get("prompt_eval_cached_count")
    starts = re.findall(r"cached n_tokens = (\d+), memory_seq_rm", log)
    if cached != 0 or not starts or int(starts[0]) != 0:
        raise ValueError("Zero-cache condition not verified")
    if "all slots are idle" not in log:
        raise ValueError("Runner idle after response not verified")
    return True


def enough_budget(started, count, *, now=None):
    now = time.monotonic() if now is None else now
    return count < MAX_REQUESTS and TOTAL_SECONDS - (now - started) >= TRIAL_RESERVE


def comparison(pairs):
    if len(pairs) != 3 or any(not a["eligible"] or not b["eligible"] for a, b in pairs):
        raise ValueError("Three eligible baseline/candidate pairs required")
    baseline = [a["wall_seconds"] for a, _ in pairs]
    candidate = [b["wall_seconds"] for _, b in pairs]
    base_median, candidate_median = statistics.median(baseline), statistics.median(candidate)
    improvement = 1 - candidate_median / base_median
    return {
        "baseline_seconds": baseline,
        "candidate_seconds": candidate,
        "baseline_median_seconds": base_median,
        "candidate_median_seconds": candidate_median,
        "baseline_range_seconds": [min(baseline), max(baseline)],
        "candidate_range_seconds": [min(candidate), max(candidate)],
        "median_improvement_fraction": improvement,
        "retain_candidate": candidate_median <= base_median * 0.8,
    }


def summarize_samples(samples, logical_processors):
    """Normalize cumulative CPU deltas by measured gaps and machine capacity."""
    if logical_processors <= 0:
        raise ValueError("Logical processor count required")
    intervals = []
    for before, after in zip(samples, samples[1:], strict=False):
        gap = after["observer_elapsed_seconds"] - before["observer_elapsed_seconds"]
        if gap <= 0 or before["phase"] != after["phase"]:
            continue
        old = {(p["pid"], p.get("start_utc")): p for p in before["processes"] if p.get("start_utc")}
        processes = []
        for process in after["processes"]:
            previous = old.get((process["pid"], process.get("start_utc")))
            if previous is None or any(p.get("cpu_seconds") is None for p in (previous, process)):
                continue
            delta = process["cpu_seconds"] - previous["cpu_seconds"]
            if delta < 0:
                continue
            processes.append(
                {
                    "pid": process["pid"],
                    "name": process.get("name", "unavailable"),
                    "cpu_seconds": delta,
                    "machine_cpu_fraction": delta / gap / logical_processors,
                }
            )
        item = {
            "phase": after["phase"],
            "gap_seconds": gap,
            "processes": sorted(processes, key=lambda p: -p["cpu_seconds"]),
            "sample_duration_seconds": after["duration_seconds"],
            "errors": after["errors"],
        }
        if "system_cpu" in before and "system_cpu" in after:
            deltas = {
                key: after["system_cpu"][key] - before["system_cpu"][key]
                for key in ("idle_100ns", "kernel_100ns", "user_100ns")
            }
            total = deltas["kernel_100ns"] + deltas["user_100ns"]
            if total > 0 and 0 <= deltas["idle_100ns"] <= total:
                item["system_busy_fraction"] = 1 - deltas["idle_100ns"] / total
        intervals.append(item)
    return {
        "sample_count": len(samples),
        "power_ac_states": sorted({s["power"]["ac_line_status"] for s in samples if "power" in s}),
        "same_phase_intervals": intervals,
        "max_gap_seconds": max(
            (
                b["observer_elapsed_seconds"] - a["observer_elapsed_seconds"]
                for a, b in zip(samples, samples[1:], strict=False)
            ),
            default=None,
        ),
        "max_sample_duration_seconds": max((s["duration_seconds"] for s in samples), default=None),
        "limits": "Approximate snapshots; inaccessible/short-lived processes cannot be attributed",
    }


class Observer:
    def __init__(self, output):
        self.output = output
        self.process = None
        self.ac_state = None

    def phase(self, name):
        (self.output / "phase.txt").write_text(name, encoding="utf-8")

    def start(self):
        self.phase("idle")
        self.stderr = (self.output / "observer-errors.log").open("wb")
        try:
            self.process = subprocess.Popen(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(Path(__file__).with_name("laptop_resource_observer.ps1").resolve()),
                    "-OutputPath",
                    str((self.output / "samples.jsonl").resolve()),
                    "-PhasePath",
                    str((self.output / "phase.txt").resolve()),
                    "-StopPath",
                    str((self.output / "stop.txt").resolve()),
                ],
                stdout=subprocess.DEVNULL,
                stderr=self.stderr,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except BaseException:
            self.stderr.close()
            raise

    def check(self):
        if self.process.poll() is not None:
            raise ValueError("Resource observer exited unexpectedly")
        samples = self.output / "samples.jsonl"
        if not samples.exists() or not samples.stat().st_size:
            raise ValueError("Resource observer produced no samples")
        with samples.open("rb") as stream:
            stream.seek(max(0, samples.stat().st_size - 1_000_000))
            raw = stream.read()
        lines = raw.splitlines()
        if not raw.endswith(b"\n"):
            lines = lines[:-1]
        ac_state = json.loads(lines[-1]).get("power", {}).get("ac_line_status")
        if ac_state not in (0, 1):
            raise ValueError("AC power state unavailable")
        if self.ac_state is not None and self.ac_state != ac_state:
            raise ValueError("AC power state changed; comparison ineligible")
        self.ac_state = ac_state

    def stop(self):
        if self.process is None:
            return {"started": False}
        (self.output / "stop.txt").touch()
        forced = False
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            forced = True
            self.process.terminate()
            self.process.wait(timeout=5)
        finally:
            self.stderr.close()
        return {"returncode": self.process.returncode, "forced_stop": forced}


async def prepare(client, output):
    settings = diagnostic.config()
    metadata = {}
    for path in ("/api/tags", "/api/show", "/api/version"):
        raw, _ = await diagnostic.bounded_request(
            client,
            "POST" if path == "/api/show" else "GET",
            path,
            json.dumps({"model": settings.chat_model}).encode() if path == "/api/show" else b"",
        )
        metadata[path] = json.loads(raw)
    if metadata["/api/version"].get("version") != "0.40.2":
        raise ValueError("Pinned runtime mismatch")
    async with OllamaConversationModel(
        settings,
        async_transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=metadata[request.url.path])
        ),
    ) as model:
        counter = create_counter(model.provenance)
    messages = await diagnostic.host_messages(settings)
    body, provenance = await diagnostic.capture(settings, messages, metadata, counter)
    if counter(json.loads(body)) != 1109:
        raise ValueError("Original 1109-token workload changed")
    save(output / "metadata.json", metadata)
    save(output / "provenance.json", {"model": provenance, "counter": counter.identity})
    (output / "baseline-request.json").write_bytes(body)
    return settings, metadata, messages, body, counter


def read_log(offset=0):
    with RUNNER_LOG.open("rb") as stream:
        stream.seek(offset)
        return stream.read().decode("utf-8", errors="replace")


def assert_idle():
    log = read_log()
    idle = log.rfind("all slots are idle")
    active = log.rfind("processing task, is_child")
    if active > idle:
        raise ValueError("Unknown residual runner activity; stop")


async def one_trial(client, root, name, threads, prepared, observer, expected=None):
    settings, metadata, messages, original, counter = prepared
    output = root / name
    output.mkdir()
    report = {
        "name": name,
        "threads_requested": threads,
        "eligible": False,
        "phase": "reset",
        "inference_requests": 0,
    }
    body = candidate_payload(original, threads)
    (output / "request.json").write_bytes(body)
    report["request_sha256"] = hashlib.sha256(body).hexdigest()
    try:
        assert_idle()
        observer.phase(name + ":reset")
        unload = json.dumps({"model": settings.chat_model, "keep_alive": 0}).encode()
        await diagnostic.bounded_post(client, "/api/generate", unload, 20)
        raw, _ = await diagnostic.bounded_request(client, "GET", "/api/ps")
        if json.loads(raw).get("models"):
            raise ValueError("Model unload not confirmed")
        log_offset = (await asyncio.to_thread(RUNNER_LOG.stat)).st_size
        report["phase"] = "warmup"
        observer.phase(name + ":warmup")
        warm = {
            "model": settings.chat_model,
            "keep_alive": "10m",
            "stream": False,
            "options": {"num_ctx": 8192},
        }
        if threads is not None:
            warm["options"]["num_thread"] = threads
        raw, elapsed = await diagnostic.bounded_post(
            client, "/api/generate", json.dumps(warm).encode(), diagnostic.WARMUP_SECONDS
        )
        (output / "warmup.json").write_bytes(raw)
        report["warmup_seconds"] = elapsed
        if json.loads(raw).get("done") is not True:
            raise ValueError("Warmup incomplete")
        raw, _ = await diagnostic.bounded_request(client, "GET", "/api/ps")
        resident = json.loads(raw)
        report["residency"] = resident
        if len(resident["models"]) != 1:
            raise ValueError("Expected one resident model")
        model = resident["models"][0]
        digest = next(
            tag["digest"]
            for tag in metadata["/api/tags"]["models"]
            if tag["name"] == settings.chat_model
        )
        if (
            model["name"] != settings.chat_model
            or model["context_length"] != 8192
            or model["digest"] != digest
            or model["size_vram"] != 0
        ):
            raise ValueError("CPU model/context/artifact mismatch")
        effective = runner_settings(read_log(log_offset))
        report["effective"] = effective
        if threads is not None and (
            effective["threads"] != threads or effective["threads_batch"] != threads
        ):
            raise ValueError("Requested thread count ignored")
        if expected and any(effective[key] != expected[key] for key in ("batch", "micro_batch")):
            raise ValueError("Automatic batch settings changed")
        observer.check()
        inference_offset = (await asyncio.to_thread(RUNNER_LOG.stat)).st_size
        observer.phase(name + ":inference")
        report["phase"] = "inference"
        report["inference_requests"] = 1
        inference_started = time.monotonic()
        try:
            raw, elapsed = await diagnostic.bounded_post(
                client, "/api/chat", body, diagnostic.WALL_SECONDS
            )
        finally:
            report["wall_seconds"] = time.monotonic() - inference_started
        (output / "response.json").write_bytes(raw)
        report["timings"] = diagnostic.timings(raw)
        report["phase"] = "validation"
        # The strict adapter constructs the original body. Only the approved
        # request-local thread option differs in the measured SDK payload.
        report["validated_step"] = await diagnostic.validate_response(
            settings, messages, metadata, counter, original, raw
        )
        log = read_log(inference_offset)
        eligible_response(raw, log)
        safe_lines = [
            line
            for line in read_log(log_offset).splitlines()
            if any(
                marker in line
                for marker in (
                    "system_info: n_threads",
                    "llama_context: n_",
                    "cached n_tokens",
                    "all slots are idle",
                    "print_timing:",
                    "stop processing:",
                )
            )
        ]
        (output / "runner.log").write_text("\n".join(safe_lines) + "\n", encoding="utf-8")
        observer.check()
        report["eligible"] = True
        report["phase"] = "complete"
        print(
            json.dumps(
                {
                    key: report[key]
                    for key in ("name", "wall_seconds", "warmup_seconds", "effective", "eligible")
                }
            ),
            flush=True,
        )
        return report
    except BaseException as exc:
        report["error_type"] = type(exc).__name__
        report["error"] = str(exc)
        raise
    finally:
        save(output / "result.json", report)


async def run(output, machine):
    if "Ryzen 3 3350U" not in machine.get("cpu", "") or machine.get("manufacturer") != "Acer":
        raise ValueError("Presentation laptop identity not verified")
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    report = {
        "started_utc": datetime.now(UTC).isoformat(),
        "machine": machine,
        "source_revision": (
            await asyncio.to_thread(
                subprocess.check_output, ["git", "rev-parse", "HEAD"], text=True
            )
        ).strip(),
        "working_tree": await asyncio.to_thread(
            subprocess.check_output, ["git", "status", "--porcelain"], text=True
        ),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "budget": {
            "total_seconds": TOTAL_SECONDS,
            "max_requests": MAX_REQUESTS,
            "trial_reserve_seconds": TRIAL_RESERVE,
        },
        "trials": [],
        "status": "failed",
        "application_acceptance": "not evaluated",
        "duplicate_stack_candidate": "omitted; one required stack, no duplicate found in preflight",
        "independent_review": "unavailable; deterministic checks and self-review only",
    }
    save(
        output / "sources.json",
        {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                Path(__file__),
                Path(__file__).with_name("laptop_resource_observer.ps1"),
                Path(diagnostic.__file__),
            )
        },
    )
    observer = Observer(output)

    async def trial(client, name, threads, prepared, expected=None):
        if not enough_budget(started, len(report["trials"])):
            raise TimeoutError("Insufficient total budget for another complete trial")
        try:
            return await one_trial(client, output, name, threads, prepared, observer, expected)
        finally:
            trial_result = output / name / "result.json"
            if trial_result.exists():
                report["trials"].append(json.loads(trial_result.read_text()))
            save(output / "result.json", report)

    try:
        async with asyncio.timeout(TOTAL_SECONDS - 15):
            await asyncio.to_thread(observer.start)
            # Preparation/idle observations are outside measured inference.
            async with httpx.AsyncClient(
                base_url=diagnostic.ORIGIN,
                timeout=httpx.Timeout(480, connect=5),
                trust_env=False,
                follow_redirects=False,
                transport=httpx.AsyncHTTPTransport(retries=0),
            ) as client:
                prepared = await prepare(client, output)
                await asyncio.sleep(6)
                observer.check()
                screens = []
                for threads in (2, 3, 4):
                    baseline = await trial(client, f"screen-{threads}-baseline", None, prepared)
                    candidate = await trial(
                        client,
                        f"screen-{threads}-candidate",
                        threads,
                        prepared,
                        baseline["effective"],
                    )
                    screens.append((candidate["wall_seconds"] / baseline["wall_seconds"], threads))
                _, selected = min(screens)
                report["screen_selected_threads"] = selected
                pairs = []
                for index in range(1, 4):
                    baseline = await trial(client, f"pair-{index}-baseline", None, prepared)
                    candidate = await trial(
                        client, f"pair-{index}-candidate", selected, prepared, baseline["effective"]
                    )
                    pairs.append((baseline, candidate))
                report["comparison"] = comparison(pairs)
                report["status"] = "complete"
                observer.phase("cleanup")
                assert_idle()
                await diagnostic.bounded_post(
                    client,
                    "/api/generate",
                    json.dumps({"model": prepared[0].chat_model, "keep_alive": 0}).encode(),
                    20,
                )
                raw, _ = await diagnostic.bounded_request(client, "GET", "/api/ps")
                if json.loads(raw).get("models"):
                    raise ValueError("Final unload failed")
                report["cleanup"] = "diagnostic model unloaded; application configuration unchanged"
    except Exception as exc:
        report["status"] = "failed"
        report["error_type"] = type(exc).__name__
        report["error"] = str(exc)
        report["cleanup"] = (
            "inspect residual runner activity before another request; no automatic retry"
        )
    finally:
        report["observer_cleanup"] = await asyncio.to_thread(observer.stop)
        if report["observer_cleanup"].get("forced_stop") or report["observer_cleanup"].get(
            "returncode", 0
        ):
            report["status"] = "failed"
        report["elapsed_seconds"] = time.monotonic() - started
        report["finished_utc"] = datetime.now(UTC).isoformat()
        samples_path = output / "samples.jsonl"
        if samples_path.exists():
            try:
                samples = [json.loads(line) for line in samples_path.read_text().splitlines()]
                summary = summarize_samples(samples, machine["logical_processors"])
                save(output / "resource-summary.json", summary)
                if len(summary["power_ac_states"]) != 1:
                    report["status"] = "failed"
                    report["power_comparison_error"] = "Power state changed or unavailable"
                    if "comparison" in report:
                        report["comparison"]["retain_candidate"] = False
            except (ValueError, KeyError) as exc:
                report["resource_summary_error"] = type(exc).__name__
                report["status"] = "failed"
        save(output / "result.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-laptop-thread-trials", action="store_true", required=True)
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
                    "status",
                    "elapsed_seconds",
                    "comparison",
                    "error_type",
                    "error",
                    "cleanup",
                )
            },
            indent=2,
        )
    )
    return 0 if report["status"] == "complete" else 1


if __name__ == "__main__":
    sys.exit(main())
