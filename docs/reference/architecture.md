# Architecture and contracts

The current backend uses one FastAPI application, Redis/Celery workers, and
MongoDB. The course target requires separately deployable model-management,
tuning, and monitoring REST services. See the [roadmap](../../PLAN.md).
The approved [midterm plan](../plans/2026-10-13-midterm-delivery-plan.md) selects
three domain processes sharing code/image/database, thin public routing, one serial
worker, one local-model profile and small live monitoring. This target remains
planned until its service/real-model/deployment gates pass.

## Architecture and ownership

| Component | State and responsibilities | Owned records |
| --- | --- | --- |
| Tracking module | Implemented: register datasets/versions, create experiments, compare results, resolve artifacts | Datasets, models, model versions, experiments |
| Tuning module | Implemented: validate bounded serial searches, persist reservations/trials, cancel jobs | Tuning jobs and trials |
| Monitoring module | Required/planned: separate monitoring REST service, observations, visualization, alert evidence, and LangChain summaries/fixes | Planned monitoring summaries and alerts |
| Conversation tool library | Implemented: 13 typed HTTP operations, trusted context, budgets/keys, public record evidence | Calls existing APIs; no owned durable records |
| Conversation module | Partial: local adapter, grounded reads, durable turns/proposals, routes and confirmed dispatch; live-model and generated-code acceptance remains open | Conversations, turns, and action records |
| Celery workers | Implemented training, tuning, recovery, and transactional tuning ownership | Write through the domain repository interfaces |

Implement separately deployable model-management, tuning, and monitoring REST
services under a reviewed extraction plan. A shared repository/image/database is
allowed; three modules in one API process are not the required service topology.
The conversation layer can remain a bounded orchestration entry point. Preserve
`/api/v1` compatibility through reviewed routing and keep domain repositories
responsible for writes. Tuning/tracking records must stay in a MongoDB deployment
supporting their shared ownership transaction; replacing it with independent
HTTP writes would lose the fence. Pass record/correlation IDs between services;
retain Redis for queued work and separate artifact storage.

## Data model: implemented and planned

Every project-scoped record includes a `project_id`, timestamps, and a schema version. Authorization checks must apply to referenced records as well as the initial request.

See the [tracking schemas](../../src/ml_pipeline_pro/schemas.py),
[tuning schemas](../../src/ml_pipeline_pro/tuning_schemas.py),
[conversation schemas](../../src/ml_pipeline_pro/conversation_schemas.py), and
[conversation store](../../src/ml_pipeline_pro/conversation_store.py) for exact
contracts. The [audit inventory](../project/project-status.md#architecture-and-durable-records)
records the initial backend scope. Dataset registration persists a reference and
hash, not CSV bytes. Binary artifacts stay outside MongoDB. Schema-version fields
exist; migration and retention procedures do not.

| Collection | Fields/intent | Indexes/intent |
| --- | --- | --- |
| `monitoring_summaries` (planned) | Project, model version, window bounds, metric aggregates, label availability | `(project_id, model_version_id, window_start)` |
| `alerts` (planned) | Project, model version, rule, observed value, status, evidence references | `(project_id, model_version_id, created_at)` |
| `conversations`, `conversation_turns` | Project, revision/turn claims, dialogue, verified record snapshots, correlations | Project/request ID and project/conversation/sequence uniqueness; history lookups |
| `conversation_actions` | Project, immutable arguments/hash, confirmation, submission key, attempt claims/outcomes, evidence | Project/conversation/action lookups |

Continue using explicit request and persistence schemas. The
[conversation plan](../plans/2026-10-06-conversation-workflows-plan.md) specifies
project access and retained dialogue/action evidence, without inventing a user
identity system or treating model proposals as confirmed actions. Define dataset/artifact/summary/log
retention and deletion before shared use. Monitoring will use Prometheus for time
series, Grafana for visualization, and MongoDB for selected aggregates and alert
evidence. Index uniqueness is tested; representative query/latency benchmarks
remain unmeasured.

## API contracts and remaining additions

Implemented endpoints use `/api/v1`, consistent errors/correlation IDs,
project-scoped access, and list pagination. The [endpoint inventory](api.md#endpoints)
and generated `/docs` describe the current surface. These monitoring routes remain
proposals; exact contracts require reviewed designs.

| Endpoint | State | Behavior |
| --- | --- | --- |
| `POST /monitoring/observations` | Planned | Ingest timestamped model observations |
| `GET /monitoring/models/{version_id}/summary` | Planned | Return a bounded monitoring summary and evidence |

Tuning jobs use `queued`, `running`, `succeeded`, `failed`, `cancel_requested`, and `cancelled`; experiment records also support `cancelled` for tuning children but have no standalone cancellation endpoint. Submission retries are idempotent, leases/heartbeats are persisted, and recovery claims are bounded. Tuning child writes share a transaction with a parent ownership fence; MongoDB replica set/sharded-cluster support is required. Preserve these contracts while strengthening outage/restart coverage. A succeeded tuning job can report `final_evaluation: skipped_budget`; version registration still requires an evaluated experiment.

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
