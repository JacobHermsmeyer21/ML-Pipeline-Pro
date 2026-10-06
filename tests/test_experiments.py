import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from kombu.exceptions import OperationalError

from ml_pipeline_pro.execution import execute_experiment


def submit(client, body, key="submission-1"):
    return client.post("/api/v1/experiments", json=body, headers={"Idempotency-Key": key})


def test_experiment_submission_is_idempotent_and_queues_ids(
    tracking_client, experiment_body, publisher, store
):
    first = submit(tracking_client, experiment_body)
    again = submit(tracking_client, experiment_body)
    assert first.status_code == again.status_code == 202
    assert first.json()["id"] == again.json()["id"]
    assert first.json()["status"] == "queued"
    assert "worker_token" not in first.json()
    assert "request_hash" not in first.json()
    assert len(store.experiments.records) == 1
    assert publisher.published[0] == ("demo", first.json()["id"])


def test_idempotency_key_cannot_be_reused_for_changed_configuration(
    tracking_client, experiment_body
):
    assert submit(tracking_client, experiment_body).status_code == 202
    changed = submit(tracking_client, {**experiment_body, "config": {"seed": 43}})
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "idempotency_conflict"


def test_queue_outage_preserves_submission_for_retry(
    tracking_client, experiment_body, publisher, store
):
    publisher.error = OperationalError("redis://user:private-secret@localhost")
    response = submit(tracking_client, experiment_body)
    assert response.status_code == 503
    experiment_id = response.json()["error"]["details"]["experiment_id"]
    assert "private-secret" not in response.text
    assert store.experiments.records[experiment_id].last_dispatch_at is None
    publisher.error = None
    retry = submit(tracking_client, experiment_body)
    assert retry.status_code == 202
    assert retry.json()["id"] == experiment_id
    assert len(store.experiments.records) == 1


@pytest.mark.parametrize("reference", ["dataset_id", "model_id"])
def test_foreign_project_references_cannot_be_submitted(
    tracking_client, experiment_body, store, reference
):
    repository = store.datasets if reference == "dataset_id" else store.models
    repository.records[experiment_body[reference]].project_id = "other"
    assert submit(tracking_client, experiment_body).status_code == 404
    assert store.experiments.records == {}


@pytest.mark.parametrize(
    "config",
    [
        {"epochs": 0},
        {"batch_size": 0},
        {"learning_rate": 0},
        {"max_runtime_seconds": 601},
        {"seed": -1},
        {"hidden_units": 513},
    ],
)
def test_training_budgets_and_parameters_are_validated(tracking_client, experiment_body, config):
    assert submit(tracking_client, {**experiment_body, "config": config}).status_code == 422


def test_submission_requires_an_idempotency_key(tracking_client, experiment_body):
    assert tracking_client.post("/api/v1/experiments", json=experiment_body).status_code == 422


def test_experiment_status_and_lists_are_project_scoped(tracking_client, experiment_body):
    record = submit(tracking_client, experiment_body).json()
    assert tracking_client.get(f"/api/v1/experiments/{record['id']}").status_code == 200
    assert len(tracking_client.get("/api/v1/experiments?status=queued").json()["items"]) == 1
    assert tracking_client.get("/api/v1/experiments?status=succeeded").json()["items"] == []
    assert (
        tracking_client.get(
            f"/api/v1/experiments/{record['id']}", headers={"X-Project-ID": "other"}
        ).status_code
        == 404
    )
    assert (
        tracking_client.get("/api/v1/experiments", headers={"X-Project-ID": "other"}).json()[
            "items"
        ]
        == []
    )


def test_running_or_completed_experiments_are_not_redispatched(
    tracking_client, experiment_body, publisher, store
):
    experiment_id = submit(tracking_client, experiment_body).json()["id"]
    store.experiments.records[experiment_id].status = "running"
    assert submit(tracking_client, experiment_body).status_code == 202
    assert len(publisher.published) == 1


def test_missing_input_at_execution_has_a_terminal_failure(
    tracking_client, experiment_body, store, app
):
    experiment_id = submit(tracking_client, experiment_body).json()["id"]
    store.datasets.records.clear()
    result = asyncio.run(execute_experiment(store, "demo", experiment_id, app.state.settings))
    assert result == "failed"
    record = tracking_client.get(f"/api/v1/experiments/{experiment_id}").json()
    assert record["status"] == "failed"
    assert "missing" in record["error_summary"]


def test_expired_worker_ownership_is_reclaimed_and_old_owner_cannot_finish(
    tracking_client, experiment_body, store
):
    experiment_id = submit(tracking_client, experiment_body).json()["id"]

    async def exercise():
        repository = store.experiments
        assert await repository.claim(
            "demo", experiment_id, "old", lease_seconds=30, max_attempts=3
        )
        assert (
            await repository.claim(
                "demo", experiment_id, "duplicate", lease_seconds=30, max_attempts=3
            )
            is None
        )
        repository.records[experiment_id].lease_expires_at = datetime.now(UTC) - timedelta(
            seconds=1
        )
        assert await repository.claim(
            "demo", experiment_id, "new", lease_seconds=30, max_attempts=3
        )
        assert not await repository.finish(
            "demo", experiment_id, "old", values={"status": "succeeded"}
        )
        assert await repository.finish("demo", experiment_id, "new", values={"status": "succeeded"})

    asyncio.run(exercise())


def test_comparison_uses_validation_metrics_and_rejects_incomplete_runs(
    tracking_client, experiment_body, store
):
    first = submit(tracking_client, experiment_body, "first").json()["id"]
    second = submit(tracking_client, experiment_body, "second").json()["id"]
    url = f"/api/v1/experiments/compare?experiment_id={first}&experiment_id={second}"
    assert tracking_client.get(url).status_code == 409
    for record_id, validation, test in ((first, 0.9, 0.5), (second, 0.8, 1.0)):
        record = store.experiments.records[record_id]
        record.status = "succeeded"
        record.metrics = {"validation_f1": validation, "test_f1": test}
    compared = tracking_client.get(url)
    assert compared.status_code == 200
    assert compared.json()["best_experiment_id"] == first
    assert tracking_client.get(url + "&metric=test_f1").status_code == 422
    assert tracking_client.get(url, headers={"X-Project-ID": "other"}).status_code == 404


def test_version_registration_rejects_incomplete_experiments(tracking_client, experiment_body):
    record = submit(tracking_client, experiment_body).json()
    response = tracking_client.post(
        f"/api/v1/models/{record['model_id']}/versions",
        json={"version": "v1", "experiment_id": record["id"]},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "experiment_incomplete"
