# Classification experiment walkthrough

Start the stack with `docker compose up --build --wait --wait-timeout 180`.
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

Queued training, experiment status, and model version registration are the next
parts of this walkthrough.
