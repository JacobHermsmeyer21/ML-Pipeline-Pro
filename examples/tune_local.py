"""Run a bounded serial Optuna search without Docker, MongoDB, or Redis."""

import argparse
import hashlib
import json
from time import monotonic, perf_counter

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.datasets import DatasetValidationError, load_dataset
from ml_pipeline_pro.schemas import DatasetCreate, DatasetRecord, ExperimentRecord, ModelRecord
from ml_pipeline_pro.training import evaluate_checkpoint, train_classifier
from ml_pipeline_pro.training_control import TrainingControl, TrainingError
from ml_pipeline_pro.tuning_sampler import suggest_trial
from ml_pipeline_pro.tuning_schemas import TrialRecord, TuningLimits, TuningRecord


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--seconds", type=int, default=300)
    args = parser.parse_args()
    settings = Settings()
    limits = TuningLimits(max_trials=args.trials, max_runtime_seconds=args.seconds)
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
    model = ModelRecord(project_id="demo", name="local-tuning")
    job = TuningRecord(
        project_id="demo",
        dataset_id=dataset.id,
        model_id=model.id,
        limits=limits,
        submission_key="local",
        request_hash="0" * 64,
    )
    deadline = monotonic() + limits.max_runtime_seconds
    search_deadline = deadline - min(10, limits.max_runtime_seconds / 10)
    history = []
    experiments = {}
    summary_root = settings.artifact_root / "local-tuning" / job.id
    summary_root.mkdir(parents=True, exist_ok=True)
    for number in range(limits.max_trials):
        if monotonic() >= search_deadline:
            break
        job.scheduled_trials = number
        reservation = suggest_trial(job, history)
        experiment = ExperimentRecord(
            id=reservation.experiment_id,
            project_id="demo",
            dataset_id=dataset.id,
            model_id=model.id,
            config=reservation.config,
            submission_key=f"local-{number}",
            request_hash=hashlib.sha256(
                json.dumps(reservation.parameters, sort_keys=True).encode()
            ).hexdigest(),
            tuning_job_id=job.id,
            tuning_trial_number=number,
            evaluate_test=False,
        )
        trial = TrialRecord(
            id=reservation.trial_id,
            project_id="demo",
            tuning_job_id=job.id,
            number=number,
            experiment_id=experiment.id,
            parameters=reservation.parameters,
            config=reservation.config,
        )
        started = perf_counter()
        try:
            result = train_classifier(
                experiment,
                dataset,
                "local",
                settings,
                control=TrainingControl(deadline=search_deadline),
                evaluate_test=False,
            )
            experiment.status = "succeeded"
            experiment.metrics = result.metrics
            experiment.artifacts = result.artifacts
            experiment.dependencies = result.dependencies
            trial.status = "succeeded"
            trial.metrics = result.metrics
            trial.objective_value = result.metrics[job.objective_metric]
            experiments[experiment.id] = experiment
        except (TrainingError, DatasetValidationError) as exc:
            trial.status = "failed"
            trial.error_summary = str(exc)
        trial.duration_seconds = perf_counter() - started
        history.append(trial)
        (summary_root / "trials.json").write_text(
            json.dumps(
                [item.model_dump(mode="json", exclude={"worker_token"}) for item in history],
                indent=2,
            ),
            encoding="utf-8",
        )
    valid = [trial for trial in history if trial.status == "succeeded"]
    if not valid:
        raise SystemExit("No trial succeeded; inspect " + str(summary_root / "trials.json"))
    best = min(valid, key=lambda trial: (-trial.objective_value, trial.number))
    selected = experiments[best.experiment_id]
    final = "succeeded"
    try:
        evaluated = evaluate_checkpoint(
            selected, dataset, "final", settings, TrainingControl(deadline=deadline)
        )
        selected.metrics = evaluated.metrics
        selected.artifacts = evaluated.artifacts
    except TrainingError:
        final = "skipped_budget"
    output = {
        "tuning_job_id": job.id,
        "completed_trials": len(history),
        "best_parameters": best.parameters,
        "best_validation_f1": best.objective_value,
        "final_evaluation": final,
        "metrics": selected.metrics,
        "artifacts": [artifact.model_dump() for artifact in selected.artifacts],
        "summary_directory": str(summary_root),
    }
    (summary_root / "summary.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
