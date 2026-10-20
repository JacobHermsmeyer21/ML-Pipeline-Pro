# ML Pipeline Pro

For the October 20 demo, see the [October 18 audit](docs/project/2026-10-18-repo-audit.md).
The minimal course features are implemented. Normal bounded AI acceptance on the
chosen CPU laptop remains open; the passing full bounded walkthrough used the RX 9070 workstation.
The [five-minute laptop rerun](docs/evidence/2026-10-19-laptop-five-minute/README.md)
passes its first inspection, then fails during a gateway liveness restart. Full
laptop acceptance remains open; more reply time is not the next proposed fix.
The later [standalone laptop gates](docs/evidence/2026-10-19-laptop-awake-gates/README.md)
pass all ten dialogue and seven snippet scenarios with the five-minute profile.
The later [unbounded laptop diagnostic](docs/evidence/2026-10-19-laptop-unbounded/README.md)
passes two complete workflows in 789.906 and 641.016 seconds with direct AI API
origins and application probes removed. The slowest replies, 276.594 and 273.719
seconds, exceed the old 270-second turn window. Normal settings are restored;
these observations establish neither finite-profile nor full gateway acceptance.

A machine learning class project for reproducible classification experiments,
bounded tuning, and conversational pipeline guidance. The backend uses FastAPI,
MongoDB, Redis/Celery, PyTorch, and Optuna. Conversation development uses
LangChain with a locally served pre-trained model.

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
