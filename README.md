# ML Pipeline Pro

A course project by **Team MJN** for reproducible classification experiments,
bounded hyperparameter tuning, monitoring, and conversational pipeline guidance.

## Demo

![Animated ML Pipeline Pro dashboard walkthrough](demo.gif)

The recording shows the locally hosted browser dashboard. For a live local
walkthrough, follow the [dashboard startup guide](docs/guides/dashboard.md#start-on-this-desktop)
and open `http://127.0.0.1:8000/dashboard/`. The base Compose stack below starts
with chat and uploads disabled; the guide explains the additional services and
configuration. Public URL verification is outside this submission update at
Jacob's request.

## Team and contributions

Contributions below are grounded in published Git history through `baa8189`
(October 20, 2026). Commit authorship records submitted work; it does not establish
how much was written manually versus with AI assistance. No contributions outside
Git were reported for this audit.

| Team member | Verified workflow contributions | Status in the submitted application |
| --- | --- | --- |
| **Jacob Hermsmeyer** ([JacobHermsmeyer21](https://github.com/JacobHermsmeyer21)) | Backend/services, dataset and model registration, serial PyTorch training, Optuna tuning and recovery, LangChain tools and Python drafts, monitoring, Docker/Kubernetes/CI, original dashboard, CSV preparation/column versions/deletion, deployment diagnostics, OpenAI integration, logistic regression, short IDs and classification metrics. Representative commits: `0e37e6e`, `5c5f429`, `c31898c`, `a44452e`. | Maintained implementation and subsequent feature work are present in the current tree. |
| **Mingma Lama** ([lama9811](https://github.com/lama9811); also commits as Mingma) | Astro/React dashboard redesign, mocked-API browser regression tests and build checks, CSP changes, Claude backend and output-budget correction, public-deployment plan, presentation slides/PDF, and an earlier submission README. Representative commits: `20bef4f`, `4f9b4a3`, `c0d3cb7`, `e0ac45c`, `c012423`, `1d89614`. | This work was contributed and merged, then removed from the application tree by restoration commit `e7c8e76`. It remains credited in history; Astro, Claude, and those slides are absent from the current submission. |
| **Nasif Ajilore** | No contribution is recorded under this name in the inspected repository history, and no work outside Git has been reported. | No verified contribution to report. An unidentified Git alias or unreported work cannot be ruled out. |

## Git workflow

The history contains repeated commits from October 6–20, 2026, feature branches,
and merged pull requests, including [PR #1](https://github.com/JacobHermsmeyer21/ML-Pipeline-Pro/pull/1)
and [PR #2](https://github.com/JacobHermsmeyer21/ML-Pipeline-Pro/pull/2).
At audit revision `baa8189`, `git shortlog -sne HEAD` records 131 commits by
Jacob's identity and 20 by Mingma's two identities (18 + 2, including merges).
These counts describe reachable history, including work later removed; they are
not measures of effort. **Active Git collaboration by all three members is not
demonstrated:** no third contributor identity appears. This requirement remains
unmet on the available evidence.

Substantive changes use written plans and human review; completed major changes
are checked, committed and pushed. See [repository workflow](AGENTS.md) and the
[development method](docs/project/development-methodology.md).

## Submission checklist

| Professor's requirement | Evidence or remaining limitation |
| --- | --- |
| Embedded animated walkthrough | Root `demo.gif` is embedded above; decoded successfully as 2,002 frames at 1922 × 1042. A recording does not establish current service availability. |
| Operational public app link | Not assessed in this update, at Jacob's request. Local startup is documented above. |
| Exact README template | Jacob confirmed that the professor did not supply a template. This README covers the supplied checklist; exact-template compliance cannot be assessed. |
| Three named members and specific contributions | All three are listed above, with historical/removed work and absent evidence stated explicitly. |
| Regular commits and collaboration by every member | Regular history exists for Jacob and Mingma; participation by Nasif is not evidenced. |
| Installation, dependencies, datasets and evaluation metrics | Documented below and in the linked setup, API and evidence guides. |

## Overview and features

Datasets, experiments and conversations support easy-to-type references such as
`d1`, `e1` and `c1` in the dashboard, agent chat and API. Full IDs keep working. See
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

Dependencies are declared in [pyproject.toml](pyproject.toml) and resolved in
[uv.lock](uv.lock). Python 3.11–3.14 is supported; CI checks Python 3.11 and 3.13.
FastAPI/Uvicorn serve the APIs; PyMongo connects to a MongoDB replica set;
Redis/Celery queue serial work; PyTorch, NumPy, scikit-learn and Optuna provide
classification and Bayesian tuning. LangChain integrates the hosted OpenAI or
local Ollama agent. Prometheus/Grafana provide monitoring. The current dashboard
is packaged HTML/CSS/JavaScript and needs no Node/Astro build.

For Python development, install uv, then run:

```powershell
uv sync --locked --extra training
# Create configuration only if it does not already exist.
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
uv run --locked --extra training python examples/train_local.py
```

The last command runs the synthetic classification example without external
services. Full API workflows need MongoDB/Redis; chat additionally needs its
configured provider. Settings and secret handling are documented in
[.env.example](.env.example) and the [setup guide](docs/guides/setup.md).

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
requires configured OpenAI credentials or an installed local model with its
verified artifact-specific token counter. See the
[OpenAI guide](docs/guides/openai-agent.md) or
[local conversation development](docs/guides/conversation-development.md).

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

## Datasets

The checked-in [classification CSV](examples/data/classification.csv) is synthetic
educational data generated by [make_dataset.py](examples/make_dataset.py) with
seed 42. It has 120 rows, two numeric features, balanced binary labels, and an
explicit `split` column: 80 training, 20 validation and 20 test rows. Regenerate it
with `uv run --locked python examples/make_dataset.py`. Its deliberately separated
classes make it a pipeline smoke test, not a representative performance benchmark.

Custom UTF-8 classification CSVs can be imported through the dashboard after
enabling managed uploads. Review the target, feature columns, categorical
encodings and splits before saving. Raw preparation defaults to stratified
70/15/15 splits with seed 42, subject to integer allocation and sufficient rows
per class; an existing split column can preserve membership. Default limits are
10,000,000 bytes and 100,000 rows. Preprocessing and normalization fit training
rows only; immutable saved versions preserve input hashes, recipes and splits.
See [raw preparation contracts](docs/reference/api.md#raw-csv-preparation).

The demo recording also shows an Iris CSV imported locally. That CSV's exact
source and license have not been supplied for this audit, and it is not the
checked-in synthetic example. A separate historical
[Drug200 run](docs/evidence/2026-10-19-drug200-demo/README.md) documents its input
hash, preparation and saved results; its original CSV is not distributed here.
Verify provenance and permission before redistributing external datasets.

## Models and evaluation metrics

The supported classifiers are a PyTorch MLP (linear → ReLU → linear) and logistic
regression (a linear classifier). Both use Adam and cross-entropy; the classifier
is separate from the pre-trained language model used for chat. Training is serial
on CPU. See [algorithm comparison](docs/guides/dashboard.md#compare-algorithms).

| Metric | Definition and use |
| --- | --- |
| Accuracy | Correct predictions divided by evaluated rows. |
| Precision | Per-class `TP / (TP + FP)`, averaged equally across all dataset classes. |
| Recall | Per-class `TP / (TP + FN)`, averaged equally across all dataset classes. |
| F1 | Per-class `2TP / (2TP + FP + FN)`, averaged equally across all dataset classes. |

Undefined per-class ratios contribute zero. Training selects the checkpoint using
validation F1 by default; bounded MLP tuning can select validation F1 or accuracy.
Test metrics are evaluated after selection, never used to pick the winner. The
dashboard separates validation values from held-out test values. Saved artifacts
are checked against recorded SHA-256 and size. Monitoring separately reports
observed inference latency, labeled accuracy, errors and declared artificial
delays; AI explanations are not measurements.

Retained results include the historical Drug200 run above: validation F1/accuracy
1.0 and held-out test macro F1 0.9586666667 / accuracy 0.9555555582 on its documented
117/38/45 split. These describe one small split, not generalization guarantees or
the Iris recording. The later
[classification-metrics acceptance record](docs/evidence/2026-10-20-dashboard-metrics/README.md)
checks all four metrics against independently reconstructed predictions for real
binary/multiclass runs. No new model evaluation was run for this README update.

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
