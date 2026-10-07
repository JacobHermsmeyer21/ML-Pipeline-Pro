# ML Pipeline Pro Implementation Plan

## Objective and scope

Build a Python platform that combines reproducible model experiments, automated hyperparameter tuning, performance monitoring, and LangChain-based conversational assistance. Deliver an end-to-end local workflow before adding scalable deployment and advanced AI features.

This is the implementation roadmap, updated October 6, 2026 against baseline `0e37e6e`. Milestones are ordered by dependency, with no assumed delivery dates or staffing levels. The [project audit](docs/project-status.md) records the implemented behavior, current validation, and open findings.

Milestones 1-3 have delivered a working local backend: a packaged FastAPI application, project-scoped dataset/model/experiment/version records, CPU PyTorch training, bounded serial Optuna tuning, explicit final test evaluation, and verified artifacts. Compose and CI are implemented. The audit reran 126 unit/API/training/tuning cases and all nine live-service integration cases successfully; baseline [CI](https://github.com/JacobHermsmeyer21/ML-Pipeline-Pro/actions/runs/37541937953) also passed Python 3.11/3.13 checks and a rebuilt Compose stack.

The full MVP remains incomplete. Conversation is the next feature milestone; monitoring and code generation are not started. Deployment/onboarding is complete only for local development. The audited tuning ownership bugs are fixed with [transactional parent/child writes and boundary regressions](docs/project-status.md#ownership-fix-validation). The [serial recovery gate](docs/recovery.md) now covers physical worker loss and dependency outages through Beat-driven recovery. Concurrent-load and network-partition validation remain before expanding worker concurrency. Keep domain responsibilities in one modular FastAPI deployment initially; split services when measurements justify it.

## Development workflow

Apply the [development methodology](docs/development-methodology.md) to each
substantive change: clarify and critique the proposal, commit a dated design plan
using [the template](docs/plans/template.md), obtain human review, then implement
with continuous verification. Define acceptance evidence before implementation.
The roadmap orders work; each design still needs its own review. Local edits use
the compressed workflow with the same relevant verification discipline.

[AGENTS.md](AGENTS.md) holds shared contracts and pre-commit checks.
[Project memory](docs/memory/README.md) preserves confirmed mechanisms and approaches
that should not be rediscovered. Keep review records and raw execution provenance
with each outcome; disclose unperformed checks or unavailable independent review.

## MVP boundaries

The MVP will support one classification dataset format, one PyTorch training adapter, model and experiment metadata, bounded Bayesian tuning, experiment comparison, basic monitoring, and conversational access to those workflows. A small API client and documented requests are sufficient for initial use.

TensorFlow support, reinforcement learning for tuning, a full web interface, automatic model promotion, and production inference serving are later extensions. The initial monitoring integration will accept metrics from workers and a sample inference client; it will not imply a complete model serving platform.

## Architecture and ownership

| Component | State and responsibilities | Owned records |
| --- | --- | --- |
| Tracking module | Implemented: register datasets/versions, create experiments, compare results, resolve artifacts | Datasets, models, model versions, experiments |
| Tuning module | Implemented: validate bounded serial searches, persist reservations/trials, cancel jobs | Tuning jobs and trials |
| Monitoring module | Planned: ingest observations, query history, evaluate alert rules | Planned monitoring summaries and alerts |
| Conversation module | Planned: dialogue, typed tools, evidence-linked explanations and code proposals | Planned conversations and action audit records |
| Celery workers | Implemented training, tuning, recovery, and transactional tuning ownership | Write through the domain repository interfaces |

Keep service contracts explicit even when components share a MongoDB deployment. Use domain repository interfaces for writes. The tuning ownership transaction coordinates tuning and tracking records within the same MongoDB deployment; preserve that atomic boundary when considering service separation. Pass record IDs and correlation IDs between components. Use Redis for queued work and artifact storage for binary outputs.

## Data model: implemented and planned

Every project-scoped record includes a `project_id`, timestamps, and a schema version. Authorization checks must apply to referenced records as well as the initial request.

| Implemented collection | Core persisted fields | Implemented indexes |
| --- | --- | --- |
| `datasets` | Name/version, local `uri`, `sha256`, column definitions, `num_classes`, `row_counts` | Unique project/name/version; project/created time/ID |
| `models` | Name, framework, task, architecture | Unique project/name; project/created time/ID |
| `model_versions` | Model/version, source experiment, checkpoint reference, `dependencies` | Unique project/model/version; project/created time/ID |
| `experiments` | Input IDs, config/seed, submission key/hash, status/attempts/leases, metrics/artifacts/dependencies, tuning linkage, test-evaluation flag | Unique project/submission key; project/model or status/created time; recovery; project/created time/ID |
| `tuning_jobs` | Objective/space/limits, status/phase, claims/deadlines, reservation/progress, selected config/trial/experiment/value, final evaluation/stop reason | Unique project/submission key; project/status/created time; recovery; project/created time/ID |
| `trials` | Job ID, zero-based `number`, parameters/config, experiment ID, metrics/objective, duration/status/error | Unique `(project_id, tuning_job_id, number)` |

See [schemas.py](src/ml_pipeline_pro/schemas.py), [tuning_schemas.py](src/ml_pipeline_pro/tuning_schemas.py), and the [audit record inventory](docs/project-status.md#architecture-and-durable-records) for the exact contracts. Dataset registration persists a reference and hash, not CSV bytes. Binary artifacts stay outside MongoDB. Schema-version fields exist; migration and retention procedures do not.

| Planned collection | Proposed core fields | Proposed indexes |
| --- | --- | --- |
| `monitoring_summaries` | Project, model version, window bounds, metric aggregates, label availability | `(project_id, model_version_id, window_start)` |
| `alerts` | Project, model version, rule, observed value, status, evidence references | `(project_id, model_version_id, created_at)` |
| `conversations` | Project, user ID, messages, tool references, retention timestamp | `(project_id, user_id, updated_at)` |
| `action_audit` | Project, actor, action, resource IDs, approval reference, outcome, correlation ID | `(project_id, created_at)` |

Continue using explicit request and persistence schemas. Define configurable retention for artifacts, datasets, conversations, summaries, and logs. The monitoring design will keep high-volume time series in Prometheus, with selected aggregates and alert evidence in MongoDB. Index uniqueness is tested, but representative query-plan and latency benchmarks remain to be implemented.

## API contracts and remaining additions

Implemented endpoints use `/api/v1`, consistent errors/correlation IDs, project-scoped access, and list pagination. The [README endpoint inventory](README.md#development-setup) and generated `/docs` describe the full current surface. The milestone contracts below distinguish existing routes from planned ones.

| Endpoint | State | Behavior |
| --- | --- | --- |
| `POST /datasets` | Implemented | Register a validated local CSV reference/version |
| `POST /models` | Implemented | Create an MLP classification model record |
| `POST /experiments` | Implemented | Validate and queue idempotent training; return `202` |
| `GET /experiments/{id}`, `GET /experiments` | Implemented | Retrieve status/metrics/artifacts; filter and paginate |
| `GET /experiments/compare` | Implemented | Compare succeeded experiments on the same dataset using validation metrics |
| `POST /models/{id}/versions` | Implemented | Register a verified checkpoint after successful final test evaluation |
| `POST /tuning-jobs` | Implemented | Queue an idempotent bounded serial search; return `202` |
| `GET /tuning-jobs/{id}`, `GET /tuning-jobs/{id}/trials` | Implemented | Return progress/best outcome and paginated saved trials |
| `POST /tuning-jobs/{id}/cancel` | Implemented | Cancel queued work or cooperatively stop running work |
| `POST /monitoring/observations` | Planned | Ingest timestamped model observations |
| `GET /monitoring/models/{version_id}/summary` | Planned | Return a bounded monitoring summary and evidence |
| `POST /chat` | Planned | Interpret requests and invoke validated authorized tools |
| `GET /health/live`, `GET /health/ready` | Implemented | Process liveness and MongoDB/Redis connectivity |

Tuning jobs use `queued`, `running`, `succeeded`, `failed`, `cancel_requested`, and `cancelled`; experiment records also support `cancelled` for tuning children but have no standalone cancellation endpoint. Submission retries are idempotent, leases/heartbeats are persisted, and recovery claims are bounded. Tuning child writes share a transaction with a parent ownership fence; MongoDB replica set/sharded-cluster support is required. Preserve these contracts while strengthening outage/restart coverage. A succeeded tuning job can report `final_evaluation: skipped_budget`; version registration still requires an evaluated experiment.

## Implementation milestones

### 1. Establish the development foundation

**Status:** Initial scope complete. Local checks and GitHub CI verify dependency installation, container startup, health endpoints, and integration without model-provider credentials. Broader supported-platform checks and operational probes remain later work.

- Create Python package structure, compatible dependency constraints, lockfile, and development tooling.
- Add `.env.example`, ignore rules, configuration validation, and structured logging with secret redaction.
- Add FastAPI service entry points, MongoDB repository interfaces, and Docker Compose for local dependencies.
- Configure GitHub Actions for linting, unit tests, and dependency checks.

**Acceptance:** A documented command starts the local services; readiness detects missing dependencies; CI runs on a clean checkout without real provider credentials.

### 2. Deliver reproducible experiment tracking

**Status:** Initial CPU classification scope complete. Repeated runs produce identical checkpoint bytes and metrics in the tested environment; altered test labels do not affect selected weights. Registration/indexes, atomic claims, queued training, artifact retrieval, and model versions are verified. Standalone experiment cancellation, immutable dataset storage, retention, shared identity, broader adapters, and scalable artifacts remain later work. Tuning cancellation is implemented in milestone 3.

- Implement the initial dataset, model, model version, and experiment schemas and indexes.
- Build a PyTorch adapter with a small classification example, explicit train/validation/test splits, and a fixed seed.
- Add queued training, artifact hashing, configuration capture, and lifecycle reporting.
- Provide experiment list and comparison workflows.

**Acceptance:** An engineer can submit a training job, inspect its status, retrieve metrics and artifacts, and reproduce results within a documented tolerance. Failed training produces a terminal status and actionable error. The test split is excluded from training and tuning decisions.

### 3. Automate bounded tuning

**Status:** Initial bounded serial CPU scope, audited ownership fixes, and controlled process-loss/outage validation complete. Optuna TPE uses typed ranges and trial/runtime limits. Reservations fix configurations/experiment IDs; tested replay reuses completed training and preserves deadlines. Selection uses validation metrics followed by final holdout evaluation, subject to budget. Cancellation is cooperative. Transactional parent fences and ten real-MongoDB boundary regressions address stale child claims and final evaluation persistence after parent ownership replacement. Ten isolated Compose recovery cases cover worker kills, final evaluation/persistence, attempt exhaustion, and MongoDB/Redis restarts. Concurrent-load validation, parallel trials, and broader adapters remain later work.

- Integrate Optuna's Bayesian optimization sampler and validate parameter types, ranges, and objective direction.
- Enforce trial count, runtime, concurrency, and resource limits in workers.
- Persist successful, failed, and cancelled trials and preserve completed results after restart.
- Implement cancellation, retry behavior, and best-trial selection with an explicit policy for invalid metrics.

**Acceptance:** A job stops scheduling at its trial/search limits, records each trial, selects the best valid outcome, and honors cancellation. Runtime enforcement is cooperative with a hard task fallback, not an exact wall-clock guarantee. Recovery preserves completed training and deadlines, rejects stale parent/child writes, and is verified under actual process loss. Search uses validation metrics; final test evaluation happens after selection, or reports skipped budget explicitly. The controlled serial process-loss/outage gate is delivered; retain it in CI.

### 4. Add conversational workflows

**Status:** Not started; next feature milestone. There is no LangChain/provider dependency, `/chat` route, conversation store, or AI evaluation suite yet.

- Configure a LangChain model-provider adapter and structured tools for experiment queries and job submission.
- Store project-scoped dialogue state and retrieve relevant experiment history.
- Ask for missing dataset, objective, or budget values before submitting incomplete configurations.
- Validate proposed actions through API schemas and authorization checks; audit mutating actions.
- Return explanations with experiment IDs, trial IDs, or metric windows as evidence.

**Acceptance:** A user can create an experiment and tuning job through conversation, compare results, and inspect supporting records. Invalid tool arguments and unauthorized resources are rejected. Provider failure does not prevent direct API use. Tests use deterministic provider stubs plus a small opt-in live evaluation suite.

### 5. Add monitoring and diagnosis

**Status:** Not started. Logs, health endpoints, and experiment metrics exist; production observations, Prometheus/Grafana, drift/quality history, and alerts do not.

- Export service latency, errors, queue depth, worker health, and training duration to Prometheus.
- Ingest sample inference observations and track prediction distributions, feature drift, and quality metrics where labels exist.
- Build Grafana dashboards and configurable alert windows and thresholds.
- Generate summaries grounded in alert evidence, distinguishing measured change from a possible cause.

**Acceptance:** A sample workload triggers a configured alert and exposes the relevant metric window. Missing or delayed labels are visible in summaries. Assistant explanations cite evidence and propose checks without presenting an inferred root cause as established fact.

### 6. Generate reviewable pipeline code

**Status:** Not started. Checked-in Python demos are examples, not a generated-code capability or execution sandbox.

- Define supported snippet templates and record assumptions, dependency requirements, and provenance.
- Check syntax, supported imports, API usage, and secret handling.
- Present generated code for explicit review before any execution.
- Provide isolated execution with resource and network controls if execution is enabled.

**Acceptance:** Supported requests produce usable snippets validated against the documented API. Generated code cannot execute solely because the assistant proposed it. Unsafe or unsupported snippets are rejected with a useful explanation.

### 7. Prepare deployment and onboarding

**Status:** Partially delivered for local use. A non-root Docker image, Compose, CI image startup/integration checks, quickstart, classification/tuning guides, and validation report exist. Shared-deployment and restore criteria remain open.

- Extend the existing image/Compose setup with operational probes and authenticated dependencies; add Kubernetes manifests with resource limits and external secret references.
- Define authentication and project-level authorization, backup/restore, artifact retention, and recovery procedures before shared deployment.
- Add immutable dataset/object storage, schema migrations, and tested metadata/artifact restore procedures.
- Extend existing CI image/integration checks into a deployment gate and verify a test-cluster rollout.
- Add conversation, monitoring, generated-code, troubleshooting, and operations guides as those workflows ship.

**Acceptance:** A clean environment can run the documented example with Compose. Kubernetes deployment passes a smoke test in a test cluster. A restore exercise recovers metadata and resolves retained artifacts. Engineers can complete the tutorial using only the documentation.

## Immediate development priorities

1. Keep transactional parent ownership fencing and its real-MongoDB boundary regressions passing; the audited stale-child-write bugs are fixed.
2. Keep the controlled worker-loss/dependency-outage recovery gate passing in CI, including final evaluation and attempt exhaustion. Concurrent load and network partitions remain prerequisites for parallel execution.
3. Define provider-independent conversation tool contracts using the implemented API schemas, project checks, and idempotency semantics; this is the next development slice.
4. Implement a small conversation slice with deterministic provider stubs, project-scoped dialogue/action evidence, missing-input handling, and grounded explanations; then add opt-in live evaluation.
5. Proceed to monitoring, reviewed code generation, and shared-deployment requirements in milestones 5-7. Keep the current serial CPU limits.

The [audit](docs/project-status.md#next-work-in-order) records the source evidence and unfinished infrastructure work. No delivery dates or quantitative completion percentage are assumed.

## Testing strategy

**Implemented checks:** 129 unit/API/training/tuning cases, 20 ordinary opt-in real-service cases, and ten separately enabled isolated worker/dependency recovery cases. CI checks Python 3.11/3.13, lint/format, installed compatibility, runtime advisories, rebuilt Compose workflows, and the recovery gate with uploaded evidence. The [ten-iteration report](docs/test-validation.md) preserves historical repeated functional validation. The following list is the target strategy; provider, monitoring, concurrent-load, network-partition, restore, and generated-code isolation tests remain to be built.

- **Unit tests:** Schema validation, tuning budgets, objective selection, job transitions, authorization checks, and provider-independent tool dispatch.
- **Integration tests:** Real MongoDB and Redis, queued worker execution, index behavior, restart recovery, cancellation, and artifact persistence.
- **End-to-end tests:** Dataset registration through training, tuning, model version registration, monitoring, and conversational queries.
- **AI evaluations:** Representative prompts, incomplete requests, ambiguous objectives, hostile instructions embedded in retrieved records, unsupported actions, and evidence citation accuracy.
- **Operational tests:** Concurrency limits, provider timeouts, queue outages, database failures, backup recovery, and isolation of generated code.

Use deterministic fixtures and a small synthetic dataset in CI. Keep live language model checks opt-in with cost budgets. Avoid requiring exact wording from probabilistic responses; assess validated actions, permissions, and factual grounding instead.

## Measurement and reporting

Treat all supplied resume percentages as hypotheses until measured. Establish baselines before optimizations and preserve benchmark scripts, environment details, raw results, and limitations.

| Claim to evaluate | Metric and experiment |
| --- | --- |
| 10x faster retrieval | Baseline median and p95 query latency divided by optimized latency on the same dataset, hardware, queries, and cache conditions |
| 30% less tuning time | Reduction in elapsed time to a fixed validation-quality threshold, across multiple seeds with equal resource budgets |
| 40% less debugging time | Reduction in time to correctly diagnose and resolve comparable seeded faults, with sample size and unresolved tasks reported |
| 25% higher coding efficiency | Define efficiency first; measure correct completed integration tasks per hour and report defects and review time |
| 50% higher model throughput | Increase in successful completed model workflows per hour under fixed compute, task mix, and quality requirements |

For reduction metrics, use `(baseline - assisted) / baseline`. For throughput improvements, use `(assisted - baseline) / baseline`. Report spread across runs and confidence intervals where sample sizes support them. Record failures and provider costs alongside speed. State how human tasks were assigned to control for learning effects.

Only write resume bullets in the past tense after the relevant capability exists. Attach measured quantitative claims to their benchmark conditions. Until then, describe the platform as planned or in development.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| AI suggestions are incorrect or use unsupported operations | Typed tools, evidence links, authorization, and review before code execution or model promotion |
| Tuning consumes excessive resources | Worker-enforced budgets, concurrency limits, cancellation, and bounded retries |
| Duplicate jobs or inconsistent results | Idempotent submissions, atomic state transitions, unique trial indexes, and durable result recording |
| Data leakage inflates evaluation results | Versioned splits, preprocessing fitted on training data, and a held-out test set |
| Sensitive data reaches model providers or logs | Minimized context, redaction, explicit access controls, and configurable retention |
| Model quality is confused with infrastructure health | Separate quality, drift, and operational metrics; disclose label availability |
| Microservice overhead slows initial delivery | Small service boundaries, shared typed contracts, and one local Compose workflow |
| Provider behavior or dependencies change | Locked compatible dependencies, provider adapters, contract tests, and recorded model/configuration identifiers |

## Completion criteria

The initial release is complete when an engineer can follow the quickstart to register a dataset, train and tune a model, compare results, register a version, inspect monitoring, and query the recorded evidence through conversation. Required tests pass, deployment and recovery procedures are exercised, generated code respects review boundaries, and reported performance claims are supported by reproducible measurements.
