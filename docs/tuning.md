# Bounded classification tuning

The tuning API contracts and MongoDB job/trial storage are implemented. Optuna
search execution is the next part currently being built; the initial contract
commit alone does not execute searches.

Tuning uses a registered dataset/model from the [experiment walkthrough](experiments.md).
Endpoints require `X-Project-ID`, an `X-API-Key` when configured, and an
`Idempotency-Key` for submission.

| Endpoint | Behavior |
| --- | --- |
| `POST /api/v1/tuning-jobs` | Validate and queue an idempotent tuning request |
| `GET /api/v1/tuning-jobs` | List jobs within a project |
| `GET /api/v1/tuning-jobs/{id}` | Inspect status, progress, budget, and selected trial |
| `GET /api/v1/tuning-jobs/{id}/trials` | Inspect saved trial configurations and outcomes |
| `POST /api/v1/tuning-jobs/{id}/cancel` | Cancel queued work or request cancellation of running work |

The initial defaults are five trials, a five-minute runtime budget, and one trial
at a time. Limits are 1–50 trials and 2–600 seconds. Search supports learning rate
float ranges, batch size choices, and stepped hidden-unit integer ranges.
Selection supports validation F1 or validation accuracy, both maximized. Test
metrics are excluded from the tuning objective.

Duplicate submission with the same body/key returns the existing job. Reusing a
key with different settings returns `409`. Queue outages return `503` with the
durable job ID. Queued cancellation is immediate; running cancellation returns
`cancel_requested`. Completed jobs cannot be cancelled.
