"""Test-only worker entrypoint; production images never import these pause points."""

import asyncio
import json
import sys
import time
from pathlib import Path
from uuid import uuid4

from pymongo.errors import PyMongoError

from ml_pipeline_pro import execution, tuning_execution, worker
from ml_pipeline_pro.jobs import ExperimentRepository
from ml_pipeline_pro.training_control import TrainingControl
from ml_pipeline_pro.tuning_store import TuningJobRepository

CONTROL_ROOT = Path("/recovery-control")


def marker(project_id, suffix, values):
    path = CONTROL_ROOT / f"{project_id}.{suffix}"
    temporary = path.with_suffix(f".{uuid4().hex}.tmp")
    temporary.write_text(json.dumps(values), encoding="utf-8")
    temporary.replace(path)


def held(project_id, boundary):
    path = CONTROL_ROOT / f"{project_id}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))["boundary"] == boundary
    except FileNotFoundError:
        return False


def enter(project_id, boundary, token):
    if not held(project_id, boundary):
        return False
    marker(project_id, "ready", {"boundary": boundary, "token": token})
    return True


def wait_release(project_id, boundary):
    deadline = time.monotonic() + 180
    while held(project_id, boundary):
        if time.monotonic() >= deadline:
            raise TimeoutError("Recovery test did not release the pause")
        time.sleep(0.05)


class PausedControl:
    def __init__(self, control, experiment, token, boundary, checks):
        self.control = control or TrainingControl()
        self.experiment = experiment
        self.token = token
        self.boundary = boundary
        self.checks = checks

    def check(self):
        self.control.check()
        self.checks -= 1
        if self.checks == 0 and enter(self.experiment.project_id, self.boundary, self.token):
            wait_release(self.experiment.project_id, self.boundary)
            self.control.check()


train = execution.train_classifier
evaluate = tuning_execution.evaluate_checkpoint
finish_test = ExperimentRepository.finish_tuning_test
get_job = TuningJobRepository.get


def paused_training(experiment, dataset, token, settings, *, control=None, **kwargs):
    # The fourth check is inside the second batch, after one optimizer step.
    control = PausedControl(control, experiment, token, "training", 4)
    return train(experiment, dataset, token, settings, control=control, **kwargs)


def paused_evaluation(experiment, dataset, token, settings, control):
    # Checkpoint/model loading has finished at the second evaluation check.
    control = PausedControl(control, experiment, token, "final_evaluation", 2)
    return evaluate(experiment, dataset, token, settings, control)


async def paused_final_commit(self, project_id, experiment_id, job_id, token, **kwargs):
    if enter(project_id, "final_commit", token):
        await asyncio.to_thread(wait_release, project_id, "final_commit")
    try:
        accepted = await finish_test(self, project_id, experiment_id, job_id, token, **kwargs)
        marker(project_id, f"commit-{token}", {"accepted": accepted, "token": token})
        return accepted
    except PyMongoError:
        marker(project_id, "outage-final_commit", {"boundary": "final_commit"})
        marker(project_id, f"commit-{token}", {"accepted": False, "token": token})
        raise


async def observed_job_read(self, project_id, job_id):
    try:
        return await get_job(self, project_id, job_id)
    except PyMongoError:
        marker(project_id, "outage-ownership_watch", {"boundary": "ownership_watch"})
        raise


if __name__ == "__main__":
    execution.train_classifier = paused_training
    tuning_execution.evaluate_checkpoint = paused_evaluation
    ExperimentRepository.finish_tuning_test = paused_final_commit
    TuningJobRepository.get = observed_job_read
    worker.app.worker_main(sys.argv[1:])
