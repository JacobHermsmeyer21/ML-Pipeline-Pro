# Workflow guide

Use these workflows after the [README setup](../../README.md#development-setup).
The examples cover the implemented backend. Conversation routes, durable history,
grounded reads and confirmed actions now exist; the evaluated [guided local model](guided-midterm-demo.md)
and [combined walkthrough](midterm-walkthrough.md) include real-model/history evidence.

- [Classification experiments](#classification-experiment-walkthrough): register inputs, train, compare, download, and register versions.
- [Bounded tuning](#bounded-classification-tuning): run a search, inspect trials, cancel, and register the evaluated winner.
- [Conversation tools](#conversation-tool-layer): call the typed Python tools over the existing API.
- [Browser dataset workflow](dashboard.md#browser-walkthrough): import original CSVs, review encodings/splits, edit columns into new versions and train.
- [Permanent deletion](dashboard.md#delete-a-dataset-or-model): preview and erase a dataset/classifier cascade, or resume an uncertain cleanup.

Run checks using [verification](verification.md). Recorded results and remaining
limitations belong in [project status](../project/project-status.md), and course acceptance
belongs in the [course checklist](../project/course-requirements.md).

## Classification experiment walkthrough

Start the stack with `docker compose up --build --wait --wait-timeout 300`.
Docker Compose 2.24 or later is required. Open `http://127.0.0.1:8000/docs` to
inspect the API. All metadata, experiment, and tuning endpoints require an
`X-Project-ID` header and an `X-API-Key` when project keys are configured.

This walkthrough uses direct registration of an already prepared numeric CSV.
For raw categorical CSVs, use the [dashboard preparation review](dashboard.md#review-and-change-encoding)
or [preview/prepare API](../reference/api.md#raw-csv-preparation). Both paths feed
the same CPU classification worker. [Current status](../project/project-status.md)
records verification and remaining limits.

The checked-in `examples/data/classification.csv` is synthetic. Its 120 rows are
explicitly split into 80 training, 20 validation, and 20 test examples. Each row
has two numeric features, an integer target (`0` or `1`), and a split name.
Regenerate the same file with `python examples/make_dataset.py`.

### Register the inputs

Run these commands in PowerShell:

```powershell
$base = 'http://127.0.0.1:8000/api/v1'
$headers = @{ 'X-Project-ID' = 'demo' }

$datasetBody = @{
    name = 'classification'
    version = 'v1'
    uri = 'classification.csv'
    feature_columns = @('feature_1', 'feature_2')
} | ConvertTo-Json
$dataset = Invoke-RestMethod -Method Post -Uri "$base/datasets" `
    -Headers $headers -ContentType 'application/json' -Body $datasetBody

$modelBody = @{ name = 'small-classifier' } | ConvertTo-Json
$model = Invoke-RestMethod -Method Post -Uri "$base/models" `
    -Headers $headers -ContentType 'application/json' -Body $modelBody

Invoke-RestMethod -Uri "$base/datasets/$($dataset.id)" -Headers $headers
Invoke-RestMethod -Uri "$base/models/$($model.id)" -Headers $headers
```

Registration returns `201`. The dataset response records its SHA-256 hash,
feature columns, number of classes, and row counts per split. The file is read
from `MLPP_DATASET_ROOT`; its URI must be a relative `.csv` path inside that
directory. Registration rejects files with invalid values, missing splits,
unknown classes, or excessive size. Custom data must be available at the same
relative path with identical contents to the API and eventual training worker.
With Compose, mount the same custom directory at `/app/examples/data` for the
API and worker. Registration records metadata and a hash; it does not upload,
copy, or preserve the CSV. Keep each registered version's file unchanged.

Dataset versions are unique within a project by `(name, version)`. Models are
unique within a project by name. Repeating registration returns `409`; retrieve
existing records with `GET /datasets` or `GET /models`, or use a new version/name.
Lists accept `limit` (1–100) and `offset` (nonnegative).

Managed upload/preparation routes instead publish files and replay matching saved
versions. To remove inputs from a saved dataset, use
[column editing](../reference/api.md#dataset-column-editing); it preserves the
original version, retained values and split membership. To erase a dataset/model
and its related history, review the separate
[permanent-deletion contract](../reference/api.md#permanent-dataset-and-model-deletion).
An erased training/tuning submission key returns 410 rather than recreating work.

### Project access

Development permits project selection without a key when no keys are configured.
To enforce keys, set `MLPP_PROJECT_API_KEYS` in `.env` to a JSON object mapping
project IDs to your own random keys (at least 16 characters). Add the matching
`X-API-Key` header to each request. Configuring any keys restricts access to the
listed projects. Production configuration requires keys; shared deployment still
needs TLS and a complete identity/authorization design.

MongoDB indexes enforce uniqueness and support project-scoped lists. Indexes are
created lazily on the first metadata request, so the API's liveness endpoint
remains available when MongoDB is offline. Storage outages return `503`.

### Submit a training experiment

Continue in the same PowerShell session:

```powershell
$submissionKey = [guid]::NewGuid().ToString()
$jobHeaders = $headers.Clone()
$jobHeaders['Idempotency-Key'] = $submissionKey
$experimentBody = @{
    dataset_id = $dataset.id
    model_id = $model.id
    config = @{
        seed = 42
        epochs = 30
        batch_size = 16
        learning_rate = 0.01
        hidden_units = 16
        max_runtime_seconds = 60
    }
} | ConvertTo-Json -Depth 5
$experiment = Invoke-RestMethod -Method Post -Uri "$base/experiments" `
    -Headers $jobHeaders -ContentType 'application/json' -Body $experimentBody

$deadline = (Get-Date).AddMinutes(2)
do {
    Start-Sleep -Seconds 1
    $result = Invoke-RestMethod -Uri "$base/experiments/$($experiment.id)" -Headers $headers
} while ($result.status -in @('queued', 'running') -and (Get-Date) -lt $deadline)
$result
if ($result.status -ne 'succeeded') {
    throw "Training did not succeed before the polling deadline: $($result.status). Inspect the experiment status and error_summary."
}
```

Submission returns `202`. Use a new idempotency key for each intentional run;
retry the same body/key after a connection error to avoid creating another
experiment. Reusing a key with a different configuration returns `409`.

The standalone lifecycle is `queued → running → succeeded` or `failed`. Tuning
child experiments can also become `cancelled`. A Redis outage during
dispatch returns `503` with the persisted experiment ID. The scheduler retries
undispatched jobs and queued jobs without progress after 60 seconds. Workers
atomically claim a job and renew a 30-second ownership lease. Expired leases are
recovered; repeated worker losses stop after three attempts by default. A stale
worker token is rejected by normal experiment completion writes. Tuning child
writes also check parent ownership in a MongoDB transaction; Compose initializes
the required replica set. See the [ownership fix](../project/project-status.md#ownership-fix-validation).

The worker rechecks the dataset hash before training. Preprocessing statistics
come only from training rows. It trains a small CPU PyTorch MLP and selects the
first checkpoint with the highest validation macro F1. Test metrics are computed
after that selection. Failure responses include an error summary; successful
responses include validation/test accuracy and macro F1, the selected epoch,
dependency versions, and artifact hashes.

Training has a cooperative runtime budget checked between batches, plus Celery
soft/hard task limits of 620/630 seconds. The training clock is per attempt and
excludes queue waiting; reclaiming a standalone experiment starts a new attempt.
The local worker container is limited to one CPU,
1 GiB of memory, and one concurrent job. Standalone experiment cancellation is
later work; [bounded tuning and its cancellation](workflows.md#bounded-classification-tuning) are available.

### Download artifacts and register a version

```powershell
Invoke-RestMethod -Uri "$base/experiments/$($experiment.id)/artifacts/model.pt" `
    -Headers $headers -OutFile model.pt
Invoke-RestMethod -Uri "$base/experiments/$($experiment.id)/artifacts/manifest.json" `
    -Headers $headers -OutFile manifest.json

$versionBody = @{ version = 'v1'; experiment_id = $experiment.id } | ConvertTo-Json
$version = Invoke-RestMethod -Method Post -Uri "$base/models/$($model.id)/versions" `
    -Headers $headers -ContentType 'application/json' -Body $versionBody
Invoke-RestMethod -Uri "$base/models/$($model.id)/versions" -Headers $headers
```

The checkpoint contains model weights, preprocessing tensors, and architecture
information. The manifest records dataset metadata/hash, configuration, selection
rule, metrics, and dependency versions. Downloads and model version registration
verify the stored hash and size. Version registration is an explicit API action
and requires a successful experiment belonging to that model with final test
evaluation. It does not deploy or serve the model.

For a second run, create a new idempotency key. Compare the completed runs with:

```powershell
$comparisonUri = "$base/experiments/compare?experiment_id=$($experiment.id)&experiment_id=SECOND_EXPERIMENT_ID&metric=validation_f1"
Invoke-RestMethod -Uri $comparisonUri -Headers $headers
```

Comparison requires the same dataset version and selects by validation F1 or
validation accuracy. `GET /experiments` accepts `status`, `model_id`, `limit`, and
`offset` filters. Test metrics cannot be the comparison selection objective.

### Try training without Docker

The actual adapter can run locally without metadata services or a queue:

```powershell
uv sync --locked --extra training
uv run --locked --extra training python examples/train_local.py
```

This prints metrics and saves checkpoint/manifest files under `artifacts/`.
It does not register records in MongoDB. After installing the training extra,
Windows users can also invoke the virtual environment directly:

```powershell
.\.venv\Scripts\python.exe examples\train_local.py
```

Unit tests verify that repeated runs on the same environment and input produce
identical metrics and checkpoint bytes. Reproducibility across different PyTorch
versions, operating systems, or hardware requires separately measured tolerances;
see [PyTorch's reproducibility guidance](https://docs.pytorch.org/docs/stable/notes/randomness.html).


## Bounded classification tuning

Bounded Optuna TPE searches run through the existing Celery worker. Each trial
uses training/validation data. After the search is frozen, the selected checkpoint
receives final test evaluation. Job and trial state are stored in MongoDB.

The initial serial workflow and transactional parent/child ownership fixes are
implemented. Tuning requires MongoDB transactions; Compose initializes a single-node
replica set. See the [project audit](../project/project-status.md) for remaining recovery work
before scaling it.

Tuning uses a registered dataset/model from the [experiment walkthrough](workflows.md#classification-experiment-walkthrough).
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

### Try the local demo

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
updated winner manifest; see [reading a local manifest](../project/project-status.md#reading-a-local-tuning-manifest).

### Run tuning through the API

Rebuild the stack with `docker compose up --build --wait --wait-timeout 300`.
Register inputs using the [experiment walkthrough](workflows.md#classification-experiment-walkthrough), then continue
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

### Budgets, cancellation, and recovery

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
Ten real-MongoDB transaction-boundary regression cases now verify rejection of
stale child claims, final evaluation commits, and other child mutations after
parent takeover. Ten additional [isolated Compose recovery cases](verification.md#worker-and-dependency-recovery-validation)
verify actual worker termination during training/final evaluation/persistence,
natural lease expiry and Beat redispatch, attempt exhaustion, and MongoDB/Redis
restarts. They preserve the original deadlines and reuse completed training.

The sampler uses two successful startup trials before TPE proposals. Proposals
reconstruct the study from saved outcomes with a seed derived from the sampler
seed and trial number. Recovered and uninterrupted searches follow the same
sequence in the tested environment. Ties retain the earliest trial; test metrics
never break ties.


## Conversation tool layer

The provider-independent Python tool layer exposes 13 typed operations over the
existing REST API. It validates tool arguments and trusted execution context,
returns public records with evidence references, and preserves API project
access, correlation IDs, job budgets, and submission idempotency.

This tool library was the first slice of [milestone 4](../../PLAN.md#implementation-milestones).
The later [conversation workflow](conversation-development.md) implements the local
LangChain adapter, chat/history endpoints, durable audit and exact confirmed actions.
Use [guided 7B](guided-midterm-demo.md) for the evaluated class configuration. The
[course instructions](../project/course-requirements.md) require pre-trained-model
integration; paid external inference and training a code language model are outside
the minimal scope. The contract examples below exercise the typed tools directly.

### Try the contract without services

```powershell
uv sync --locked --extra training
uv run --locked --extra training python examples/tools_local.py
```

The [example](../../examples/tools_local.py) uses scripted provider calls and a
synthetic queued experiment. It prints a successful read with experiment
evidence, followed by a validation error identifying the missing submission
configuration. It trains no model and contacts no API or provider. Its data is
an example, not an experiment result.

### Call an existing API

Run the [local stack](setup.md#run-the-whole-local-stack) and register inputs
using the [experiment guide](workflows.md#register-the-inputs). An application
can then use:

```python
import asyncio

from ml_pipeline_pro.tool_schemas import ToolCall, ToolContext
from ml_pipeline_pro.tool_transport import HttpToolTransport
from ml_pipeline_pro.tools import ToolDispatcher, tool_catalog


async def main():
    context = ToolContext(project_id="demo")
    async with HttpToolTransport("http://127.0.0.1:8000") as transport:
        dispatcher = ToolDispatcher(transport)
        result = await dispatcher.execute(
            ToolCall(name="list_experiments", arguments={"limit": 10}), context
        )
        print(result.model_dump_json(indent=2))
    print([item.name for item in tool_catalog()])


asyncio.run(main())
```

When project keys are configured, the host supplies `api_key` from its secret
source to `ToolContext`; keys must be printable ASCII without spaces. The API
checks it against `MLPP_PROJECT_API_KEYS`. Context omits the key and submission
key from its representation and serialized output. Tool arguments cannot choose
the project, key, origin, headers, correlation ID, or submission key.

The origin accepts HTTP(S), an optional port, and an optional trailing slash;
credentials, additional paths, queries, and fragments are rejected. The adapter
adds `/api/v1` itself. Resource IDs accept 1-128 letters, digits, underscores, or
hyphens, including current UUIDs. A future model adapter receives catalog schemas and
supplies tool calls; the host constructs context independently.

### Supported operations

| Tool | Arguments |
| --- | --- |
| `list_datasets`, `list_models`, `list_tuning_jobs` | Optional `limit`, `offset` |
| `get_dataset` | `dataset_id` |
| `get_model` | `model_id` |
| `list_experiments` | Optional `status`, `model_id`, `limit`, `offset` |
| `get_experiment` | `experiment_id` |
| `compare_experiments` | `experiment_ids` (2-20 distinct IDs); optional validation `metric` |
| `get_tuning_job` | `tuning_job_id` |
| `list_tuning_trials` | `tuning_job_id`; optional `limit`, `offset` |
| `create_experiment` | `dataset_id`, `model_id`, `config` with explicit `max_runtime_seconds` |
| `create_tuning_job` | Training inputs plus explicit `objective_metric` and `limits.max_trials` / `limits.max_runtime_seconds` |
| `cancel_tuning_job` | `tuning_job_id` |

All argument models reject extra fields. Lists default to `limit=50`, `offset=0`;
limits are 1-100 and offsets are nonnegative. Comparison defaults to
`validation_f1`; only `validation_f1` and `validation_accuracy` are supported.
The API checks succeeded experiments, finite metrics, and a common dataset.
Training and tuning retain their [existing parameter bounds](workflows.md#bounded-classification-tuning).
The catalog includes JSON schemas and defaults for optional arguments.

Dataset/model registration, artifact downloads, version registration, standalone
experiment cancellation, and code execution are outside this catalog.

### Submit and retry jobs

Mutations default to denied. The host sets `allow_mutations=True` after its
application has authorized that action. This is an execution permission, not a
new user identity/role or durable approval system. A live language-model application
needs the later reviewed approval and action-audit design.

The tool requires an explicit training runtime budget. Tuning additionally
requires its validation objective, trial count, and total runtime budget; missing
values return `tool_validation_error` with field locations before dispatch.
Other defaults come from the existing API schemas: training seed 42, 30 epochs,
batch size 16, learning rate 0.01, and 16 hidden units; tuning maximizes its
validation objective with sampler seed 42, the existing search-space defaults,
and concurrency 1. This stricter tool requiredness leaves direct API defaults
unchanged.

For each intentional submission, the host creates and retains a key:

```python
from uuid import uuid4

submission = ToolContext(project_id="demo", allow_mutations=True, submission_key=str(uuid4()))
training = ToolCall(
    name="create_experiment",
    arguments={
        "dataset_id": "REGISTERED_DATASET_ID",
        "model_id": "REGISTERED_MODEL_ID",
        "config": {"max_runtime_seconds": 60},
    },
)
# Inside the HTTP transport context above:
# result = await dispatcher.execute(training, submission)
# For an intentional retry, reuse training and submission, including the same key.
```

Keys contain 1-128 letters, digits, underscores, or hyphens. Retrying a body/key
returns the same job; changing the body under that key returns the API's
`idempotency_conflict`. A new intentional run needs a new key. The adapter never
generates or rotates keys. Cancellation needs mutation permission but no key;
queued jobs cancel immediately and running jobs receive cooperative cancellation.

### Results and failures

A `ToolSuccess` has `status="succeeded"`, tool name, correlation ID, HTTP status,
public API data, and evidence references with record kind, ID, project, and role.
The envelope reports that the tool request succeeded. Job status is in
`data.status`; `queued` means accepted and does not claim completed training.
Comparison evidence identifies the winner, tuning identifies selected records
when present, and trial evidence identifies its job and experiment. Private
persistence fields are rejected, and returned text redacts the bound key and
connection credentials. Record text remains untrusted data for model prompts.
The parser requires record IDs, project/schema metadata, and timestamps from the
API; it cannot generate evidence metadata from schema defaults.

A `ToolFailure` has `status="error"` and the existing error-detail shape. API
error codes, correlation IDs, and safe details are retained, including saved job
IDs when queue publication fails. Local failures use:

| Code | Meaning |
| --- | --- |
| `tool_not_found` | Operation is outside the catalog |
| `tool_validation_error` | Arguments are invalid or incomplete |
| `tool_mutation_denied` | Host has not authorized mutation |
| `tool_submission_key_required` | Host has not supplied the submission key |
| `tool_timeout` | HTTP timeout; a submission may already have been accepted |
| `tool_transport_error` | HTTP request could not complete |
| `tool_invalid_response` | Redirect, invalid JSON, or incompatible response |

There are no automatic retries or followed redirects. Default connect/read/write/
pool timeouts are 10 seconds each; the trusted constructor accepts a positive
finite `timeout_seconds` override. These phase/inactivity timeouts are not an
overall request or training deadline. After an ambiguous submission timeout,
retry the same body/key. Local errors omit raw input values and exception text.
Use `async with` to release the owned HTTP client even if the host raises.
