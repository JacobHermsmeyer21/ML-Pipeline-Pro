# Setup guide

Run commands from the repository root. For a first start, use
[the README](../../README.md#development-setup).

## Run the whole local stack

Install Docker with Compose 2.24 or later, then run from the repository root:

```powershell
docker compose up --build --wait --wait-timeout 300
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/ready
```

Open [interactive API docs](http://127.0.0.1:8000/docs);
see the [endpoint reference](../reference/api.md).

Compose runs the API, a training worker, a recovery scheduler, MongoDB, and Redis. It publishes ports 8000, 27017, and 6379 on localhost and retains metadata, Redis data, and artifacts in named volumes. The worker has one CPU, 1 GiB of memory, and one concurrent job. Compose explicitly sets `MLPP_ENVIRONMENT=development` and container connection/storage paths; an `.env` environment value does not override these settings. Metadata endpoints require `X-Project-ID` and enforce `X-API-Key` when project keys are configured. Shared deployment still needs the controls listed in the [audit](../project/project-status.md#deployment-and-operational-gaps). Stop the stack with `docker compose down`; its named volumes remain available for the next startup.

Project lifecycle admission, permanent deletion, conversations and tuning use
MongoDB transactions. Compose initializes a single-node `mlpp` replica set and
waits for a writable primary. When upgrading an existing local stack, run
`docker compose up --build --wait --wait-timeout 300`; the MongoDB volume is retained.
Host connections must use `mongodb://127.0.0.1:27017/?directConnection=true`,
including an existing `.env`, because the replica set advertises its container
hostname. External deployments need a replica set or sharded cluster; standalone
MongoDB does not support the current transactional mutation workflow.

The checked-in CSV is included in the image. Direct `POST /api/v1/datasets`
registration records a hash and reference without copying the source. Custom
files registered this way must be mounted at the same relative path under the
dataset root for the API and worker and remain unchanged.

## Browser workspace and managed uploads

The packaged dashboard is available at `http://127.0.0.1:8000/dashboard/` on the
compatibility API and model API. The base stack disables uploads and chat and
does not start Grafana. Follow the [dashboard startup](dashboard.md#start-on-this-desktop)
for the domain, monitoring, local-AI and dashboard overlays; chat also needs the
explicit installed model/tokenizer from [local model setup](local-model-setup.md).

`compose.dashboard.yaml` enables `MLPP_DATASET_UPLOAD_ENABLED` in the model API
and shares a durable uploads volume with a read-only worker mount. The setting
gates numeric upload, raw CSV preview/preparation and saved-column editing. Raw
import saves the original CSV, canonical numeric CSV and reviewed training-fitted
recipe. Column edits project a new immutable version without changing existing
rows/splits/transforms. See the [dataset API contracts](../reference/api.md#raw-csv-preparation).

Upgrade all domain APIs, worker and scheduler together after active work drains.
Their shared artifact root holds stable native publication/attempt locks used by
permanent deletion; the worker's uploads mount stays read-only. Preserve both
artifact and uploads volumes when stopping or upgrading. Explicit
[permanent deletion](dashboard.md#delete-a-dataset-or-model) removes only its
reviewed cascade and exclusively owned managed files; shared source files,
operator originals, conversations/drafts and historical Prometheus samples remain.

## Develop the API on your host

Install [uv](https://docs.astral.sh/uv/getting-started/installation/). The project defaults to Python 3.11; uv can provision it if needed. Versions 3.11 through 3.14 are allowed by the manifest, while CI tests 3.11/3.13 on Linux and local validation uses Windows/Python 3.11. From the repository root:

```powershell
uv sync --locked
Copy-Item .env.example .env
docker compose up --wait mongo redis
uv run --locked uvicorn ml_pipeline_pro.main:create_app --factory --reload --no-access-log
```

For queued experiments with the host API, also start the container worker and scheduler with `docker compose up --build --wait mongo redis worker scheduler`. Both use the same MongoDB/Redis and checked-in dataset. To download artifacts through the host API, replace the named artifact volume with a shared host directory mounted at `/app/artifacts` in the containers and set the host's `MLPP_ARTIFACT_ROOT` to that directory. Running the whole stack in Compose already shares artifact storage correctly.

The API runs at `http://127.0.0.1:8000`. Select `.venv/Scripts/python.exe` as the Python interpreter in your Windows editor. On macOS or Linux, use `cp .env.example .env` and `.venv/bin/python`.

If Docker or the dependency services are not installed yet, the API still starts: liveness and `/docs` work, and readiness returns `503`. The foundation's unit tests also run without MongoDB, Redis, or language model credentials.

Configuration uses the `MLPP_` prefix. `.env.example` lists connection URLs, dataset/artifact directories, data limits, project keys, worker recovery limits, and the [conversation settings](conversation-development.md#configuration). Environment variables override `.env`. Credentials belong in `.env` or the environment, outside source control. Connection URLs are treated as secrets; configured passwords and project keys are redacted from application and client logs.

## Verify the setup

Follow [verification](verification.md) for fast checks and the opt-in
real-service/recovery gates. Keep `--extra training` for PyTorch/Optuna commands.
