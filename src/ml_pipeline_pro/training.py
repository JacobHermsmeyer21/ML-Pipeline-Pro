"""Deterministic CPU PyTorch classification with isolated test evaluation."""

import copy
import io
import json
import platform
from dataclasses import dataclass
from importlib.metadata import version
from time import perf_counter

from ml_pipeline_pro.artifacts import read_artifact, write_artifact
from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.datasets import DatasetValidationError, load_dataset
from ml_pipeline_pro.preparation_files import read_preparation
from ml_pipeline_pro.schemas import ArtifactReference, DatasetRecord, ExperimentRecord
from ml_pipeline_pro.training_control import TrainingBudgetExceeded, TrainingControl, TrainingError


@dataclass
class TrainingResult:
    metrics: dict[str, float]
    artifacts: list[ArtifactReference]
    dependencies: dict[str, str]


def train_classifier(
    experiment: ExperimentRecord,
    dataset: DatasetRecord,
    token: str,
    settings: Settings,
    *,
    control: TrainingControl | None = None,
    evaluate_test: bool = True,
    objective_metric: str = "validation_f1",
) -> TrainingResult:
    started = perf_counter()
    try:
        import torch
    except ImportError:
        raise TrainingError("Install the training extra to run PyTorch experiments") from None

    config = experiment.config

    def check_budget() -> None:
        if control:
            control.check()
        if perf_counter() - started > config.max_runtime_seconds:
            raise TrainingBudgetExceeded("Training exceeded its configured runtime budget")

    check_budget()
    loaded = load_dataset(dataset, settings)
    preparation = read_preparation(dataset, settings)
    if loaded.sha256 != dataset.sha256:
        raise DatasetValidationError("Dataset changed after registration; register a new version")
    torch.set_num_threads(1)
    torch.manual_seed(config.seed)
    torch.use_deterministic_algorithms(True)
    generator = torch.Generator().manual_seed(config.seed)

    train = loaded.splits["train"]
    features = torch.tensor(train.features, dtype=torch.float32)
    targets = torch.tensor(train.targets, dtype=torch.long)
    mean = features.mean(dim=0)
    std = features.std(dim=0, unbiased=False).clamp_min(1e-6)
    features = (features - mean) / std
    validation = loaded.splits["validation"]
    validation_x = (torch.tensor(validation.features, dtype=torch.float32) - mean) / std
    validation_y = torch.tensor(validation.targets, dtype=torch.long)

    model = torch.nn.Sequential(
        torch.nn.Linear(len(dataset.feature_columns), config.hidden_units),
        torch.nn.ReLU(),
        torch.nn.Linear(config.hidden_units, loaded.num_classes),
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
    loss_function = torch.nn.CrossEntropyLoss()

    best_f1 = -1.0
    best_state = None
    best_epoch = 0
    for epoch in range(config.epochs):
        check_budget()
        model.train()
        order = torch.randperm(len(targets), generator=generator)
        for start in range(0, len(targets), config.batch_size):
            check_budget()
            batch = order[start : start + config.batch_size]
            optimizer.zero_grad(set_to_none=True)
            loss = loss_function(model(features[batch]), targets[batch])
            if not torch.isfinite(loss):
                raise TrainingError(
                    "Training produced nonfinite loss; review the data and learning rate"
                )
            loss.backward()
            optimizer.step()
        accuracy, f1 = _scores(model, validation_x, validation_y, loaded.num_classes)
        score = f1 if objective_metric == "validation_f1" else accuracy
        # Ties retain the first checkpoint; test labels never select a model.
        if score > best_f1:
            best_f1, best_epoch = score, epoch + 1
            best_state = copy.deepcopy(model.state_dict())

    check_budget()
    model.load_state_dict(best_state)
    validation_accuracy, validation_f1 = _scores(
        model, validation_x, validation_y, loaded.num_classes
    )
    metrics = {
        "validation_accuracy": validation_accuracy,
        "validation_f1": validation_f1,
        "best_epoch": float(best_epoch),
    }
    if evaluate_test:
        check_budget()
        test = loaded.splits["test"]
        test_x = (torch.tensor(test.features, dtype=torch.float32) - mean) / std
        test_y = torch.tensor(test.targets, dtype=torch.long)
        test_accuracy, test_f1 = _scores(model, test_x, test_y, loaded.num_classes)
        metrics.update(test_accuracy=test_accuracy, test_f1=test_f1)
    dependencies = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "torch": str(torch.__version__),
        "numpy": version("numpy"),
        "ml_pipeline_pro": version("ml-pipeline-pro"),
    }
    checkpoint = io.BytesIO()
    torch.save(
        {
            "state_dict": best_state,
            "mean": mean,
            "std": std,
            "feature_columns": dataset.feature_columns,
            "num_classes": loaded.num_classes,
            "hidden_units": config.hidden_units,
            **({"preparation": preparation} if preparation is not None else {}),
        },
        checkpoint,
    )
    manifest = {
        "experiment_id": experiment.id,
        "project_id": experiment.project_id,
        "model_id": experiment.model_id,
        "dataset": dataset.model_dump(mode="json"),
        "config": config.model_dump(),
        "metrics": metrics,
        "dependencies": dependencies,
        "selection_metric": objective_metric,
        "selection_direction": "maximize",
        "test_evaluated": evaluate_test,
        **({"preparation": preparation} if preparation is not None else {}),
    }
    check_budget()
    artifacts = [
        write_artifact(
            checkpoint.getvalue(), "model.pt", experiment.project_id, experiment.id, token, settings
        ),
        write_artifact(
            json.dumps(manifest, indent=2, sort_keys=True).encode(),
            "manifest.json",
            experiment.project_id,
            experiment.id,
            token,
            settings,
        ),
    ]
    return TrainingResult(metrics, artifacts, dependencies)


def _scores(model, features, targets, num_classes: int) -> tuple[float, float]:
    import torch

    model.eval()
    with torch.inference_mode():
        predictions = model(features).argmax(dim=1)
        accuracy = float((predictions == targets).float().mean())
        class_f1 = []
        for label in range(num_classes):
            tp = int(((predictions == label) & (targets == label)).sum())
            fp = int(((predictions == label) & (targets != label)).sum())
            fn = int(((predictions != label) & (targets == label)).sum())
            denominator = 2 * tp + fp + fn
            class_f1.append(2 * tp / denominator if denominator else 0.0)
        return accuracy, sum(class_f1) / len(class_f1)


def evaluate_checkpoint(
    experiment: ExperimentRecord,
    dataset: DatasetRecord,
    token: str,
    settings: Settings,
    control: TrainingControl,
) -> TrainingResult:
    import torch

    control.check()
    loaded = load_dataset(dataset, settings)
    read_preparation(dataset, settings)
    if loaded.sha256 != dataset.sha256:
        raise DatasetValidationError("Dataset changed after registration; register a new version")
    reference = next(artifact for artifact in experiment.artifacts if artifact.name == "model.pt")
    content = read_artifact(reference, experiment.project_id, experiment.id, settings)
    checkpoint = torch.load(io.BytesIO(content), weights_only=True)
    model = torch.nn.Sequential(
        torch.nn.Linear(len(dataset.feature_columns), experiment.config.hidden_units),
        torch.nn.ReLU(),
        torch.nn.Linear(experiment.config.hidden_units, dataset.num_classes),
    )
    model.load_state_dict(checkpoint["state_dict"])
    control.check()
    test = loaded.splits["test"]
    features = (torch.tensor(test.features, dtype=torch.float32) - checkpoint["mean"]) / checkpoint[
        "std"
    ]
    accuracy, f1 = _scores(
        model, features, torch.tensor(test.targets, dtype=torch.long), dataset.num_classes
    )
    control.check()
    metrics = {**experiment.metrics, "test_accuracy": accuracy, "test_f1": f1}
    original_manifest = next(
        artifact for artifact in experiment.artifacts if artifact.name == "manifest.json"
    )
    manifest = json.loads(
        read_artifact(original_manifest, experiment.project_id, experiment.id, settings)
    )
    manifest.update(
        metrics=metrics, test_evaluated=True, final_tuning_job_id=experiment.tuning_job_id
    )
    updated_manifest = write_artifact(
        json.dumps(manifest, indent=2, sort_keys=True).encode(),
        "manifest.json",
        experiment.project_id,
        experiment.id,
        token,
        settings,
    )
    return TrainingResult(metrics, [reference, updated_manifest], experiment.dependencies)
