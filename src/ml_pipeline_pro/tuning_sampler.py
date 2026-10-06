"""Reconstruct seeded TPE suggestions from durable trial history."""

from uuid import NAMESPACE_URL, uuid5

from ml_pipeline_pro.schemas import TrainingConfig
from ml_pipeline_pro.tuning_schemas import TrialReservation, TuningRecord


def suggest_trial(job: TuningRecord, history) -> TrialReservation:
    import optuna
    from optuna.distributions import CategoricalDistribution, FloatDistribution, IntDistribution
    from optuna.trial import TrialState, create_trial

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    space = job.search_space
    distributions = {
        "learning_rate": FloatDistribution(
            space.learning_rate.low, space.learning_rate.high, log=space.learning_rate.log
        ),
        "batch_size": CategoricalDistribution(space.batch_size.choices),
        "hidden_units": IntDistribution(
            space.hidden_units.low, space.hidden_units.high, step=space.hidden_units.step
        ),
    }
    number = job.scheduled_trials
    sampler = optuna.samplers.TPESampler(
        seed=(job.sampler_seed + number) % 2**32, n_startup_trials=2
    )
    study = optuna.create_study(direction=job.direction, sampler=sampler)
    for saved in history:
        succeeded = saved.status == "succeeded" and saved.objective_value is not None
        study.add_trial(
            create_trial(
                params=saved.parameters,
                distributions=distributions,
                value=saved.objective_value if succeeded else None,
                state=TrialState.COMPLETE if succeeded else TrialState.FAIL,
            )
        )
    proposed = study.ask(fixed_distributions=distributions)
    config = TrainingConfig.model_validate({**job.config.model_dump(), **proposed.params})
    return TrialReservation(
        number=number,
        trial_id=str(uuid5(NAMESPACE_URL, f"mlpp:{job.id}:trial:{number}")),
        experiment_id=str(uuid5(NAMESPACE_URL, f"mlpp:{job.id}:experiment:{number}")),
        parameters=proposed.params,
        config=config,
    )
