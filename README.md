# ML Pipeline Pro

ML Pipeline Pro is a machine learning class project for model management,
automated tuning, monitoring, conversational pipeline guidance, and AI-generated
Python integration snippets. It currently provides a local REST API and CPU
workers for reproducible classification experiments and bounded tuning. The
[course requirements](docs/course-requirements.md) define the remaining deliverable.

**Source audit, October 8, 2026:** Version `0.1.0` has completed the initial scope of milestones 1-3: the foundation, experiment tracking, and serial Optuna tuning. Register datasets/models, train or tune through Celery, inspect results, cancel searches, download verified artifacts, and explicitly register model versions. The broader MVP remains in development. The audit's tuning recovery ownership bugs and controlled process-loss/outage validation are addressed; concurrent-load and network-partition evidence remain before expanding worker concurrency.

Read the [project audit and development status](docs/project-status.md) for verified capabilities, open findings, and immediate priorities. [PLAN.md](PLAN.md) defines the remaining milestones and acceptance criteria.

Development follows the [AI-assisted engineering method](docs/development-methodology.md): clarify and challenge ideas, commit design plans for human review, then implement with continuous verification. [AGENTS.md](AGENTS.md) carries the shared rules and checks; [project memory](docs/memory/README.md) preserves evidence-linked findings.

Follow the [classification walkthrough](docs/workflows.md#classification-experiment-walkthrough) for experiment requests, or the [tuning walkthrough](docs/workflows.md#bounded-classification-tuning) for a five-trial search within a five-minute budget. Both include demos that run without services. The next feature milestone is conversational access to these verified APIs.

The [conversation tool guide](docs/workflows.md#conversation-tool-layer) covers the first milestone
4 slice: 13 provider-independent tools for reads, comparison, bounded submission,
and tuning cancellation. Run `uv run --locked --extra training python examples/tools_local.py`
for a service-free contract demo. Person A's initial conversation foundation adds
locked LangChain dependencies, strict conversation schemas, the model interface,
and validated chat settings. The next A1 slice supplies a tested local inference
adapter with native tool proposals and bounded requests. A durable turn/proposal
store now supplies fenced reservation/completion and replay. Chat routes,
host orchestration, action decisions/dispatch, installed-artifact token verification, and real-model
evaluation remain outstanding under
the [approved design](docs/plans/2026-10-06-conversation-workflows-plan.md).
See [conversation development](docs/conversation-development.md) for this slice's
boundaries, configuration, and next steps.

## Development setup

### Run the whole local stack

Install Docker with Compose 2.24 or later, then run from the repository root:

```powershell
docker compose up --build --wait --wait-timeout 300
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/ready
```

Open [the API documentation](http://127.0.0.1:8000/docs). The current endpoints are:

| Endpoint | Meaning |
| --- | --- |
| `GET /api/v1/health/live` | Process is running; does not contact dependencies |
| `GET /api/v1/health/ready` | MongoDB and Redis both respond within the configured timeout |
| `POST /api/v1/datasets` | Validate a local CSV and register its content hash and split metadata |
| `GET /api/v1/datasets` and `GET /api/v1/datasets/{id}` | List or retrieve datasets within a project |
| `POST /api/v1/models` | Register a PyTorch classification model |
| `GET /api/v1/models` and `GET /api/v1/models/{id}` | List or retrieve models within a project |
| `POST /api/v1/experiments` | Queue a bounded training job; requires `Idempotency-Key` |
| `GET /api/v1/experiments` and `GET /api/v1/experiments/{id}` | Filter experiments or retrieve status, metrics, and artifacts |
| `GET /api/v1/experiments/compare` | Compare completed experiments using validation metrics |
| `GET /api/v1/experiments/{id}/artifacts/{name}` | Download a hash-verified checkpoint or manifest |
| `POST /api/v1/models/{id}/versions` | Register a model version from a completed experiment |
| `GET /api/v1/models/{id}/versions` and `GET /api/v1/models/{id}/versions/{version_id}` | Retrieve registered model versions |
| `POST /api/v1/tuning-jobs` | Queue a bounded TPE search; requires `Idempotency-Key` |
| `GET /api/v1/tuning-jobs` and `GET /api/v1/tuning-jobs/{id}` | Retrieve tuning status, budgets, and the selected configuration |
| `GET /api/v1/tuning-jobs/{id}/trials` | Inspect trial parameters, metrics, durations, and failures |
| `POST /api/v1/tuning-jobs/{id}/cancel` | Cancel queued tuning or cooperatively stop an active trial |

Readiness returns `503` with each dependency's status when either service is unavailable. Responses include `X-Correlation-ID`; an optional valid caller ID is preserved in the response and request logs. Errors contain `error.code`, `error.message`, and `error.correlation_id`.

Readiness checks MongoDB/Redis connectivity. Experiment status and heartbeat timestamps show worker progress separately.

Compose runs the API, a training worker, a recovery scheduler, MongoDB, and Redis. It publishes ports 8000, 27017, and 6379 on localhost and retains metadata, Redis data, and artifacts in named volumes. The worker has one CPU, 1 GiB of memory, and one concurrent job. Compose explicitly sets `MLPP_ENVIRONMENT=development` and container connection/storage paths; an `.env` environment value does not override these settings. Metadata endpoints require `X-Project-ID` and enforce `X-API-Key` when project keys are configured. Shared deployment still needs the controls listed in the [audit](docs/project-status.md#deployment-and-operational-gaps). Stop the stack with `docker compose down`; its named volumes remain available for the next startup.

Tuning requires MongoDB transactions. Compose initializes a single-node `mlpp` replica set and waits for a writable primary. When upgrading an existing local stack, run `docker compose up --build --wait --wait-timeout 300`; the existing MongoDB volume is retained. Host connections to this container must use `mongodb://127.0.0.1:27017/?directConnection=true`, including an existing `.env`, because the replica set advertises its container hostname. External MongoDB deployments must support transactions through a replica set or sharded cluster; standalone MongoDB can still serve ordinary experiments but cannot execute tuning.

The checked-in CSV is included in the image. Custom data must be mounted at the same relative path under the dataset root for the API and worker. Registration records a hash and reference; it does not upload or copy the source file.

### Develop the API on your host

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

Configuration uses the `MLPP_` prefix. `.env.example` lists connection URLs, dataset/artifact directories, data limits, project keys, worker recovery limits, and the [conversation settings](docs/conversation-development.md#configuration). Environment variables override `.env`. Credentials belong in `.env` or the environment, outside source control. Connection URLs are treated as secrets; configured passwords and project keys are redacted from application and client logs.

### Run checks

Follow [verification](docs/verification.md) for the fast gate, ordinary integration
with both opt-in flags, isolated recovery, and historical repeat commands.
Keep `--extra training` on commands that need PyTorch/Optuna. Test counts and
coverage are recorded by revision in [project status](docs/project-status.md).

### Source layout

```text
src/ml_pipeline_pro/
  main.py           # Application factory and versioned health endpoints
  config.py         # Validated environment configuration
  connections.py    # Async client lifecycle and dependency checks
  errors.py         # Consistent API errors
  logging.py        # JSON request logs and credential redaction
  repositories.py   # Record schema and project-scoped repository contract
  ownership.py      # Transactional parent fences for tuning child writes
  schemas.py        # Dataset, model, experiment, and model version schemas
  api.py            # Metadata, experiment, comparison, and artifact endpoints
  access.py         # Project selection and optional API key enforcement
  datasets.py       # Bounded CSV validation and explicit splits
  tracking.py       # Owned repositories and MongoDB indexes
  jobs.py           # Atomic worker claims, heartbeats, and completion
  queue.py          # Celery configuration and Redis dispatch
  worker.py         # Training and recovery tasks
  execution.py      # Job execution and terminal status reporting
  training.py       # Deterministic CPU PyTorch adapter
  artifacts.py      # Artifact writes, hashing, and download verification
  tuning_schemas.py # Search spaces, budgets, and job/trial contracts
  tuning_store.py   # Tuning-owned collections, leases, and reservations
  tuning_api.py     # Tuning submission, progress, and cancellation
  tuning_sampler.py # Seeded TPE suggestions from durable history
  tuning_execution.py # Serial search and final holdout evaluation
  training_control.py # Deadlines, cancellation, and ownership checks
  conversation_schemas.py # Strict chat/action/fact contracts; no routes or storage yet
  conversation_model.py # Injected model interface and native tool descriptions
  conversation_ollama.py # Local LangChain adapter; artifact-specific token counter required
  conversation_store.py # Transactional turn claims/replay and immutable saved proposals
tests/
  integration/      # Opt-in tests against real MongoDB and Redis
compose.yaml        # API and local dependencies
.github/workflows/  # CI checks, ordinary integration, and isolated recovery
```

## Documentation roadmap

| Document | Owns |
| --- | --- |
| [Workflow guide](docs/workflows.md) | Classification, bounded tuning, and typed tool tutorials |
| [Conversation development](docs/conversation-development.md) | Person A's foundation, configuration, and outstanding A1 implementation |
| [Verification](docs/verification.md) | Test setup, recovery boundaries, historical ten-iteration report |
| [Project status](docs/project-status.md) | Implemented capabilities, limitations, audit findings, dated execution evidence |
| [Course requirements](docs/course-requirements.md) | Supplied acceptance checklist and evidence needed to close each requirement |
| [PLAN.md](PLAN.md) | Remaining milestones and measurement criteria |
| [Development method](docs/development-methodology.md) | Design/review process; AGENTS.md owns standing repository contracts |
| [Project memory](docs/memory/README.md) | Short technical findings with evidence |
| [Design plans](docs/plans/template.md) | Change-specific contracts, human approval, and implementation outcomes |

Required local-model, monitoring, AI snippet, separate-service, and Kubernetes/CI/CD
tutorials remain outstanding with those features. Historical test counts and
unverified improvement targets are not current completion claims.
