"""Offline analysis of the retained laptop request; never sends inference."""

import argparse
import copy
import hashlib
import json
import platform
import subprocess
import time
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from ml_pipeline_pro.conversation_guidance import guided_instructions
from ml_pipeline_pro.conversation_qwen_counter import (
    TOKENIZER_SHA256,
    QwenInputCounter,
    render_qwen_request,
)
from ml_pipeline_pro.conversation_service import HOST_INSTRUCTIONS

CATALOG_MARKER = "Supported tools (exact argument shapes are enforced by the response schema): "


def main():
    started_utc = datetime.now(UTC).isoformat()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    baseline = root / "docs/evidence/2026-10-18-laptop-qwen-diagnostic"
    tokenizer = root / ".tools/local-model-setup/tokenizer.json"
    manifest = json.loads((baseline / "manifest.json").read_bytes())
    inputs = {}
    for name in ("request.json", "result.json", "response.json"):
        data = (baseline / name).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != manifest[name]["sha256"]:
            raise ValueError(f"Baseline hash differs: {name}")
        inputs[name] = digest
    payload = json.loads((baseline / "request.json").read_bytes())
    run = json.loads((baseline / "result.json").read_bytes())
    response = json.loads((baseline / "response.json").read_bytes())
    if payload["messages"][0]["content"] != guided_instructions():
        raise ValueError("Current guided instructions differ from retained request")
    if payload["messages"][1]["content"] != HOST_INSTRUCTIONS:
        raise ValueError("Current host instructions differ from retained request")

    preparation = []
    for _ in range(3):
        started, cpu_started = time.perf_counter(), time.process_time()
        counter = QwenInputCounter(run["provenance"], tokenizer)
        preparation.append(
            {
                "wall_seconds": time.perf_counter() - started,
                "process_cpu_seconds": time.process_time() - cpu_started,
            }
        )
    for _ in range(3):
        counter(payload)
    observations = []
    for _ in range(30):
        started, cpu_started = time.perf_counter(), time.process_time()
        tokens = counter(payload)
        observations.append(
            {
                "wall_seconds": time.perf_counter() - started,
                "process_cpu_seconds": time.process_time() - cpu_started,
                "tokens": tokens,
            }
        )
    if any(item["tokens"] != 1109 for item in observations):
        raise ValueError("Token count does not match retained runtime's 1,109")
    policy, catalog = payload["messages"][0]["content"].split(CATALOG_MARKER)
    segments = [
        ("guided_policy_including_catalog_label", policy + CATALOG_MARKER),
        ("tool_catalog", catalog),
        ("host_policy", payload["messages"][1]["content"]),
        ("history_marker", payload["messages"][2]["content"]),
        ("user_request", payload["messages"][3]["content"]),
    ]
    segment_counts = [
        {
            "segment": name,
            "utf8_bytes": len(content.encode()),
            "standalone_tokens": len(
                counter.tokenizer.encode(content, add_special_tokens=False).ids
            ),
        }
        for name, content in segments
    ]
    ablations = []
    for label, drop_catalog, drop_host in (
        ("original", False, False),
        ("catalog_removed", True, False),
        ("host_policy_removed", False, True),
        ("catalog_and_host_policy_removed", True, True),
    ):
        candidate = copy.deepcopy(payload)
        if drop_catalog:
            candidate["messages"][0]["content"] = policy
        if drop_host:
            del candidate["messages"][1]
        ablations.append({"case": label, "rendered_tokens": counter(candidate)})

    prompt_seconds = response["prompt_eval_duration"] / 1e9
    generation_seconds = response["eval_duration"] / 1e9
    runtime_seconds = response["total_duration"] / 1e9
    other_seconds = runtime_seconds - prompt_seconds - generation_seconds
    tokens_per_second = response["prompt_eval_count"] / prompt_seconds
    projections = [
        {
            **case,
            "estimated_runtime_seconds": (
                other_seconds + generation_seconds + case["rendered_tokens"] / tokens_per_second
            ),
        }
        for case in ablations
    ]
    result = {
        "started_utc": started_utc,
        "finished_utc": datetime.now(UTC).isoformat(),
        "source_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "working_tree": subprocess.check_output(
            ["git", "status", "--short"], cwd=root, text=True
        ).strip(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": {name: version(name) for name in ("tokenizers", "langchain-ollama", "ollama")},
        "baseline_inputs_sha256": inputs,
        "tokenizer_sha256": TOKENIZER_SHA256,
        "counter_identity": counter.identity,
        "live_inference_requests": 0,
        "measurement_machine": "Workstation; see current-machine.json, not the laptop",
        "method": {
            "workload": "Unchanged retained read_guidance SDK request",
            "preparation_repetitions": 3,
            "unreported_count_warmups": 3,
            "count_repetitions": 30,
            "standalone_segment_counts_are_additive": False,
            "ablations": "Token counts only; incomplete policies, never sent or supported",
            "projection": "Constant laptop prompt throughput, unchanged generation and other time",
            "projection_is_measured_inference": False,
        },
        "preparation_observations": preparation,
        "count_observations": observations,
        "segments": segment_counts,
        "full_rendered_tokens": counter(payload),
        "rendered_utf8_bytes": len(render_qwen_request(payload).encode()),
        "ablations": ablations,
        "retained_laptop_baseline": {
            "runtime_seconds": runtime_seconds,
            "http_wall_seconds": run["inference_wall_seconds"],
            "prompt_seconds": prompt_seconds,
            "generation_seconds": generation_seconds,
            "load_seconds": response["load_duration"] / 1e9,
            "other_seconds_including_load": other_seconds,
            "prompt_fraction_of_runtime": prompt_seconds / runtime_seconds,
            "prompt_tokens_per_second": tokens_per_second,
            "maximum_input_tokens_for_20s_at_same_rates": (
                (20 - generation_seconds - other_seconds) * tokens_per_second
            ),
            "runtime_if_prompt_tokens_halved_estimate_seconds": (
                other_seconds + generation_seconds + prompt_seconds / 2
            ),
            "overall_speedup_if_all_prompt_cost_vanished_upper_bound": (
                runtime_seconds / (generation_seconds + other_seconds)
            ),
        },
        "constant_throughput_projections": projections,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "tokens": result["full_rendered_tokens"],
                "segments": segment_counts,
                "estimates_only": projections,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
