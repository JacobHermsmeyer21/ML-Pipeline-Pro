"""Run the real CPU training adapter without MongoDB, Redis, or Docker."""

import argparse
import json

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.datasets import load_dataset
from ml_pipeline_pro.schemas import (
    DatasetCreate,
    DatasetRecord,
    ExperimentRecord,
    ModelRecord,
    TrainingConfig,
)
from ml_pipeline_pro.training import train_classifier


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs", type=int, default=30)
    args = parser.parse_args()
    settings = Settings()
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
    model = ModelRecord(project_id="demo", name="local-classifier")
    experiment = ExperimentRecord(
        project_id="demo",
        model_id=model.id,
        dataset_id=dataset.id,
        submission_key="local",
        request_hash="0" * 64,
        config=TrainingConfig(seed=args.seed, epochs=args.epochs),
    )
    result = train_classifier(experiment, dataset, "local", settings)
    print(
        json.dumps(
            {
                "experiment_id": experiment.id,
                "metrics": result.metrics,
                "artifacts": [artifact.model_dump() for artifact in result.artifacts],
                "artifact_root": str(settings.artifact_root),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
