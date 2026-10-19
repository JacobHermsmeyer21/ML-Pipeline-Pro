"""Reproduce descriptive CPU-trial results from retained evidence (standard library only)."""

import argparse
import gzip
import json
import statistics
from collections import defaultdict
from pathlib import Path


def read_json(path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8-sig"))
    with gzip.open(str(path) + ".gz", "rt", encoding="utf-8") as stream:
        return json.load(stream)


def describe(values):
    return {"min": min(values), "median": statistics.median(values), "max": max(values)}


def analyze(root):
    result = read_json(root / "result.json")
    resources = read_json(root / "resource-summary.json")
    samples_path = root / "samples.jsonl"
    if samples_path.exists():
        samples = [json.loads(line) for line in samples_path.read_text().splitlines()]
    else:
        with gzip.open(str(samples_path) + ".gz", "rt", encoding="utf-8") as stream:
            samples = [json.loads(line) for line in stream]
    observer_pids = {s["observer_pid"] for s in samples}
    by_phase = defaultdict(list)
    for interval in resources["same_phase_intervals"]:
        by_phase[interval["phase"]].append(interval)

    cpu = {}
    for phase, intervals in by_phase.items():
        if not phase.endswith(":inference"):
            continue
        seconds = sum(i["gap_seconds"] for i in intervals)
        capacity = seconds * result["machine"]["logical_processors"]
        totals = defaultdict(float)
        observer_cpu = 0.0
        for interval in intervals:
            for process in interval["processes"]:
                totals[process["name"]] += process["cpu_seconds"]
                if process["pid"] in observer_pids:
                    observer_cpu += process["cpu_seconds"]
        system_busy = sum(i["system_busy_fraction"] * i["gap_seconds"] for i in intervals) / seconds
        cpu[phase] = {
            "attribution_status": (
                "Incomplete: non-atomic samples, long query delays and denied process access; "
                "residual is not measured competing CPU"
            ),
            "interval_count": len(intervals),
            "covered_seconds": seconds,
            "system_busy_fraction": system_busy,
            "llama_server_machine_cpu_fraction": totals["llama-server"] / capacity,
            "observer_machine_cpu_fraction": observer_cpu / capacity,
            "all_observed_process_machine_cpu_fraction": sum(totals.values()) / capacity,
            "unattributed_busy_fraction_approximate": system_busy - sum(totals.values()) / capacity,
            "top_processes_by_cpu_seconds": [
                {"name": name, "cpu_seconds": value, "machine_cpu_fraction": value / capacity}
                for name, value in sorted(totals.items(), key=lambda item: -item[1])[:10]
            ],
        }

    measurements = []
    baseline = read_json(root / "baseline-request.json")
    for trial in result["trials"]:
        request = read_json(root / trial["name"] / "request.json")
        if trial["threads_requested"] is not None:
            assert request["options"].pop("num_thread") == trial["threads_requested"]
        assert request == baseline
        response = read_json(root / trial["name"] / "response.json")
        assert response["prompt_eval_cached_count"] == 0
        assert response["prompt_eval_count"] == 1109
        assert json.loads(response["message"]["content"]) == {
            "call": {"name": "get_experiment", "arguments": {"experiment_id": "exp-low"}}
        }
        measurements.append(
            {
                key: trial[key]
                for key in (
                    "name",
                    "threads_requested",
                    "eligible",
                    "wall_seconds",
                    "warmup_seconds",
                    "timings",
                    "effective",
                )
            }
        )
    assert len(measurements) == 12 and all(t["eligible"] for t in measurements)
    inference_samples = [s for s in samples if s["phase"].endswith(":inference")]
    perf = defaultdict(list)
    for sample in inference_samples:
        for name, counter in sample.get("performance", {}).items():
            if isinstance(counter, dict) and counter.get("value") is not None:
                perf[name].append(counter["value"])
    base_pairs = [
        t["wall_seconds"]
        for t in measurements
        if t["name"].startswith("pair-") and t["name"].endswith("baseline")
    ]
    candidate_pairs = [
        t["wall_seconds"]
        for t in measurements
        if t["name"].startswith("pair-") and t["name"].endswith("candidate")
    ]
    assert statistics.median(base_pairs) == result["comparison"]["baseline_median_seconds"]
    assert statistics.median(candidate_pairs) == result["comparison"]["candidate_median_seconds"]
    return {
        "run_status": result["status"],
        "source_revision": result["source_revision"],
        "source_was_dirty": bool(result["working_tree"]),
        "elapsed_seconds": result["elapsed_seconds"],
        "comparison": result["comparison"],
        "measurements": measurements,
        "resource_sample_count": len(samples),
        "overall_max_gap_seconds": resources["max_gap_seconds"],
        "overall_max_sample_seconds": resources["max_sample_duration_seconds"],
        "inference_sample_duration_seconds": describe(
            [s["duration_seconds"] for s in inference_samples]
        ),
        "inference_sample_gap_seconds": describe(
            [
                s["sample_gap_seconds"]
                for s in inference_samples
                if s["sample_gap_seconds"] is not None
            ]
        ),
        "sample_error_count": sum(len(s["errors"]) for s in samples),
        "process_access_error_observations": sum(
            len(p["errors"]) for s in samples for p in s["processes"]
        ),
        "observer_startup_and_all_phases_cpu_seconds": samples[-1]["observer_cpu_seconds"],
        "power_ac_states": resources["power_ac_states"],
        "battery_percent_first_last": [
            samples[0]["power"]["battery_percent"],
            samples[-1]["power"]["battery_percent"],
        ],
        "performance_counters_during_inference": {
            name: describe(values) for name, values in perf.items()
        },
        "phase_cpu_diagnostics_not_complete_attribution": cpu,
        "cleanup": result["cleanup"],
        "observer_cleanup": result["observer_cleanup"],
        "limits": (
            "Descriptive three-pair evidence on battery; long sample/query delays and denied "
            "process access prevent complete CPU attribution or a contention-cause claim; "
            "no significance or full-turn acceptance claim"
        ),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = analyze(args.root)
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: summary[key]
                for key in (
                    "run_status",
                    "elapsed_seconds",
                    "comparison",
                    "resource_sample_count",
                    "overall_max_gap_seconds",
                    "inference_sample_duration_seconds",
                    "battery_percent_first_last",
                )
            },
            indent=2,
        )
    )
