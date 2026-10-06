# Classification experiment walkthrough

Start the stack with `docker compose up --build --wait --wait-timeout 300`.
Docker Compose 2.24 or later is required. Open `http://127.0.0.1:8000/docs` to
inspect the API. Dataset and model endpoints require an `X-Project-ID` header.

The checked-in `examples/data/classification.csv` is synthetic. Its 120 rows are
explicitly split into 80 training, 20 validation, and 20 test examples. Each row
has two numeric features, an integer target (`0` or `1`), and a split name.
Regenerate the same file with `python examples/make_dataset.py`.

## Register the inputs

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
relative path to the API and eventual training worker.

Dataset versions are unique within a project by `(name, version)`. Models are
unique within a project by name. Repeating registration returns `409`; retrieve
existing records with `GET /datasets` or `GET /models`, or use a new version/name.
Lists accept `limit` (1–100) and `offset` (nonnegative).

## Project access

Development permits project selection without a key when no keys are configured.
To enforce keys, set `MLPP_PROJECT_API_KEYS` in `.env` to a JSON object mapping
project IDs to your own random keys (at least 16 characters). Add the matching
`X-API-Key` header to each request. Configuring any keys restricts access to the
listed projects. Production configuration requires keys; shared deployment still
needs TLS and a complete identity/authorization design.

MongoDB indexes enforce uniqueness and support project-scoped lists. Indexes are
created lazily on the first metadata request, so the API's liveness endpoint
remains available when MongoDB is offline. Storage outages return `503`.

## Submit a training experiment

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
```

Submission returns `202`. Use a new idempotency key for each intentional run;
retry the same body/key after a connection error to avoid creating another
experiment. Reusing a key with a different configuration returns `409`.

The lifecycle is `queued → running → succeeded` or `failed`. A Redis outage during
dispatch returns `503` with the persisted experiment ID. The scheduler retries
undispatched jobs and queued jobs without progress after 60 seconds. Workers
atomically claim a job and renew a 30-second ownership lease. Expired leases are
recovered; repeated worker losses stop after three attempts by default. A stale
worker cannot replace results recorded by its replacement.

The worker rechecks the dataset hash before training. Preprocessing statistics
come only from training rows. It trains a small CPU PyTorch MLP and selects the
first checkpoint with the highest validation macro F1. Test metrics are computed
after that selection. Failure responses include an error summary; successful
responses include validation/test accuracy and macro F1, the selected epoch,
dependency versions, and artifact hashes.

Training has a cooperative runtime budget checked between batches, plus a Celery
hard task limit of 630 seconds. The local worker container is limited to one CPU,
1 GiB of memory, and one concurrent job. Cancellation and tuning are later work.

## Download artifacts and register a version

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
information. The manifest records the dataset snapshot, configuration, selection
rule, metrics, and dependency versions. Downloads and model version registration
verify the stored hash and size. Version registration is an explicit API action
and requires a successful experiment belonging to that model.

For a second run, create a new idempotency key. Compare the completed runs with:

```powershell
$comparisonUri = "$base/experiments/compare?experiment_id=$($experiment.id)&experiment_id=SECOND_EXPERIMENT_ID&metric=validation_f1"
Invoke-RestMethod -Uri $comparisonUri -Headers $headers
```

Comparison requires the same dataset version and selects by validation F1 or
validation accuracy. `GET /experiments` accepts `status`, `model_id`, `limit`, and
`offset` filters. Test metrics cannot be the comparison selection objective.

## Try training without Docker

The actual adapter can run locally without metadata services or a queue:

```powershell
uv sync --locked --extra training
uv run --locked --extra training python examples/train_local.py
```

This prints metrics and saves checkpoint/manifest files under `artifacts/`.
It does not register records in MongoDB. The initial Windows workspace already
has the training dependencies installed, so it can also run:

```powershell
.\.venv\Scripts\python.exe examples\train_local.py
```

Unit tests verify that repeated runs on the same environment and input produce
identical metrics and checkpoint bytes. Reproducibility across different PyTorch
versions, operating systems, or hardware requires separately measured tolerances;
see [PyTorch's reproducibility guidance](https://docs.pytorch.org/docs/stable/notes/randomness.html).

## Validate the full stack

With the full Compose stack running:

```powershell
$env:MLPP_RUN_INTEGRATION = '1'
$env:MLPP_RUN_WORKER_INTEGRATION = '1'
uv run --locked --extra training pytest -m integration
Remove-Item Env:MLPP_RUN_INTEGRATION
Remove-Item Env:MLPP_RUN_WORKER_INTEGRATION
```

These tests check real indexes, atomic claims, ownership recovery, Redis dispatch,
training, artifact downloads, and model version registration. The complete suite
passed [GitHub CI for commit 56f4a08](https://github.com/JacobHermsmeyer21/ML-Pipeline-Pro/actions/runs/37529542384).
Docker Engine remains unavailable on the initial Windows machine; its 88 local
unit/training tests verify the real training adapter and API/worker contracts using
deterministic repository substitutes.
