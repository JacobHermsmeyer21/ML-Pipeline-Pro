# ML Pipeline Pro

A machine learning class project for reproducible classification experiments,
bounded tuning, and conversational pipeline guidance. The backend uses FastAPI,
MongoDB, Redis/Celery, PyTorch, and Optuna. Conversation development uses
LangChain with a locally served pre-trained model.

You can register datasets and models, queue training or tuning, compare validation
results, download verified artifacts, and register model versions. Training runs
serially on CPU. Conversation tools, a local model adapter, durable history,
grounded reads, authenticated routes, and confirmed actions are implemented;
the opt-in [guided 7B demo](docs/guides/guided-midterm-demo.md) passes its original
live conversation/snippet gates; human quality and full onboarding remain open.
Supported Python snippet generation now saves restricted, validated drafts for
human review. See the [snippet guide](docs/guides/snippet-generation.md).

The full course project is **in development**. Separate model-management, tuning,
and monitoring services, live monitoring, final human AI review, and
Kubernetes/deployment CI/CD remain outstanding. See the
[roadmap](PLAN.md) and [course checklist](docs/project/course-requirements.md).

## Development setup

Install Docker with Compose 2.24 or later. From the repository root:

```powershell
docker compose up --build --wait --wait-timeout 300
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/ready
```

Open [interactive API docs](http://127.0.0.1:8000/docs). The stack starts the API,
worker, recovery scheduler, MongoDB replica set, and Redis. Metadata requests
require `X-Project-ID` and, when configured, `X-API-Key`. Stop with
`docker compose down`; named volumes retain data and artifacts.

Follow the [setup guide](docs/guides/setup.md) for host development, configuration,
custom data, and shared artifact storage. Chat defaults to disabled; enabling it
still requires an installed model and verified artifact-specific token counter.
See [conversation development](docs/guides/conversation-development.md).

## Try a workflow

For the independently runnable model/tuning APIs, follow
[domain service setup](docs/guides/domain-services.md). Monitoring and Kubernetes
are still outstanding.

- [Classification](docs/guides/workflows.md#classification-experiment-walkthrough): register inputs, train, compare, and register a version.
- [Bounded tuning](docs/guides/workflows.md#bounded-classification-tuning): search within trial/runtime limits, inspect results, and cancel.
- [Conversation tools](docs/guides/workflows.md#conversation-tool-layer): use typed tools over the existing API.
- [Generated Python drafts](docs/guides/snippet-generation.md): request, inspect, and review integration snippets through chat.
- [API reference](docs/reference/api.md): endpoints, access headers, errors, and idempotency.

The walkthroughs include demos that run without services.

## Run checks

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```powershell
uv sync --locked --extra training
uv run --locked --extra training ruff check .
uv run --locked --extra training ruff format --check .
uv run --locked --extra training pytest -m "not integration" --cov
uv pip check
```

The [verification guide](docs/guides/verification.md) covers ordinary integration
and isolated recovery. Both use explicit opt-in flags; missing services or skipped
selected cases are verification gaps. Historical results live in
[project status](docs/project/project-status.md).

## Documentation roadmap

Use the [documentation index](docs/README.md) to find guides, references, project
records, reviewed plans, technical memory, and saved evidence.
[PLAN.md](PLAN.md) tracks milestones; [AGENTS.md](AGENTS.md) defines repository
rules. Substantive designs follow the
[development method](docs/project/development-methodology.md) and require human
review before implementation.

Application code is in [`src/ml_pipeline_pro`](src/ml_pipeline_pro/), tests in
[`tests`](tests/), and runnable examples in [`examples`](examples/).
