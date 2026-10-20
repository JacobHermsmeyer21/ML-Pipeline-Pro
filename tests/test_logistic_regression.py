"""Algorithm admission, legacy serialization and real linear classifier boundaries."""

import asyncio
import hashlib
import io
import json

import pytest
from pydantic import ValidationError

from ml_pipeline_pro.datasets import load_dataset
from ml_pipeline_pro.execution import execute_experiment
from ml_pipeline_pro.schemas import ExperimentCreate, LogisticRegressionConfig, TrainingConfig
from ml_pipeline_pro.training import TrainingError, load_checkpoint, train_classifier
from ml_pipeline_pro.training_control import TrainingControl
from tests.test_experiments import submit
from tests.test_tools import call, context, run_call, training_arguments, tuning_arguments

pytest_plugins = ["tests.test_training"]


@pytest.mark.parametrize("tool", ["create_experiment", "create_tuning_job"])
def test_host_rejects_logistic_proposal_before_saving(training_input, tool):
    from tests.test_conversation_service import RecordsTransport, ScriptedModel, model_record, run
    from tests.test_conversation_service import call as model_call

    _, dataset, _ = training_input
    inputs = {"dataset_id": dataset.id, "model_id": "model"}
    arguments = (
        training_arguments(inputs) if tool == "create_experiment" else tuning_arguments(inputs)
    )
    transport = RecordsTransport(
        {
            f"/api/v1/datasets/{dataset.id}": dataset.model_dump(mode="json"),
            "/api/v1/models/model": model_record(architecture="logistic_regression"),
        }
    )
    result, memory, _ = run(ScriptedModel(model_call(tool, **arguments)), transport)
    assert result.status == "failed"
    assert result.error["code"] == "unsupported_model_algorithm"
    assert result.pending_action is None
    assert all(request[0] == "GET" for request in transport.calls)


def test_legacy_config_serialization_and_hash_are_unchanged():
    body = ExperimentCreate(dataset_id="dataset", model_id="model")
    expected = {
        "dataset_id": "dataset",
        "model_id": "model",
        "config": {
            "seed": 42,
            "epochs": 30,
            "batch_size": 16,
            "learning_rate": 0.01,
            "hidden_units": 16,
            "max_runtime_seconds": 60,
        },
    }
    assert body.model_dump() == expected
    assert hashlib.sha256(json.dumps(body.model_dump(), sort_keys=True).encode()).digest() == (
        hashlib.sha256(json.dumps(expected, sort_keys=True).encode()).digest()
    )
    assert isinstance(ExperimentCreate.model_validate(expected).config, TrainingConfig)


def test_logistic_defaults_have_the_same_fingerprint_when_explicit():
    minimal = ExperimentCreate(
        dataset_id="dataset", model_id="model", config={"algorithm": "logistic_regression"}
    )
    explicit = ExperimentCreate.model_validate(minimal.model_dump())
    assert json.dumps(minimal.model_dump(), sort_keys=True) == json.dumps(
        explicit.model_dump(), sort_keys=True
    )


@pytest.mark.parametrize(
    "extra",
    [
        {"hidden_units": 16},
        {"l2_strength": -1},
        {"l2_strength": 1.1},
        {"l2_strength": float("inf")},
    ],
)
def test_logistic_config_rejects_hidden_units_and_invalid_l2(extra):
    with pytest.raises(ValidationError):
        LogisticRegressionConfig(algorithm="logistic_regression", **extra)


def logistic_model(client):
    response = client.post(
        "/api/v1/models", json={"name": "linear", "architecture": "logistic_regression"}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_admission_rejects_mismatch_without_queueing_and_preserves_replay(
    tracking_client, experiment_body, publisher, store
):
    original = submit(tracking_client, experiment_body).json()
    linear = logistic_model(tracking_client)
    for body in [
        {**experiment_body, "model_id": linear},
        {**experiment_body, "config": {"algorithm": "logistic_regression"}},
    ]:
        response = submit(tracking_client, body, "mismatch")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "model_config_mismatch"
    assert len(store.experiments.records) == 1
    assert len(publisher.published) == 1
    # Replays resolve the original admission before rechecking referenced models.
    store.models.records.pop(experiment_body["model_id"])
    assert submit(tracking_client, experiment_body).json()["id"] == original["id"]


def test_logistic_api_worker_download_register_and_unsupported_tools(
    tracking_client, experiment_body, app, store, tmp_path, tuning_store
):
    linear = logistic_model(tracking_client)
    inputs = {**experiment_body, "model_id": linear}
    for name, arguments in [
        ("create_experiment", training_arguments(inputs)),
        ("create_tuning_job", tuning_arguments(inputs)),
    ]:
        result = run_call(
            app, call(name, **arguments), context(allow_mutations=True, submission_key="ai")
        )
        assert result.http_status == 409
        assert result.error.code == "unsupported_model_algorithm"
    tuning = tracking_client.post(
        "/api/v1/tuning-jobs", json=inputs, headers={"Idempotency-Key": "tune"}
    )
    assert tuning.status_code == 409
    assert tuning.json()["error"]["code"] == "unsupported_model_algorithm"
    assert not store.experiments.records
    app.state.settings.artifact_root = tmp_path
    body = {**inputs, "config": {"algorithm": "logistic_regression", "epochs": 30}}
    record = submit(tracking_client, body).json()
    assert (
        asyncio.run(execute_experiment(store, "demo", record["id"], app.state.settings))
        == "succeeded"
    )
    completed = tracking_client.get(f"/api/v1/experiments/{record['id']}").json()
    assert completed["config"]["algorithm"] == "logistic_regression"
    for artifact in completed["artifacts"]:
        response = tracking_client.get(
            f"/api/v1/experiments/{record['id']}/artifacts/{artifact['name']}"
        )
        assert response.status_code == 200
        assert len(response.content) == artifact["size_bytes"]
        assert hashlib.sha256(response.content).hexdigest() == artifact["sha256"]
    version = tracking_client.post(
        f"/api/v1/models/{linear}/versions", json={"version": "v1", "experiment_id": record["id"]}
    )
    assert version.status_code == 201, version.text
    assert submit(tracking_client, body).json()["id"] == record["id"]


@pytest.mark.parametrize("classes", [2, 3])
def test_linear_checkpoint_metrics_scaling_selection_and_reload(
    training_input, classes, monkeypatch
):
    import torch
    from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

    from ml_pipeline_pro import training

    selected_predictions = []
    original_scores = training._scores

    def observe_scores(model, features, targets, num_classes):
        with torch.inference_mode():
            selected_predictions.append(model(features).argmax(1).clone())
        return original_scores(model, features, targets, num_classes)

    monkeypatch.setattr(training, "_scores", observe_scores)

    settings, dataset, experiment = training_input
    # Separable fixed splits; validation/test offsets detect accidental full-data scaling.
    rows = ["feature_1,feature_2,target,split"]
    centers = [(-4, -4), (4, -4), (0, 4)]
    for split, count, offset in [("train", 12, 0), ("validation", 4, 0.1), ("test", 4, 0.2)]:
        for label, (x, y) in enumerate(centers[:classes]):
            rows.extend(
                f"{x + i * 0.01 + offset},{y + (i % 3) * 0.02},{label},{split}"
                for i in range(count)
            )
    path = settings.dataset_root / dataset.uri
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    loaded = load_dataset(dataset, settings)
    dataset = dataset.model_copy(
        update={"sha256": loaded.sha256, "num_classes": classes, "row_counts": loaded.row_counts}
    )
    experiment.config = LogisticRegressionConfig(
        algorithm="logistic_regression", epochs=50, l2_strength=0.01
    )
    result = train_classifier(
        experiment, dataset, "linear", settings, architecture="logistic_regression"
    )
    content = (settings.artifact_root / result.artifacts[0].uri).read_bytes()
    model, checkpoint = load_checkpoint(content, experiment, dataset)
    assert isinstance(model, torch.nn.Linear)
    assert set(checkpoint["state_dict"]) == {"weight", "bias"}
    train = torch.tensor(loaded.splits["train"].features)
    assert torch.equal(checkpoint["mean"], train.mean(0))
    assert torch.equal(checkpoint["std"], train.std(0, unbiased=False).clamp_min(1e-6))
    test = loaded.splits["test"]
    x = (torch.tensor(test.features) - checkpoint["mean"]) / checkpoint["std"]
    predictions = model(x).argmax(1).tolist()
    assert predictions == selected_predictions[-1].tolist()
    assert result.metrics["test_accuracy"] == pytest.approx(
        accuracy_score(test.targets, predictions), abs=1e-6
    )
    assert result.metrics["test_f1"] == pytest.approx(
        f1_score(test.targets, predictions, average="macro"), abs=1e-6
    )
    for name, scorer in [("precision", precision_score), ("recall", recall_score)]:
        assert result.metrics[f"test_{name}"] == pytest.approx(
            scorer(test.targets, predictions, average="macro", zero_division=0), abs=1e-6
        )
    assert result.metrics["validation_f1"] >= 0.9
    again = train_classifier(
        experiment, dataset, "repeat", settings, architecture="logistic_regression"
    )
    reloaded, _ = load_checkpoint(
        (settings.artifact_root / again.artifacts[0].uri).read_bytes(), experiment, dataset
    )
    assert torch.equal(model(x).argmax(1), reloaded(x).argmax(1))
    original_hashes = [a.sha256 for a in result.artifacts]
    experiment.artifacts = result.artifacts
    experiment.metrics = result.metrics
    from ml_pipeline_pro.training import evaluate_checkpoint

    evaluated = evaluate_checkpoint(experiment, dataset, "evaluation", settings, TrainingControl())
    assert evaluated.metrics == result.metrics
    assert original_hashes == [
        hashlib.sha256((settings.artifact_root / a.uri).read_bytes()).hexdigest()
        for a in result.artifacts
    ]
    # Changing only test labels cannot affect the validation-selected checkpoint.
    path.write_text(
        "\n".join(
            ",".join([*row.split(",")[:2], str((int(row.split(",")[2]) + 1) % classes), "test"])
            if row.endswith(",test")
            else row
            for row in rows
        )
        + "\n",
        encoding="utf-8",
    )
    dataset.sha256 = load_dataset(dataset, settings).sha256
    changed = train_classifier(
        experiment, dataset, "changed", settings, architecture="logistic_regression"
    )
    assert changed.artifacts[0].sha256 == result.artifacts[0].sha256
    assert changed.metrics["validation_f1"] == result.metrics["validation_f1"]


def test_worker_rechecks_model_config(training_input):
    settings, dataset, experiment = training_input
    experiment.config = LogisticRegressionConfig(algorithm="logistic_regression")
    with pytest.raises(TrainingError, match="algorithm mismatch"):
        train_classifier(experiment, dataset, "mismatch", settings)


def test_l2_gradient_penalizes_weights_only(training_input, monkeypatch):
    import torch

    settings, dataset, experiment = training_input
    strength = 0.2
    experiment.config = LogisticRegressionConfig(
        algorithm="logistic_regression", epochs=1, l2_strength=strength
    )
    original_adam = torch.optim.Adam
    original_loss = torch.nn.CrossEntropyLoss
    observed = {}

    class CheckedAdam(original_adam):
        def __init__(self, params, **kwargs):
            super().__init__(params, **kwargs)
            observed["params"] = self.param_groups[0]["params"]

        def step(self, *args, **kwargs):
            weight, bias = observed["params"]
            expected_weight, expected_bias = observed["ce_gradients"]
            assert torch.allclose(weight.grad, expected_weight + strength * weight, atol=1e-6)
            assert torch.allclose(bias.grad, expected_bias, atol=1e-6)
            observed["checked"] = True
            return super().step(*args, **kwargs)

    class ObservedLoss(original_loss):
        def forward(self, logits, targets):
            loss = super().forward(logits, targets)
            observed["ce_gradients"] = torch.autograd.grad(
                loss, observed["params"], retain_graph=True
            )
            return loss

    monkeypatch.setattr(torch.optim, "Adam", CheckedAdam)
    monkeypatch.setattr(torch.nn, "CrossEntropyLoss", ObservedLoss)
    train_classifier(
        experiment, dataset, "regularized", settings, architecture="logistic_regression"
    )
    assert observed["checked"]


@pytest.mark.parametrize(
    "change",
    [
        {"algorithm": "unknown"},
        {"format_version": 2},
        {"num_classes": 5},
        {"feature_columns": ["wrong"]},
    ],
)
def test_checkpoint_rejects_invalid_algorithm_or_dimensions(training_input, change):
    import torch

    settings, dataset, experiment = training_input
    experiment.config = LogisticRegressionConfig(algorithm="logistic_regression", epochs=2)
    result = train_classifier(
        experiment, dataset, "linear", settings, architecture="logistic_regression"
    )
    checkpoint = torch.load(settings.artifact_root / result.artifacts[0].uri, weights_only=True)
    checkpoint.update(change)
    stream = io.BytesIO()
    torch.save(checkpoint, stream)
    with pytest.raises(TrainingError):
        load_checkpoint(stream.getvalue(), experiment, dataset)
