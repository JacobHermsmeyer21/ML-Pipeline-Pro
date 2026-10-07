"""Physical worker/dependency loss in a disposable, independently named Compose stack."""

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from bson.json_util import dumps
from pymongo import MongoClient

pytestmark = [
    pytest.mark.integration,
    pytest.mark.recovery,
    pytest.mark.skipif(
        os.getenv("MLPP_RUN_RECOVERY_INTEGRATION") != "1",
        reason="Set MLPP_RUN_RECOVERY_INTEGRATION=1 to run the isolated failure stack",
    ),
]
ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "artifacts/recovery-validation"
CONTROL = EVIDENCE / "control"


def wait_for(read, predicate=bool, *, timeout=90):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = read()
        if predicate(last):
            return last
        time.sleep(0.1)
    raise AssertionError(f"Recovery polling timed out; last observation: {last!r}")


class RecoveryStack:
    def __init__(self):
        self.project = f"mlpp-recovery-{uuid4().hex[:12]}"
        self.evidence = EVIDENCE / self.project
        self.evidence.mkdir(parents=True)
        self.command = [
            "docker",
            "compose",
            "--project-name",
            self.project,
            "--file",
            "compose.yaml",
            "--file",
            "tests/integration/compose.recovery.yaml",
        ]

    def compose(self, *args, timeout=90):
        result = subprocess.run(
            [*self.command, *args], cwd=ROOT, capture_output=True, text=True, timeout=timeout
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout

    def start(self, *, build=False):
        if build:
            self.compose("build", "api", timeout=600)
        self.compose("up", "--wait", "--wait-timeout", "180", "--no-build", timeout=210)

    def kill_worker(self):
        self.compose("kill", "--signal", "SIGKILL", "worker")

    def restart_worker(self):
        self.compose("start", "worker")


@pytest.fixture(scope="module")
def recovery_stack():
    CONTROL.mkdir(parents=True, exist_ok=True)
    # The container runs as uid 10001, including on Linux CI hosts.
    CONTROL.chmod(0o777)
    stack = RecoveryStack()
    try:
        stack.start(build=True)
        yield stack
    finally:
        try:
            (stack.evidence / "compose.log").write_text(
                stack.compose("logs", "--no-color"), encoding="utf-8"
            )
        finally:
            stack.compose("down", "--volumes", "--remove-orphans", timeout=120)


class RecoveryCase:
    def __init__(self, stack, client, database):
        self.stack, self.client, self.database = stack, client, database
        self.project = client.headers["X-Project-ID"]
        self.gate = CONTROL / f"{self.project}.json"

    def pause(self, boundary):
        self.gate.write_text(json.dumps({"boundary": boundary}), encoding="utf-8")

    def release(self):
        self.gate.unlink(missing_ok=True)

    def marker(self, suffix):
        path = CONTROL / f"{self.project}.{suffix}"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def at_boundary(self):
        return wait_for(lambda: self.marker("ready"), timeout=45)

    def get(self, path):
        response = self.client.get(path)
        assert response.status_code == 200, response.text
        return response.json()

    def terminal(self, path):
        return wait_for(
            lambda: self.get(path), lambda record: record["status"] in {"succeeded", "failed"}
        )

    def submit(self, kind):
        body = {**self.inputs, "config": {"epochs": 5, "max_runtime_seconds": 60}}
        if kind == "tuning-jobs":
            body.update(
                limits={"max_trials": 2, "max_runtime_seconds": 300},
                search_space={"learning_rate": {"low": 0.01, "high": 0.05}},
            )
        return self.client.post(f"/{kind}", json=body, headers={"Idempotency-Key": "recovery"})

    def snapshot(self, name):
        records = {
            collection: list(self.database[collection].find({"project_id": self.project}))
            for collection in ("experiments", "trials", "tuning_jobs")
        }
        (self.stack.evidence / f"{self.project}-{name}.json").write_text(
            dumps(records, indent=2), encoding="utf-8"
        )
        return records

    def artifacts(self, experiment):
        for reference in experiment["artifacts"]:
            response = self.client.get(
                f"/experiments/{experiment['id']}/artifacts/{reference['name']}"
            )
            assert response.status_code == 200, response.text
            assert hashlib.sha256(response.content).hexdigest() == reference["sha256"]


@pytest.fixture
def recovery_case(recovery_stack):
    project = f"test_{uuid4().hex}"
    with (
        httpx.Client(
            base_url="http://127.0.0.1:28000/api/v1",
            headers={"X-Project-ID": project},
            timeout=10,
        ) as client,
        MongoClient(
            "mongodb://127.0.0.1:47017/?directConnection=true", timeoutMS=3000, tz_aware=True
        ) as mongo,
    ):
        case = RecoveryCase(recovery_stack, client, mongo.mlpp_recovery)
        dataset = client.post(
            "/datasets",
            json={
                "name": "classification",
                "version": "v1",
                "uri": "classification.csv",
                "feature_columns": ["feature_1", "feature_2"],
            },
        )
        model = client.post("/models", json={"name": "classifier"})
        assert dataset.status_code == model.status_code == 201
        case.inputs = {"dataset_id": dataset.json()["id"], "model_id": model.json()["id"]}
        try:
            yield case
        finally:
            case.release()
            # Restore stopped services even when an assertion fails.
            recovery_stack.start()
            case.snapshot("final-state")
            for name in ("experiments", "trials", "tuning_jobs", "datasets", "models"):
                mongo.mlpp_recovery[name].delete_many({"project_id": project})


def test_killed_training_worker_is_recovered_by_beat(recovery_case):
    case = recovery_case
    case.pause("training")
    response = case.submit("experiments")
    assert response.status_code == 202, response.text
    path = f"/experiments/{response.json()['id']}"
    case.at_boundary()
    before = case.snapshot("interrupted")["experiments"][0]
    assert before["status"] == "running" and before["attempts"] == 1
    case.stack.kill_worker()
    case.release()
    case.stack.restart_worker()
    after = case.terminal(path)
    assert after["status"] == "succeeded" and after["attempts"] == 2, after
    case.artifacts(after)
    records = case.snapshot("recovered")
    assert len(records["experiments"]) == 1


@pytest.mark.parametrize("boundary", ["training", "final_evaluation", "final_commit"])
def test_killed_tuning_worker_preserves_reservations_results_and_deadlines(recovery_case, boundary):
    case = recovery_case
    case.pause(boundary)
    response = case.submit("tuning-jobs")
    assert response.status_code == 202, response.text
    job_id = response.json()["id"]
    case.at_boundary()
    before = case.snapshot("interrupted")
    job = before["tuning_jobs"][0]
    if boundary != "training":
        assert job["phase"] == "evaluating"
        assert all(record["status"] == "succeeded" for record in before["experiments"])
        assert not any(record["test_evaluated"] for record in before["experiments"])
        for experiment in before["experiments"]:
            case.artifacts({**experiment, "id": experiment["_id"]})
    case.stack.kill_worker()
    case.release()
    case.stack.restart_worker()
    after = case.terminal(f"/tuning-jobs/{job_id}")
    assert after["status"] == "succeeded" and after["attempts"] == 2, after
    assert after["final_evaluation"] == "succeeded"
    recovered = case.snapshot("recovered")
    final = recovered["tuning_jobs"][0]
    assert final["deadline_at"] == job["deadline_at"]
    assert final["search_deadline_at"] == job["search_deadline_at"]
    assert final["completed_trials"] == final["scheduled_trials"] == 2
    assert len(recovered["trials"]) == len(recovered["experiments"]) == 2
    assert sorted(trial["number"] for trial in recovered["trials"]) == [0, 1]
    assert all("test_f1" not in trial["metrics"] for trial in recovered["trials"])
    assert sum(record["test_evaluated"] for record in recovered["experiments"]) == 1
    for original in before["experiments"]:
        current = next(item for item in recovered["experiments"] if item["_id"] == original["_id"])
        assert current["config"] == original["config"]
        assert current["attempts"] == (2 if boundary == "training" else 1)
        if original["status"] == "succeeded":
            assert current["artifacts"][0] == original["artifacts"][0]
    case.artifacts(case.get(f"/experiments/{after['best_experiment_id']}"))


@pytest.mark.parametrize("kind", ["experiments", "tuning-jobs"])
def test_repeated_worker_loss_exhausts_attempts_and_closes_children(recovery_case, kind):
    case = recovery_case
    case.pause("training")
    response = case.submit(kind)
    assert response.status_code == 202, response.text
    path = f"/{kind}/{response.json()['id']}"
    for attempt in (1, 2):
        case.at_boundary()
        assert case.get(path)["attempts"] == attempt
        case.stack.kill_worker()
        (CONTROL / f"{case.project}.ready").unlink()
        case.stack.restart_worker()
    failed = case.terminal(path)
    assert failed["status"] == "failed" and failed["attempts"] == 2
    assert "attempt limit" in failed["error_summary"]
    records = case.snapshot("exhausted")
    # Tuning parent failure precedes transactional child cleanup; wait for both.
    if kind == "tuning-jobs":
        wait_for(
            lambda: case.database.tuning_jobs.find_one({"project_id": case.project}),
            lambda job: job["failed_trials"] == 1 and job["reservation"] is None,
        )
        records = case.snapshot("children-closed")
        assert records["tuning_jobs"][0]["reservation"] is None
        assert records["tuning_jobs"][0]["failed_trials"] == 1
        assert len(records["trials"]) == 1
    assert len(records["experiments"]) == 1
    assert records["experiments"][0]["status"] == "failed"


@pytest.mark.parametrize("boundary", ["training", "final_commit"])
def test_mongodb_outage_during_ownership_watch_or_final_commit_is_recovered(
    recovery_case, boundary
):
    case = recovery_case
    case.pause(boundary)
    response = case.submit("tuning-jobs")
    assert response.status_code == 202, response.text
    case.at_boundary()
    before = case.snapshot("before-outage")
    case.stack.compose("stop", "--timeout", "1", "mongo")
    if boundary == "final_commit":
        case.release()
    # The ownership watch observes a real driver error. The final transaction
    # may retry internally rather than surfacing the first connection failure.
    wait_for(lambda: case.marker("outage-ownership_watch"), timeout=20)
    # Keep MongoDB offline until the active owner can no longer renew its lease.
    remaining = before["tuning_jobs"][0]["lease_expires_at"].timestamp() - time.time()
    if remaining > 0:
        time.sleep(remaining + 1)
    case.release()
    case.stack.compose("up", "--wait", "--wait-timeout", "60", "--no-deps", "mongo")
    if boundary == "final_commit":
        token = before["tuning_jobs"][0]["worker_token"]
        attempted = wait_for(lambda: case.marker(f"commit-{token}"), timeout=30)
        assert attempted["accepted"] is False
    after = case.terminal(f"/tuning-jobs/{response.json()['id']}")
    assert after["status"] == "succeeded" and after["attempts"] == 2, after
    records = case.snapshot("recovered")
    assert records["tuning_jobs"][0]["deadline_at"] == before["tuning_jobs"][0]["deadline_at"]
    assert len(records["trials"]) == len(records["experiments"]) == 2
    assert after["completed_trials"] == after["scheduled_trials"] == 2
    assert after["final_evaluation"] == "succeeded"
    if boundary == "final_commit":
        assert all(record["attempts"] == 1 for record in records["experiments"])
    case.artifacts(case.get(f"/experiments/{after['best_experiment_id']}"))


@pytest.mark.parametrize("kind", ["experiments", "tuning-jobs"])
def test_redis_outage_preserves_submission_and_beat_dispatches_after_restart(recovery_case, kind):
    case = recovery_case
    case.stack.compose("stop", "--timeout", "1", "redis")
    response = case.submit(kind)
    assert response.status_code == 503, response.text
    assert response.json()["error"]["code"] == "queue_unavailable"
    collection = "experiments" if kind == "experiments" else "tuning_jobs"
    records = case.snapshot("undispatched")[collection]
    assert len(records) == 1 and records[0]["status"] == "queued"
    record_id = records[0]["_id"]
    assert records[0]["attempts"] == 0 and records[0]["last_dispatch_at"] is None
    case.stack.compose("up", "--wait", "--wait-timeout", "60", "--no-deps", "redis")
    after = case.terminal(f"/{kind}/{record_id}")
    assert after["status"] == "succeeded" and after["attempts"] == 1, after
    repeated = case.submit(kind)
    assert repeated.status_code == 202 and repeated.json()["id"] == record_id
    assert len(case.snapshot("recovered")[collection]) == 1
