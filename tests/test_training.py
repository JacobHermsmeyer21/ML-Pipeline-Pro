import asyncio
import hashlib
import io
from pathlib import Path

import pytest

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.datasets import DatasetValidationError, load_dataset
from ml_pipeline_pro.execution import execute_experiment
from ml_pipeline_pro.schemas import DatasetCreate, DatasetRecord, ExperimentRecord, TrainingConfig
from ml_pipeline_pro.training import TrainingError, train_classifier
from tests.test_experiments import submit

torch = pytest.importorskip("torch", reason="Install the training extra for real PyTorch tests")


@pytest.fixture
def training_input(tmp_path):
    dataset_root = tmp_path / "data"
    dataset_root.mkdir()
    (dataset_root / "classification.csv").write_bytes(
        Path("examples/data/classification.csv").read_bytes()
    )
    settings = Settings(
        _env_file=None, dataset_root=dataset_root, artifact_root=tmp_path / "artifacts"
    )
    definition = DatasetCreate(
        name="classification",
        version="v1",
        uri="classification.csv",
        feature_columns=["feature_1", "feature_2"],
    )
    loaded = load_dataset(definition, settings)
    dataset = DatasetRecord(
        **definition.model_dump(exclude={"expected_sha256"}),
        project_id="demo",
        sha256=loaded.sha256,
        num_classes=loaded.num_classes,
        row_counts=loaded.row_counts,
    )
    experiment = ExperimentRecord(
        project_id="demo",
        model_id="model",
        dataset_id=dataset.id,
        submission_key="test",
        request_hash="0" * 64,
        config=TrainingConfig(epochs=10),
    )
    return settings, dataset, experiment


def test_fixed_seed_reproduces_metrics_and_checkpoint_bytes(training_input):
    settings, dataset, experiment = training_input
    first = train_classifier(experiment, dataset, "first", settings)
    second = train_classifier(experiment, dataset, "second", settings)
    assert first.metrics == second.metrics
    assert first.artifacts[0].sha256 == second.artifacts[0].sha256
    assert first.metrics["validation_f1"] >= 0.9
    assert first.metrics["test_f1"] >= 0.9
    assert first.dependencies["torch"] == str(torch.__version__)
    for artifact in first.artifacts:
        content = (settings.artifact_root / artifact.uri).read_bytes()
        assert artifact.sha256 == hashlib.sha256(content).hexdigest()


def test_test_labels_cannot_change_selected_weights(training_input):
    settings, dataset, experiment = training_input
    first = train_classifier(experiment, dataset, "first", settings)
    path = settings.dataset_root / dataset.uri
    lines = path.read_text().splitlines()
    for index, line in enumerate(lines):
        parts = line.split(",")
        if parts[-1] == "test":
            parts[2] = str(1 - int(parts[2]))
            lines[index] = ",".join(parts)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    changed = dataset.model_copy(update={"sha256": load_dataset(dataset, settings).sha256})
    second = train_classifier(experiment, changed, "second", settings)
    assert first.artifacts[0].sha256 == second.artifacts[0].sha256
    assert first.metrics["validation_f1"] == second.metrics["validation_f1"]
    assert first.metrics["test_f1"] != second.metrics["test_f1"]


def test_preprocessing_uses_only_training_rows(training_input):
    settings, dataset, experiment = training_input
    result = train_classifier(experiment, dataset, "normalization", settings)
    checkpoint = torch.load(
        io.BytesIO((settings.artifact_root / result.artifacts[0].uri).read_bytes()),
        weights_only=True,
    )
    loaded = load_dataset(dataset, settings)
    expected = torch.tensor(loaded.splits["train"].features, dtype=torch.float32)
    assert torch.equal(checkpoint["mean"], expected.mean(dim=0))
    assert torch.equal(checkpoint["std"], expected.std(dim=0, unbiased=False).clamp_min(1e-6))


def test_changed_dataset_is_rejected_before_training(training_input):
    settings, dataset, experiment = training_input
    with (settings.dataset_root / dataset.uri).open("a", encoding="utf-8") as stream:
        stream.write("-1,-1,0,train\n")
    with pytest.raises(DatasetValidationError, match="changed after registration"):
        train_classifier(experiment, dataset, "changed", settings)


def test_runtime_budget_produces_an_actionable_failure(training_input, monkeypatch):
    settings, dataset, experiment = training_input
    ticks = iter([0, 2])
    monkeypatch.setattr("ml_pipeline_pro.training.perf_counter", lambda: next(ticks))
    experiment.config.max_runtime_seconds = 1
    with pytest.raises(TrainingError, match="runtime budget"):
        train_classifier(experiment, dataset, "budget", settings)


def test_api_worker_results_artifacts_and_version_registration(
    tracking_client, experiment_body, store, app, tmp_path
):
    app.state.settings.artifact_root = tmp_path
    record = submit(tracking_client, {**experiment_body, "config": {"epochs": 10}}).json()

    async def execute():
        assert (
            await execute_experiment(store, "demo", record["id"], app.state.settings) == "succeeded"
        )
        assert (
            await execute_experiment(store, "demo", record["id"], app.state.settings)
            == "not_claimed"
        )

    asyncio.run(execute())
    completed = tracking_client.get(f"/api/v1/experiments/{record['id']}").json()
    assert completed["status"] == "succeeded"
    assert completed["attempts"] == 1
    assert completed["metrics"]["validation_f1"] >= 0.9
    assert completed["error_summary"] is None
    artifact = next(item for item in completed["artifacts"] if item["name"] == "model.pt")
    path = f"/api/v1/experiments/{record['id']}/artifacts/model.pt"
    download = tracking_client.get(path)
    assert download.status_code == 200
    assert hashlib.sha256(download.content).hexdigest() == artifact["sha256"]
    assert tracking_client.get(path, headers={"X-Project-ID": "other"}).status_code == 404
    version_url = f"/api/v1/models/{record['model_id']}/versions"
    version_body = {"version": "v1", "experiment_id": record["id"]}
    created = tracking_client.post(version_url, json=version_body)
    assert created.status_code == 201, created.text
    assert created.json()["artifact"]["sha256"] == artifact["sha256"]
    assert tracking_client.get(version_url).json()["items"][0]["id"] == created.json()["id"]
    assert tracking_client.get(f"{version_url}/{created.json()['id']}").status_code == 200
    assert (
        tracking_client.get(
            f"{version_url}/{created.json()['id']}", headers={"X-Project-ID": "other"}
        ).status_code
        == 404
    )
    assert tracking_client.post(version_url, json=version_body).status_code == 409
    (tmp_path / artifact["uri"]).write_bytes(b"tampered")
    assert tracking_client.get(path).status_code == 409
    assert (
        tracking_client.post(version_url, json={**version_body, "version": "v2"}).status_code == 409
    )


def test_worker_records_changed_dataset_failure(
    tracking_client, experiment_body, store, app, tmp_path
):
    app.state.settings.dataset_root = tmp_path
    data = Path("examples/data/classification.csv").read_bytes()
    (tmp_path / "classification.csv").write_bytes(data + b"-1,-1,0,train\n")
    record = submit(tracking_client, experiment_body).json()
    assert (
        asyncio.run(execute_experiment(store, "demo", record["id"], app.state.settings)) == "failed"
    )
    response = tracking_client.get(f"/api/v1/experiments/{record['id']}").json()
    assert response["status"] == "failed"
    assert "changed after registration" in response["error_summary"]
    assert response["artifacts"] == []
