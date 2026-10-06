"""Deterministic CPU PyTorch classification with isolated test evaluation."""

import copy
import io
import json
import platform
from dataclasses import dataclass
from importlib.metadata import version
from time import perf_counter

from ml_pipeline_pro.artifacts import write_artifact
from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.datasets import DatasetValidationError, load_dataset
from ml_pipeline_pro.schemas import ArtifactReference, DatasetRecord, ExperimentRecord


class TrainingError(ValueError):
    pass


@dataclass
class TrainingResult:
    metrics: dict[str, float]
    artifacts: list[ArtifactReference]
    dependencies: dict[str, str]


def train_classifier(
    experiment: ExperimentRecord, dataset: DatasetRecord, token: str, settings: Settings
) -> TrainingResult:
    started = perf_counter()
    try:
        import torch
    except ImportError:
        raise TrainingError("Install the training extra to run PyTorch experiments") from None

    config = experiment.config

    def check_budget() -> None:
        if perf_counter() - started > config.max_runtime_seconds:
            raise TrainingError("Training exceeded its configured runtime budget")

    loaded = load_dataset(dataset, settings)
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

    def evaluate(x, y) -> tuple[float, float]:
        model.eval()
        with torch.inference_mode():
            predictions = model(x).argmax(dim=1)
            accuracy = float((predictions == y).float().mean())
            class_f1 = []
            for label in range(loaded.num_classes):
                true_positive = int(((predictions == label) & (y == label)).sum())
                false_positive = int(((predictions == label) & (y != label)).sum())
                false_negative = int(((predictions != label) & (y == label)).sum())
                denominator = 2 * true_positive + false_positive + false_negative
                class_f1.append(2 * true_positive / denominator if denominator else 0.0)
            return accuracy, sum(class_f1) / len(class_f1)

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
        _, score = evaluate(validation_x, validation_y)
        # Ties retain the first checkpoint; test labels never select a model.
        if score > best_f1:
            best_f1, best_epoch = score, epoch + 1
            best_state = copy.deepcopy(model.state_dict())

    check_budget()
    model.load_state_dict(best_state)
    validation_accuracy, validation_f1 = evaluate(validation_x, validation_y)
    test = loaded.splits["test"]
    test_x = (torch.tensor(test.features, dtype=torch.float32) - mean) / std
    test_y = torch.tensor(test.targets, dtype=torch.long)
    test_accuracy, test_f1 = evaluate(test_x, test_y)
    metrics = {
        "validation_accuracy": validation_accuracy,
        "validation_f1": validation_f1,
        "test_accuracy": test_accuracy,
        "test_f1": test_f1,
        "best_epoch": float(best_epoch),
    }
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
        "selection_metric": "validation_f1",
        "selection_direction": "maximize",
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
