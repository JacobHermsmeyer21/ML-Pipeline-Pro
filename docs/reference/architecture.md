# Architecture and contracts

The compatibility backend uses one FastAPI application, Redis/Celery workers and
MongoDB. Model-management/conversation and tuning also have independent factories
and a [domain Compose topology](../guides/domain-services.md) with public routing.
The [monitoring overlay](../guides/monitoring-demo.md) completes the three independent
REST services; [Kubernetes](../guides/kubernetes-demo.md) deploys the same image and
shared stores. See the [roadmap](../../PLAN.md).
The approved [midterm plan](../plans/2026-10-13-midterm-delivery-plan.md) selects
three domain processes sharing code/image/database, thin public routing, one serial
worker, one local-model profile and small live monitoring. This target remains
bounded by the [midterm scope](../project/midterm-scope.md); wider production/drift
work remains deferred.

## Architecture and ownership

| Component | State and responsibilities | Owned records |
| --- | --- | --- |
| Model-management service | Register/upload/prepare datasets, derive column versions, manage classifier definitions/versions, experiments and verified artifacts; own the packaged dashboard and deletion API | Datasets, models, model versions, experiments and deletion operations |
| Tuning module | Implemented: validate bounded serial searches, persist reservations/trials, cancel jobs | Tuning jobs and trials |
| Monitoring service | Immutable project/version observations, capped summaries, Prometheus/Grafana, one threshold and separate LangChain interpretation/checks | Monitoring observations; summaries derived on read |
| Conversation tool library | Implemented: 13 typed HTTP operations, trusted context, budgets/keys, public record evidence | Calls existing APIs; no owned durable records |
| Conversation module | Guided 7B demo verified: bounded local adapter, current facts/history, durable turns/drafts/proposals and exact confirmed dispatch; native failures retained | Conversations, turns, and action records |
| Celery workers | Implemented training, tuning, recovery, and transactional tuning ownership | Write through the domain repository interfaces |

The browser workspace is packaged HTML/CSS/JavaScript served by the compatibility
and model APIs. It uses existing project-scoped HTTP contracts, keeps API keys in
memory, and stores selected project/conversation/pending request identities in tab
session storage. Grafana panels are embedded only for the configured demo project;
training metrics and inference observations remain separate data sources.

The reviewed factories deploy model-management, tuning, and monitoring REST
services independently. A shared repository/image/database is
allowed; three modules in one API process are not the required service topology.
The conversation layer can remain a bounded orchestration entry point. Preserve
`/api/v1` compatibility through reviewed routing and keep domain repositories
responsible for writes. Tuning/tracking records must stay in a MongoDB deployment
supporting their shared ownership transaction; replacing it with independent
HTTP writes would lose the fence. Pass record/correlation IDs between services;
retain Redis for queued work and separate artifact storage.

## Data model and storage

Domain records carry project scope, timestamps and schema versions; lifecycle
gates and minimal cleanup receipts use their dedicated contracts. Authorization
checks apply to referenced records as well as the initial request.

See the [tracking schemas](../../src/ml_pipeline_pro/schemas.py),
[tuning schemas](../../src/ml_pipeline_pro/tuning_schemas.py),
[conversation schemas](../../src/ml_pipeline_pro/conversation_schemas.py), and
[conversation store](../../src/ml_pipeline_pro/conversation_store.py) for exact
contracts. The [audit inventory](../project/project-status.md#architecture-and-durable-records)
records the historical initial backend scope. Direct dataset registration stores
a URI/hash without copying bytes. Managed uploads instead publish immutable files
under `uploads/<project>/`; raw preparation retains source/canonical CSVs and a
versioned recipe. MongoDB holds references/hashes, not CSV/checkpoint bytes.
Explicit dataset/model erasure is implemented; scheduled retention, general
migrations and coordinated backup/restore remain outstanding.

| Collection | Fields/intent | Indexes/intent |
| --- | --- | --- |
| `datasets` | Identity, canonical CSV hash/URI, feature/target/split metadata; optional preparation and column-selection provenance | Unique project/name/version; scoped pagination; partial unique project/selection-parent/version replay index |
| `models`, `model_versions`, `experiments` | Classifier definitions, evaluated versions, configuration/metrics/artifact references and submission ownership | Scoped identity/pagination, model/version and submission-key indexes |
| `tuning_jobs`, `trials` | Bounded search, original deadlines, reserved configurations/IDs, validation objectives and final evaluation | Scoped submission keys, status/recovery and unique project/job/trial number |
| `project_lifecycle`, `deletions`, `deletion_items`, `deleted_submissions` | Project mutation gate/generation, resumable cleanup journal/minimal receipt and erased submission-key receipts | Project gate identity; scoped operation/key, captured item and erased collection/key digest |
| `monitoring_observations` | Immutable project/sample identity, model version, measured timestamp/latency, labels/outcome, safe fault enum/input hash | Unique `_id`; project/version/observed time and scoped pagination indexes |
| Wider summary/alert state (deferred) | Durable historical aggregates, alert lifecycle and general drift | Outside the approved minimal midterm; current summaries/rule derive from a bounded window |
| `conversations`, `conversation_turns` | Project, revision/turn claims, dialogue, verified record snapshots, correlations | Project/request ID and project/conversation/sequence uniqueness; history lookups |
| `conversation_actions` | Project, immutable arguments/hash, confirmation, submission key, attempt claims/outcomes, evidence | Project/conversation/action lookups |

Continue using explicit request and persistence schemas. The
[conversation plan](../plans/2026-10-06-conversation-workflows-plan.md) specifies
project access and retained dialogue/action evidence, without inventing a user
identity system or treating model proposals as confirmed actions. Define
broader dataset/artifact/summary/log retention before shared use. Current
monitoring uses Prometheus for time series, Grafana for visualization and MongoDB
for immutable observations. Summaries derive from bounded reads; durable historical
aggregates and alert lifecycle remain deferred. Index uniqueness and small-demo
query/index evidence are recorded; larger query/latency benchmarks remain deferred.

## API contracts and remaining additions

Implemented endpoints use `/api/v1`, consistent errors/correlation IDs,
project-scoped access, and list pagination. The [endpoint inventory](api.md#endpoints)
and generated `/docs` describe the current surface. Monitoring routes are implemented
in the independent monitoring service under the
[approved design](../plans/2026-10-13-monitoring-deployment-plan.md).

| Endpoint | State | Behavior |
| --- | --- | --- |
| `POST /api/v1/monitoring/observations` | Implemented | Ingest/replay immutable project-scoped model observations |
| `GET /api/v1/monitoring/model-versions/{version_id}/summary` | Implemented | Return a bounded monitoring summary and evidence |
| `POST /api/v1/monitoring/model-versions/{version_id}/diagnosis` | Implemented | Generate cited local-model advice for human review |
| `GET /api/v1/monitoring/metrics` | Implemented | Export project-scoped Prometheus metrics |

Tuning jobs use `queued`, `running`, `succeeded`, `failed`, `cancel_requested`, and `cancelled`; experiment records also support `cancelled` for tuning children but have no standalone cancellation endpoint. Submission retries are idempotent, leases/heartbeats are persisted, and recovery claims are bounded. Tuning child writes share a transaction with a parent ownership fence; MongoDB replica set/sharded-cluster support is required. Preserve these contracts while strengthening outage/restart coverage. A succeeded tuning job can report `final_evaluation: skipped_budget`; version registration still requires an evaluated experiment.

## Dataset column versions

The model service owns reviewed column-subset creation. An optional typed
`DatasetRecord.selection` records immediate parent hashes/ID, omissions and
request/review digests. A partial unique index on project, selection parent ID
and destination version supports exact replay even after parent removal.
Original datasets need no migration. Parent IDs are provenance, not cascading
ownership. Each child directly references all files needed to train it.

Projection retains canonical row order, targets, split membership and feature
aliases. Raw-prepared children use a self-contained v2 manifest with frozen
retained transforms, supported alongside v1. The existing project publication
lock and lifecycle-generation transaction fence the new writer against deletion;
file work stays owned through cancellation and uncertain inserts retain published
files. Deploy matching services/workers together. See
[the API contract](api.md#dataset-column-editing) and
[the approved plan](../plans/2026-10-19-dataset-column-editing-plan.md).

## Permanent deletion and publication ownership

Dataset/model deletion captures an exact project-scoped dependency preview and
requires its hash plus an idempotency key. Related active jobs block the operation.
The lifecycle transaction writes a shared project gate before admitting new
datasets, jobs, versions or observations; a read-only reference check would not
serialize those writes against deletion. Registration/column publication binds
the original lifecycle generation while holding its native publication lock.

Terminal status or an expired lease does not prove an old worker has stopped
writing files. Each attempt holds a separate native lock through all owned work;
cleanup obtains those locks before removing artifacts. Intent is persisted before
file removal. An incomplete operation retains its journal/gate for explicit
same-key resumption; completion scrubs the manifest and keeps minimal receipts.
Erased submission keys return 410 without allocating replacement work.

Dataset erasure preserves files referenced by surviving versions, including a
column-derived child's original raw source. Model erasure preserves datasets.
Conversations/drafts, operator originals, exports/backups and previously scraped
Prometheus samples remain. Shared filesystem roots and working native locks are
required; expiring soft locks cannot replace them. See the
[deletion contract](api.md#permanent-dataset-and-model-deletion),
[storage finding](../memory/permanent-deletion-storage.md) and
[real-service/process evidence](../evidence/2026-10-19-permanent-deletion/README.md).

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| AI suggestions are incorrect or use unsupported operations | Typed tools, evidence links, authorization, and review before code execution or model promotion |
| Tuning consumes excessive resources | Worker-enforced budgets, concurrency limits, cancellation, and bounded retries |
| Duplicate jobs or inconsistent results | Idempotent submissions, atomic state transitions, unique trial indexes, and durable result recording |
| Data leakage inflates evaluation results | Versioned splits, preprocessing fitted on training data, and a held-out test set |
| Sensitive data reaches model context or logs | Local inference without cloud fallback, minimized context, redaction, access controls, and reviewed retention |
| Model quality is confused with infrastructure health | Separate quality, drift, and operational metrics; disclose label availability |
| Required microservices disrupt domain ownership | Reviewed extraction, shared typed/repository contracts, preserved transactions, and real-service/recovery regressions |
| Local model/runtime behavior changes or does not fit hardware | Locked compatible dependencies, recorded model digest/runtime/context, real-model evaluation, and measured resource limits |
