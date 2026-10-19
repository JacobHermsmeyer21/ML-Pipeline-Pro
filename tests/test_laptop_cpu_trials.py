import asyncio
import json
import subprocess

import httpx
import pytest

from evaluations import laptop_cpu_trials as trials


def test_candidate_changes_only_allowlisted_request_local_thread_count():
    body = json.dumps(
        {
            "model": "pinned",
            "options": {"num_ctx": 8192, "num_predict": 1024},
            "messages": [{"role": "user", "content": "original"}],
            "format": {},
        }
    ).encode()
    for threads in (None, 2, 3, 4):
        candidate = json.loads(trials.candidate_payload(body, threads))
        if threads is not None:
            assert candidate["options"].pop("num_thread") == threads
        assert candidate == json.loads(body)
    with pytest.raises(ValueError):
        trials.candidate_payload(body, 8)
    with pytest.raises(ValueError):
        trials.candidate_payload(trials.candidate_payload(body, 2), 3)


def test_effective_threads_are_inference_settings_and_missing_flags_fail():
    log = (
        "using 5 threads for HTTP server\n"
        "system_info: n_threads = 2 (n_threads_batch = 2) / 4\n"
        "llama_context: n_batch = 1024\nllama_context: n_ubatch = 1024\n"
    )
    assert trials.runner_settings(log) == {
        "threads": 2,
        "threads_batch": 2,
        "batch": 1024,
        "micro_batch": 1024,
    }
    with pytest.raises(ValueError):
        trials.runner_settings("using 5 threads for HTTP server")


@pytest.mark.parametrize(
    "cached,log,valid",
    [
        (0, "cached n_tokens = 0, memory_seq_rm\nall slots are idle", True),
        (1, "cached n_tokens = 0, memory_seq_rm\nall slots are idle", False),
        (0, "cached n_tokens = 100, memory_seq_rm\nall slots are idle", False),
        (0, "cached n_tokens = 0, memory_seq_rm", False),
        (None, "cached n_tokens = 0, memory_seq_rm\nall slots are idle", False),
    ],
)
def test_cache_and_runner_completion_are_required(cached, log, valid):
    raw = json.dumps({"prompt_eval_cached_count": cached})
    if valid:
        assert trials.eligible_response(raw, log)
    else:
        with pytest.raises(ValueError):
            trials.eligible_response(raw, log)


def test_reserve_stops_before_inference_or_request_budget_exhaustion():
    assert trials.enough_budget(100, 0, now=100)
    assert trials.enough_budget(100, 15, now=3040)
    assert not trials.enough_budget(100, 0, now=3040.001)
    assert not trials.enough_budget(100, 16, now=100)


def test_retention_uses_three_valid_pairs_medians_and_fixed_twenty_percent_gate():
    def observation(seconds, eligible=True):
        return {"wall_seconds": seconds, "eligible": eligible}

    pairs = [(observation(a), observation(b)) for a, b in [(100, 80), (90, 70), (110, 90)]]
    result = trials.comparison(pairs)
    assert result["baseline_median_seconds"] == 100
    assert result["candidate_median_seconds"] == 80
    # Floating-point subtraction at the exact boundary must not reject 20%.
    assert result["retain_candidate"]
    pairs[0][1]["eligible"] = False
    with pytest.raises(ValueError):
        trials.comparison(pairs)
    with pytest.raises(ValueError):
        trials.comparison(pairs[:1])


def test_resource_deltas_use_actual_late_gaps_and_exclude_pid_reuse_or_denied_access():
    def sample(elapsed, cpu, phase="inference"):
        return {
            "observer_elapsed_seconds": elapsed,
            "phase": phase,
            "processes": [
                {"pid": 7, "name": "runner", "start_utc": "same", "cpu_seconds": cpu},
                {"pid": 8, "name": "denied", "errors": ["cpu_unavailable"]},
            ],
            "system_cpu": {
                "idle_100ns": elapsed * 10,
                "kernel_100ns": elapsed * 80,
                "user_100ns": elapsed * 20,
            },
            "duration_seconds": 0.1,
            "errors": [],
        }

    before, after = sample(0, 0), sample(10, 20)
    result = trials.summarize_samples([before, after], 4)
    interval = result["same_phase_intervals"][0]
    assert interval["gap_seconds"] == 10
    assert interval["processes"][0]["machine_cpu_fraction"] == 0.5
    assert interval["system_busy_fraction"] == 0.9
    after["processes"][0]["start_utc"] = "reused"
    assert (
        trials.summarize_samples([before, after], 4)["same_phase_intervals"][0]["processes"] == []
    )
    after["phase"] = "warmup"
    assert trials.summarize_samples([before, after], 4)["same_phase_intervals"] == []


def test_observer_stops_and_reaps_only_its_owned_process_on_late_exit(tmp_path):
    observer = trials.Observer(tmp_path)
    events = []

    class Process:
        returncode = 0

        def wait(self, timeout):
            events.append(("wait", timeout))
            if len(events) == 1:
                raise subprocess.TimeoutExpired("observer", timeout)

        def terminate(self):
            events.append(("terminate",))

    observer.process = Process()
    observer.stderr = (tmp_path / "stderr").open("wb")
    assert observer.stop()["forced_stop"]
    assert events == [("wait", 5), ("terminate",), ("wait", 5)]
    assert observer.stderr.closed and (tmp_path / "stop.txt").exists()


def test_observer_rejects_power_changes_and_handles_partial_sample_writes(tmp_path):
    class Process:
        def poll(self):
            return None

    observer = trials.Observer(tmp_path)
    observer.process = Process()
    path = tmp_path / "samples.jsonl"
    path.write_bytes(b'{"power":{"ac_line_status":0}}\n{')
    observer.check()
    assert observer.ac_state == 0
    path.write_bytes(b'{"power":{"ac_line_status":0}}\n{"power":{"ac_line_status":1}}\n')
    with pytest.raises(ValueError, match="power state changed"):
        observer.check()


def test_reset_failure_stops_without_warmup_inference_or_retry(tmp_path, monkeypatch):
    from evaluations import laptop_qwen_diagnostic as diagnostic

    monkeypatch.setattr(trials, "assert_idle", lambda: None)
    body = json.dumps({"options": {"num_ctx": 8192, "num_predict": 1024}}).encode()
    prepared = diagnostic.config(), {}, [], body, None

    class Observer:
        def phase(self, name):
            pass

    calls = []

    def handle(request):
        calls.append(request.url.path)
        return httpx.Response(503)

    async def run():
        async with httpx.AsyncClient(
            base_url=diagnostic.ORIGIN, transport=httpx.MockTransport(handle)
        ) as client:
            with pytest.raises(httpx.HTTPStatusError):
                await trials.one_trial(client, tmp_path, "failed", 2, prepared, Observer())

    asyncio.run(run())
    assert calls == ["/api/generate"]
    assert json.loads((tmp_path / "failed/result.json").read_text())["eligible"] is False


@pytest.mark.parametrize("failure", [None, "ignored_threads", "cached", "timeout", "semantic"])
def test_trial_preserves_workload_stops_on_failure_and_never_retries(
    tmp_path, monkeypatch, failure
):
    from evaluations import laptop_qwen_diagnostic as diagnostic

    cfg = diagnostic.config()
    original = json.dumps(
        {
            "model": cfg.chat_model,
            "messages": ["original"],
            "options": {"num_ctx": 8192, "num_predict": 1024},
        }
    ).encode()
    prepared = (
        cfg,
        {"/api/tags": {"models": [{"name": cfg.chat_model, "digest": "a"}]}},
        [],
        original,
        None,
    )
    log = (
        f"system_info: n_threads = {4 if failure == 'ignored_threads' else 2} "
        "(n_threads_batch = 2)\n"
        "llama_context: n_batch = 1024\nllama_context: n_ubatch = 1024\n"
        "cached n_tokens = 0, memory_seq_rm\nall slots are idle\n"
    )
    runner_log = tmp_path / "runner.log"
    runner_log.write_text(log)
    monkeypatch.setattr(trials, "RUNNER_LOG", runner_log)
    monkeypatch.setattr(trials, "read_log", lambda offset=0: log)
    monkeypatch.setattr(diagnostic, "WALL_SECONDS", 0.01)

    async def validate(*args):
        assert args[4] == original
        if failure == "semantic":
            raise ValueError("Wrong tool arguments")
        return {"call": {"name": "get_experiment", "arguments": {"experiment_id": "exp-low"}}}

    monkeypatch.setattr(diagnostic, "validate_response", validate)

    class Observer:
        def phase(self, name):
            pass

        def check(self):
            pass

    calls = []
    ps_count = 0

    async def handle(request):
        nonlocal ps_count
        calls.append(request.url.path)
        if request.url.path == "/api/ps":
            ps_count += 1
            return httpx.Response(
                200,
                json={
                    "models": []
                    if ps_count == 1
                    else [
                        {
                            "name": cfg.chat_model,
                            "context_length": 8192,
                            "digest": "a",
                            "size_vram": 0,
                        }
                    ]
                },
            )
        if request.url.path == "/api/generate":
            if "options" in json.loads(request.content):
                assert json.loads(request.content)["options"] == {"num_ctx": 8192, "num_thread": 2}
            return httpx.Response(200, json={"done": True})
        assert json.loads(request.content) == json.loads(trials.candidate_payload(original, 2))
        if failure == "timeout":
            await asyncio.sleep(1)
        return httpx.Response(
            200,
            json={
                "prompt_eval_cached_count": 1 if failure == "cached" else 0,
                "total_duration": 4,
                "load_duration": 1,
                "prompt_eval_duration": 2,
                "eval_duration": 1,
                "prompt_eval_count": 1109,
                "eval_count": 18,
            },
        )

    async def run():
        async with httpx.AsyncClient(
            base_url=diagnostic.ORIGIN, transport=httpx.MockTransport(handle)
        ) as client:
            result = await trials.one_trial(client, tmp_path, "run", 2, prepared, Observer())
            assert result["eligible"]

    if failure:
        with pytest.raises((ValueError, TimeoutError)):
            asyncio.run(run())
    else:
        asyncio.run(run())
    assert calls.count("/api/chat") == (0 if failure == "ignored_threads" else 1)
    result = json.loads((tmp_path / "run/result.json").read_text())
    assert result["eligible"] == (failure is None)
