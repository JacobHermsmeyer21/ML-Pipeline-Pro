# Bounded classification tuning

Bounded Optuna TPE searches run through the existing Celery worker. Each trial
uses training/validation data. After the search is frozen, the selected checkpoint
receives final test evaluation. Job and trial state are stored in MongoDB.

The initial serial workflow is implemented. See the [project audit](project-status.md)
for development status and open ownership/recovery findings before scaling it.

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
`cancel_requested`. Succeeded/failed jobs cannot be cancelled; repeating a
cancellation on an already cancelled job returns that job.

## Try the local demo

From the repository root, install the training extra and run a five-trial search
without services:

```powershell
uv sync --locked --extra training
uv run --locked --extra training python examples/tune_local.py --trials 5 --seconds 300
```

The demo prints the selected parameters, validation score, final test metrics,
and artifact locations. It saves every trial and a result summary under
`artifacts/local-tuning/JOB_ID/`. It does not register records in MongoDB.

Trial checkpoints/manifests live under `artifacts/demo/EXPERIMENT_ID/local/`.
The selected checkpoint keeps its original path; its evaluated manifest is
written under `artifacts/demo/EXPERIMENT_ID/final/`. An original
`local/manifest.json` with `test_evaluated: false` remains valid trial evidence,
even if its experiment wins. Follow `summary.json` artifact references to the
updated winner manifest; see [reading a local manifest](project-status.md#reading-a-local-tuning-manifest).

## Run tuning through the API

Rebuild the stack with `docker compose up --build --wait --wait-timeout 300`.
Register inputs using the [experiment walkthrough](experiments.md), then continue
in that PowerShell session with `$base`, `$headers`, `$dataset`, and `$model`:

```powershell
$tuningHeaders = $headers.Clone()
$tuningHeaders['Idempotency-Key'] = [guid]::NewGuid().ToString()
$tuningBody = @{
    dataset_id = $dataset.id
    model_id = $model.id
    objective_metric = 'validation_f1'
    direction = 'maximize'
    sampler_seed = 42
    config = @{ seed = 42; epochs = 30; max_runtime_seconds = 60 }
    limits = @{ max_trials = 5; max_runtime_seconds = 300; concurrency = 1 }
    search_space = @{
        learning_rate = @{ low = 0.0001; high = 0.05; log = $true }
        batch_size = @{ choices = @(8, 16, 32) }
        hidden_units = @{ low = 8; high = 64; step = 8 }
    }
} | ConvertTo-Json -Depth 8
$job = Invoke-RestMethod -Method Post -Uri "$base/tuning-jobs" `
    -Headers $tuningHeaders -ContentType 'application/json' -Body $tuningBody

$pollDeadline = (Get-Date).AddMinutes(6)
do {
    Start-Sleep -Seconds 1
    $result = Invoke-RestMethod -Uri "$base/tuning-jobs/$($job.id)" -Headers $headers
} while ($result.status -in @('queued', 'running', 'cancel_requested') -and (Get-Date) -lt $pollDeadline)

if ($result.status -in @('queued', 'running', 'cancel_requested')) {
    throw "Tuning polling timed out with status $($result.status). Retrieve the job again to inspect progress."
}
$result
$trials = Invoke-RestMethod -Uri "$base/tuning-jobs/$($job.id)/trials" -Headers $headers
$trials.items | Select-Object number, status, parameters, objective_value, duration_seconds
```

The job exposes progress counts, the selected configuration and experiment,
budget deadlines, and a stop reason. Trial metrics contain validation results;
only the selected experiment receives test metrics. Trial `number` is zero-based.
`completed_trials` counts succeeded, failed, and cancelled terminal trials;
`failed_trials` counts failures only. Trial records keep their validation-only
metrics after winner evaluation; retrieve the selected experiment for test metrics.

When the job and `final_evaluation` both report `succeeded`, retrieve and register
that checkpoint:

```powershell
if ($result.status -ne 'succeeded' -or $result.final_evaluation -ne 'succeeded') {
    throw 'Version registration requires successful tuning and final test evaluation. Inspect the job result first.'
}
$winner = Invoke-RestMethod -Uri "$base/experiments/$($result.best_experiment_id)" -Headers $headers
Invoke-RestMethod -Uri "$base/experiments/$($winner.id)/artifacts/model.pt" `
    -Headers $headers -OutFile tuned-model.pt
$versionBody = @{ version = 'tuned-v1'; experiment_id = $winner.id } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$base/models/$($model.id)/versions" `
    -Headers $headers -ContentType 'application/json' -Body $versionBody
```

Version registration requires final test evaluation. It is an explicit action
and does not automatically deploy or promote the model.

## Budgets, cancellation, and recovery

The overall clock starts on the first worker claim, excludes queue wait, and is
preserved during recovery. Each trial also has its own training runtime limit. Search
reserves the smaller of ten seconds or ten percent of the total budget for final
test evaluation. Scheduling stops at the trial count or search deadline. Checks
occur between batches, so a single operation can extend past the cooperative
deadline. Celery's soft/hard task limits are 620/630 seconds. The worker container
permits one concurrent job, one CPU, and 1 GiB of memory.

If successful trials remain when search time expires, their best validation result
is retained. If final test time also expires, the job reports
`final_evaluation: skipped_budget`; model version registration is blocked. Submit
a separate normal experiment with `best_config` and its own budget for full
evaluation. If all trials fail, the job fails while retaining their configurations
and errors. Nonfinite objectives cannot become winners.

To cancel:

```powershell
Invoke-RestMethod -Method Post -Uri "$base/tuning-jobs/$($job.id)/cancel" -Headers $headers
```

Cancellation prevents new reservations and signals the active trial to stop
between batches. Completed results remain available. Expired leases are recovered
by the scheduler, with at most `MLPP_WORKER_MAX_ATTEMPTS` claims. Each reservation
fixes its number, parameters, and experiment ID before execution. Replacement
workers reuse it and completed training without resetting the budget.

Beat schedules recovery every 15 seconds, but its recovery tasks share the worker
with training/tuning, so queue load can delay redispatch. Current tests exercise
saved reservations/training with forced lease expiry and simulated storage errors.
Actual worker termination/restart tests and the audit's child-claim/final-commit
ownership gaps remain [follow-up work](project-status.md#open-audit-findings).

The sampler uses two successful startup trials before TPE proposals. Proposals
reconstruct the study from saved outcomes with a seed derived from the sampler
seed and trial number. Recovered and uninterrupted searches follow the same
sequence in the tested environment. Ties retain the earliest trial; test metrics
never break ties.

## Validation

```powershell
uv sync --locked --extra training
uv run --locked --extra training pytest -m "not integration"
```

With the full stack running, use the integration command from
[experiments.md](experiments.md#validate-the-full-stack). All 126 local unit/training
tests and nine real-service integration tests passed on October 6, 2026, including
real tuning indexes and deadlines, recovery after saved training, queued tuning,
final test evaluation, and active cancellation.

The audit reran both suites and the five-trial demo successfully. Python 3.11/3.13
checks, dependency audits, and rebuilt Docker integration also passed
[baseline CI for 0e37e6e](https://github.com/JacobHermsmeyer21/ML-Pipeline-Pro/actions/runs/37541937953).
Passing existing cases does not close the newly identified ownership findings.
The [historical validation report](test-validation.md) preserves ten repeated runs
against its original commit.

For isolated test services, override `MLPP_TEST_API_BASE_URL`,
`MLPP_TEST_MONGODB_URI`, and `MLPP_TEST_REDIS_URL`.
