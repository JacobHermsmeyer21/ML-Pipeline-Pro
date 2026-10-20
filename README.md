# ML Pipeline Pro

Experiments and conversations support easy-to-type references such as `e1` and
`c1` in the dashboard, agent chat and API. Full IDs keep working. See
[short IDs and the existing-data upgrade](docs/guides/short-record-ids.md).

Models support `mlp` (the default) and `logistic_regression`. Create a linear model
with `POST /api/v1/models` and
`{"name":"linear_baseline","architecture":"logistic_regression"}`. Submit
`POST /api/v1/experiments` with your `dataset_id`, `model_id`, an `Idempotency-Key`
header, and `"config":{"algorithm":"logistic_regression","epochs":30,"l2_strength":0}`.
Common config fields/defaults are seed 42, batch size 16, learning rate 0.01 and
runtime limit 60 seconds. Logistic configs exclude `hidden_units`; MLP payloads
retain their existing defaults. A config/model mismatch returns scoped
`409 model_config_mismatch`. Architecture is immutable after creation.

Logistic regression is a fresh PyTorch linear classifier trained with minibatch
Adam, cross entropy and optional `0.5 * l2_strength * sum(weight ** 2)` (bias is
unpenalized). It supports binary and multiclass classification; convergence and
superiority over MLP are not guaranteed. Scaling fits training rows and checkpoints
are selected by validation metrics. Logistic tuning and AI mutation proposals are
deferred (`409 unsupported_model_algorithm`); manual training, read/compare tools,
artifact downloads and version registration work with both algorithms. See the
[dashboard comparison walkthrough](docs/guides/dashboard.md#compare-algorithms).

A machine learning class project for reproducible classification experiments,
bounded tuning, and conversational pipeline guidance. The backend uses FastAPI,
MongoDB, Redis/Celery, PyTorch, and Optuna. Conversation development uses
LangChain with OpenAI as the default agent provider and an explicit local Ollama option.

For OpenAI, set `OPENAI_API_KEY` in the ignored `.env` file and enable
`MLPP_CHAT_ENABLED=true`, `MLPP_CHAT_BACKEND=openai`, `MLPP_CHAT_PROTOCOL=native`.
The default hosted model is `gpt-5.4-mini`; prompts and supplied record context are
sent externally. Read the [OpenAI setup and verification guide](docs/guides/openai-agent.md)
for limits, deployment, local compatibility and current acceptance evidence.
The retained local-model results below do not establish OpenAI acceptance.

Current as of October 19, 2026: the local dashboard supports original CSV import,
reviewed categorical encoding/splits, immutable column-subset versions and
permanent dataset/classifier deletion. Independent model, tuning and monitoring
APIs, generated Python drafts, Prometheus/Grafana and Docker/Kubernetes delivery
have retained minimal-course evidence. See [current status](docs/project/project-status.md)
and the [course checklist](docs/project/course-requirements.md) for verification and
remaining review/deployment gaps. Plans and dated audits retain their original scope.

The [October 19 RX 9070 desktop demo](docs/evidence/2026-10-19-desktop-demo/README.md)
passes the full bounded AI walkthrough. On the CPU laptop,
[standalone gates](docs/evidence/2026-10-19-laptop-awake-gates/README.md) pass all ten
dialogue and seven snippet scenarios with the five-minute profile, while the
[bounded Kubernetes walkthrough](docs/evidence/2026-10-19-laptop-gateway-health/README.md)
still fails during a gateway restart. Two later
[unbounded diagnostics](docs/evidence/2026-10-19-laptop-unbounded/README.md) pass
complete workflows in 789.906/641.016 seconds using direct AI origins with
application probes removed. Those diagnostics do not establish finite-profile or
full gateway acceptance; normal settings and probes were restored.

You can register datasets and models, queue training or tuning, compare validation
results, download verified artifacts, and register model versions. Training runs
serially on CPU. Conversation tools, a local model adapter, durable history,
grounded reads, authenticated routes, and confirmed actions are implemented;
the opt-in [guided 7B demo](docs/guides/guided-midterm-demo.md) passes the original
ten dialogue and seven snippet cases. Earlier slow/failed runs remain recorded;
local inference capacity depends on the declared runtime and available resources.
Supported Python snippet generation now saves restricted, validated drafts for
human review. See the [snippet guide](docs/guides/snippet-generation.md).

The approved [midterm walkthrough](docs/guides/midterm-walkthrough.md) now has three
independent domain APIs, guided local AI, generated drafts, measured monitoring
with Prometheus/Grafana, and a local Kubernetes deployment path. Human draft and
monitoring reviews are recorded, and the clean-checkout/full Kubernetes AI walkthroughs
pass. Kubernetes and recovery [successful implementation CI](https://github.com/JacobHermsmeyer21/ML-Pipeline-Pro/actions/runs/38505646188) pass. See the
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

The [local dashboard](docs/guides/dashboard.md) brings CSV upload, model training,
saved experiments, local-agent chat and embedded Grafana panels into one browser
workspace at `http://127.0.0.1:8000/dashboard/`. Use the dashboard Compose overlay
for durable shared uploads and Grafana embedding. Uploads are disabled by default.
The additive `POST /api/v1/datasets/upload` accepts raw `text/csv` with dataset
metadata in query parameters; [the API reference](docs/reference/api.md#dataset-upload)
documents its limits, project scope, replay and failure responses.
For original classification CSVs, `POST /api/v1/datasets/preview` proposes editable
encodings and stratified 70/15/15 splits; `POST /api/v1/datasets/prepare` saves the
exact reviewed recipe. Both accept multipart CSV/JSON and use the same opt-in
upload setting. See [raw CSV preparation](docs/reference/api.md#raw-csv-preparation).

Choose input columns before uploading, or use **Edit columns** on a saved dataset
to drop inputs and **Save as new version**. Existing versions/runs retain their
original data; rows, labels and splits are preserved. The additive
`GET /api/v1/datasets/{id}/columns`, `POST /api/v1/datasets/{id}/columns/preview`
and `POST /api/v1/datasets/{id}/columns` routes use the upload opt-in setting.
See [column editing](docs/reference/api.md#dataset-column-editing).

Use **Delete dataset** or **Manage models** in the dashboard to permanently erase
an item and its related training history/checkpoints after reviewing the exact
scope. Related active jobs block deletion; conversations/drafts and shared or
operator-owned inputs are kept. The authenticated deletion-preview, `DELETE`
dataset/model and operation-status routes are documented in
[permanent deletion](docs/reference/api.md#permanent-dataset-and-model-deletion).

For the independently runnable model/tuning APIs, follow
[domain service setup](docs/guides/domain-services.md). Monitoring and Kubernetes
use the [monitoring](docs/guides/monitoring-demo.md) and
[Kubernetes](docs/guides/kubernetes-demo.md) guides.

- [Classification](docs/guides/workflows.md#classification-experiment-walkthrough): register inputs, train, compare, and register a version.
- [Bounded tuning](docs/guides/workflows.md#bounded-classification-tuning): search within trial/runtime limits, inspect results, and cancel.
- [Conversation tools](docs/guides/workflows.md#conversation-tool-layer): use typed tools over the existing API.
- [Generated Python drafts](docs/guides/snippet-generation.md): request, inspect, and review integration snippets through chat.
- [API reference](docs/reference/api.md): endpoints, access headers, errors, and idempotency.
- [Complete midterm demo](docs/guides/midterm-walkthrough.md): the approved minimal all-nine workflow.

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

The opt-in [five-minute laptop profile](docs/guides/laptop-five-minute.md) allows
240 seconds per model call, 270 seconds per complete turn and a 300-second client
wait. Default call/turn settings remain 20/60 seconds; their allowed finite ceiling
is 300 seconds with model <= turn. Use the matching deployment and client profile;
increasing only a client wait cannot extend the application's budget. Readiness
requires the retained laptop gates and complete demo results, not configuration alone.

In this opt-in profile, `GET /gateway-live` returns `200 {"status":"alive"}`
locally from nginx with the usual correlation header. Kubernetes uses it only for
gateway liveness; readiness and startup still check the upstream API. Validate the
failure boundary with `uv run --locked --extra training python scripts/check_laptop_gateway.py`.
This uses an already installed `nginx:1.28-alpine` image in a disposable test network,
does not pull images or invoke a model, and saves DNS/TCP failure evidence under
`artifacts/laptop-gateway-check/`.

The separately approved `laptop-unbounded-diagnostic` profile measures AI completion
with no model/turn/client waiting cutoff. It requires
`MLPP_CHAT_UNBOUNDED_DIAGNOSTIC=true` and both chat/model timeouts set to `none`,
is rejected in production, and removes application probes only from its rendered
Kubernetes manifest. Use explicit direct model/monitoring API origins for long AI
requests; the gateway remains on the backend path. Saved diagnostic turns have
matching private mode markers and null deadlines; a crashed owner remains running
until investigated. Default/five-minute profiles, existing finite deadlines and
action/job budgets retain their behavior. See the
[diagnostic procedure](docs/guides/laptop-five-minute.md#unbounded-timing-diagnostic).
