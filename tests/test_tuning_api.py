import asyncio

import pytest
from kombu.exceptions import OperationalError

from ml_pipeline_pro.schemas import TrainingConfig
from ml_pipeline_pro.tuning_schemas import TrialRecord


def submit_tuning(client, body, key="tuning-1"):
    return client.post("/api/v1/tuning-jobs", json=body, headers={"Idempotency-Key": key})


def test_tuning_submission_is_idempotent_and_project_scoped(
    tracking_client, experiment_body, tuning_store, publisher
):
    first = submit_tuning(tracking_client, experiment_body)
    again = submit_tuning(tracking_client, experiment_body)
    assert first.status_code == again.status_code == 202
    assert first.json()["id"] == again.json()["id"]
    assert first.json()["limits"] == {"max_trials": 5, "max_runtime_seconds": 300, "concurrency": 1}
    assert first.json()["objective_metric"] == "validation_f1"
    assert "worker_token" not in first.json()
    assert "reservation" not in first.json()
    assert len(tuning_store.jobs.records) == 1
    assert publisher.published_tuning[0] == ("demo", first.json()["id"])
    assert tracking_client.get(f"/api/v1/tuning-jobs/{first.json()['id']}").status_code == 200
    assert (
        tracking_client.get(
            f"/api/v1/tuning-jobs/{first.json()['id']}", headers={"X-Project-ID": "other"}
        ).status_code
        == 404
    )
    assert (
        tracking_client.get("/api/v1/tuning-jobs", headers={"X-Project-ID": "other"}).json()[
            "items"
        ]
        == []
    )


def test_tuning_key_cannot_be_reused_with_changed_limits(
    tracking_client, experiment_body, tuning_store
):
    assert submit_tuning(tracking_client, experiment_body).status_code == 202
    changed = submit_tuning(tracking_client, {**experiment_body, "limits": {"max_trials": 4}})
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "idempotency_conflict"


def test_queue_failure_preserves_tuning_job_for_retry(
    tracking_client, experiment_body, tuning_store, publisher
):
    publisher.error = OperationalError("redis://user:private-password@host")
    response = submit_tuning(tracking_client, experiment_body)
    assert response.status_code == 503
    assert "private-password" not in response.text
    job_id = response.json()["error"]["details"]["tuning_job_id"]
    publisher.error = None
    assert submit_tuning(tracking_client, experiment_body).json()["id"] == job_id
    assert len(tuning_store.jobs.records) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"limits": {"max_trials": 0}},
        {"limits": {"max_trials": 51}},
        {"limits": {"max_runtime_seconds": 1}},
        {"limits": {"max_runtime_seconds": 601}},
        {"limits": {"concurrency": 2}},
        {"limits": {"max_trials": True}},
        {"objective_metric": "test_f1"},
        {"direction": "minimize"},
        {"search_space": {"learning_rate": {"low": 0}}},
        {"search_space": {"learning_rate": {"low": 0.5, "high": 0.1}}},
        {"search_space": {"batch_size": {"choices": [16, 16]}}},
        {"search_space": {"batch_size": {"choices": [0, 16]}}},
        {"search_space": {"hidden_units": {"low": 8, "high": 15, "step": 8}}},
        {"search_space": {"unknown_parameter": {"low": 1, "high": 2}}},
    ],
)
def test_tuning_budgets_search_spaces_and_objectives_are_validated(
    tracking_client, experiment_body, tuning_store, changes
):
    response = submit_tuning(tracking_client, {**experiment_body, **changes})
    assert response.status_code == 422
    assert tuning_store.jobs.records == {}


@pytest.mark.parametrize("reference", ["dataset_id", "model_id"])
def test_tuning_rejects_foreign_project_references(
    tracking_client, experiment_body, tuning_store, store, reference
):
    repository = store.datasets if reference == "dataset_id" else store.models
    repository.records[experiment_body[reference]].project_id = "other"
    assert submit_tuning(tracking_client, experiment_body).status_code == 404
    assert tuning_store.jobs.records == {}


def test_queued_cancellation_is_terminal_and_not_redispatched(
    tracking_client, experiment_body, tuning_store, publisher
):
    job_id = submit_tuning(tracking_client, experiment_body).json()["id"]
    response = tracking_client.post(f"/api/v1/tuning-jobs/{job_id}/cancel")
    assert response.status_code == 202
    assert response.json()["status"] == "cancelled"
    assert response.json()["completed_at"]
    assert tracking_client.post(f"/api/v1/tuning-jobs/{job_id}/cancel").status_code == 202
    assert submit_tuning(tracking_client, experiment_body).json()["status"] == "cancelled"
    assert len(publisher.published_tuning) == 1


def test_running_cancellation_is_requested_and_completed_jobs_cannot_be_cancelled(
    tracking_client, experiment_body, tuning_store
):
    job_id = submit_tuning(tracking_client, experiment_body).json()["id"]
    record = tuning_store.jobs.records[job_id]
    record.status = "running"
    assert (
        tracking_client.post(f"/api/v1/tuning-jobs/{job_id}/cancel").json()["status"]
        == "cancel_requested"
    )
    record.status = "succeeded"
    assert tracking_client.post(f"/api/v1/tuning-jobs/{job_id}/cancel").status_code == 409
    assert (
        tracking_client.post(
            f"/api/v1/tuning-jobs/{job_id}/cancel", headers={"X-Project-ID": "other"}
        ).status_code
        == 404
    )


def test_trial_listing_is_scoped_ordered_and_paginated(
    tracking_client, experiment_body, tuning_store
):
    job_id = submit_tuning(tracking_client, experiment_body).json()["id"]

    async def insert():
        await tuning_store.jobs.claim("demo", job_id, "worker", lease_seconds=30, max_attempts=3)
        for number in (2, 0, 1):
            await tuning_store.trials.insert(
                TrialRecord(
                    project_id="demo",
                    tuning_job_id=job_id,
                    number=number,
                    experiment_id=f"trial-{number}",
                    parameters={"learning_rate": 0.01},
                    config=TrainingConfig(),
                    worker_token="worker",
                )
            )

    asyncio.run(insert())
    response = tracking_client.get(f"/api/v1/tuning-jobs/{job_id}/trials?limit=1&offset=1")
    assert response.status_code == 200
    assert response.json()["items"][0]["number"] == 1
    assert "worker_token" not in response.json()["items"][0]
    assert (
        tracking_client.get(
            f"/api/v1/tuning-jobs/{job_id}/trials", headers={"X-Project-ID": "other"}
        ).status_code
        == 404
    )
