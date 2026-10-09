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

Tuning requires MongoDB transactions. Compose initializes a single-node `mlpp` replica set and waits for a writable primary. When upgrading an existing local stack, run `docker compose up --build --wait --wait-timeout 300`; the existing MongoDB volume is retained. Host connections to this container must use `mongodb://127.0.0.1:27017/?directConnection=true`, including an existing `.env`, because the replica set advertises its container hostname. External MongoDB deployments must support transactions through a replica set or sharded cluster; standalone MongoDB can still serve ordinary experiments but cannot execute tuning.

The checked-in CSV is included in the image. Custom data must be mounted at the same relative path under the dataset root for the API and worker. Registration records a hash and reference; it does not upload or copy the source file.

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
