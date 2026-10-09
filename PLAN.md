# ML Pipeline Pro Implementation Plan

## Objective and scope

Build the machine learning class platform specified in the
[supplied course requirements](docs/course-requirements.md): model management,
Bayesian tuning, monitoring, LangChain conversation with a local pre-trained
language model, and AI-generated Python integration snippets. Deliver separate
model-management, tuning, and monitoring REST services, Docker containers,
Kubernetes deployment, CI/CD, tests, and onboarding as part of the course scope.

This roadmap was aligned to the user-supplied instructions on October 6-7, 2026
against documentation baseline `ba6334f`. Existing validation retains its own
source revisions in the [project audit](docs/project-status.md). Milestones are
ordered by dependency, with no assumed delivery dates or staffing levels. The
[course checklist](docs/course-requirements.md#requirement-coverage-and-acceptance-evidence)
records incomplete requirements without treating roadmap decisions as approval.

Milestones 1-3 have delivered a working local backend: a packaged FastAPI application, project-scoped dataset/model/experiment/version records, CPU PyTorch training, bounded serial Optuna tuning, explicit final test evaluation, and verified artifacts. Compose and CI are implemented. The audit reran 126 unit/API/training/tuning cases and all nine live-service integration cases successfully; baseline [CI](https://github.com/JacobHermsmeyer21/ML-Pipeline-Pro/actions/runs/37541937953) also passed Python 3.11/3.13 checks and a rebuilt Compose stack.

The course deliverable remains incomplete. Provider-independent conversation tools
are implemented; local LangChain conversation is the next feature slice under the
[revised plan](docs/plans/2026-10-06-conversation-workflows-plan.md), approved October 7, 2026; implementation remains outstanding.
Monitoring and AI code generation are not started. Deployment/onboarding is
complete only for the existing local backend. The current modular FastAPI
application is a development baseline; required domain-service separation must
be delivered regardless of commercial scaling needs. Preserve the
[transactional ownership fixes](docs/project-status.md#ownership-fix-validation)
and [serial recovery gate](docs/verification.md#worker-and-dependency-recovery-validation). Concurrent-load and network-partition
validation remain prerequisites for increasing training concurrency, independent
of separating API services.

The [two-person completion plan](docs/plans/2026-10-08-two-person-course-completion-plan.md)
proposes owners, interface handoffs, dependency checkpoints, and evidence for all
remaining course requirements. That allocation awaits review and preserves the
existing conversation approval; new feature designs still require their own review.

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

The course MVP will support one classification dataset format, one PyTorch
training adapter, metadata/version storage, bounded Bayesian tuning with
LangChain suggestions, comparison, monitoring/visualization with evidence-linked
summaries and proposed fixes, guided dialogue/history, and LangChain-generated
Python snippets. A small API client and documented requests are sufficient;
separate domain services and an exercised Kubernetes/CI/CD deployment are still
required. The classification workload and the pre-trained language model are
distinct; custom language-model training/fine-tuning is optional research work.

Use a locally served pre-trained model through LangChain, with external inference
and cloud fallback disabled for the course workflow. A paid hosted API is not a
dependency of course completion. Select and test the model/runtime, record their
versions and artifact identity, and document inference memory/runtime limits.
Local inference still consumes compute. Model installation and real-model
evaluation cannot be replaced by a deterministic stub demonstration.

TensorFlow, reinforcement learning, a full web UI, automatic model promotion, and
production serving of the managed classification models are later extensions.
PyTorch and Bayesian optimization choose alternatives permitted by the supplied
instructions. The monitoring demo accepts worker metrics and sample inference
observations; commercial multi-tenant hardening is separate from the local
course/test-cluster acceptance.

## Architecture and ownership

| Component | State and responsibilities | Owned records |
| --- | --- | --- |
| Tracking module | Implemented: register datasets/versions, create experiments, compare results, resolve artifacts | Datasets, models, model versions, experiments |
| Tuning module | Implemented: validate bounded serial searches, persist reservations/trials, cancel jobs | Tuning jobs and trials |
| Monitoring module | Required/planned: separate monitoring REST service, observations, visualization, alert evidence, and LangChain summaries/fixes | Planned monitoring summaries and alerts |
| Conversation tool library | Implemented: 13 typed HTTP operations, trusted context, budgets/keys, public record evidence | Calls existing APIs; no owned durable records |
| Conversation module | Required/planned: local pre-trained model through LangChain, guided dialogue/history, validated actions, and AI-generated code proposals | Planned conversations, turns, and action records |
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

See [schemas.py](src/ml_pipeline_pro/schemas.py), [tuning_schemas.py](src/ml_pipeline_pro/tuning_schemas.py), and the [audit record inventory](docs/project-status.md#architecture-and-durable-records) for the exact contracts. Dataset registration persists a reference and hash, not CSV bytes. Binary artifacts stay outside MongoDB. Schema-version fields exist; migration and retention procedures do not.

| Planned collection | Proposed core fields | Proposed indexes |
| --- | --- | --- |
| `monitoring_summaries` | Project, model version, window bounds, metric aggregates, label availability | `(project_id, model_version_id, window_start)` |
| `alerts` | Project, model version, rule, observed value, status, evidence references | `(project_id, model_version_id, created_at)` |
| `conversations`, `conversation_turns` | Project, revision/turn claims, dialogue, verified record snapshots, correlations | Project/request ID and project/conversation/sequence uniqueness; history lookups |
| `conversation_actions` | Project, immutable arguments/hash, confirmation, submission key, attempt claims/outcomes, evidence | Project/conversation/action lookups |

Continue using explicit request and persistence schemas. The
[conversation plan](docs/plans/2026-10-06-conversation-workflows-plan.md) specifies
project access and retained dialogue/action evidence, without inventing a user
identity system or treating model proposals as confirmed actions. Define dataset/artifact/summary/log
retention and deletion before shared use. Monitoring will use Prometheus for time
series, Grafana for visualization, and MongoDB for selected aggregates and alert
evidence. Index uniqueness is tested; representative query/latency benchmarks
remain unmeasured.

## API contracts and remaining additions

Implemented endpoints use `/api/v1`, consistent errors/correlation IDs, project-scoped access, and list pagination. The [README endpoint inventory](README.md#development-setup) and generated `/docs` describe the full current surface. The table below lists future routes; their exact contracts require reviewed designs.

| Endpoint | State | Behavior |
| --- | --- | --- |
| `POST /monitoring/observations` | Planned | Ingest timestamped model observations |
| `GET /monitoring/models/{version_id}/summary` | Planned | Return a bounded monitoring summary and evidence |

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

**Status:** Tool slice and initial conversation foundation implemented; the local
conversational interface remains in development. The provider-independent layer
exposes 13 existing API operations with budgets, trusted context/retry keys, and
record evidence. Locked LangChain dependencies, strict conversation schemas,
the model interface, and chat settings now exist. The local inference adapter has
deterministic SDK/HTTP tests; durable turn/proposal storage has real-MongoDB
claim/replay/takeover coverage. The bounded host loop grounds supplied API facts
and preflights saved proposals. Authenticated chat/history/action routes and
confirmed dispatch now include same-key retries and killed-chat-process recovery.
Artifact-specific token verification, real-model evaluation, independent review
and clean-checkout onboarding remain outstanding. See the
[development guide](docs/conversation-development.md).
The [implemented tool design](docs/plans/2026-10-06-conversation-tools-plan.md) and
[revised local conversation plan](docs/plans/2026-10-06-conversation-workflows-plan.md)
have different approval scopes. Course C3/C5 still need evidence.

- Configure LangChain's local pre-trained model adapter and structured tools; document model installation, artifact/version identity, and inference limits without paid external calls.
- Store project-scoped dialogue/action state and retrieve relevant experiment/trial history to guide pipeline creation and enhancement.
- Ask for missing dataset, objective, or budget values before submitting incomplete configurations.
- Suggest supported tuning configurations from history and documented practices; preserve explicit budgets, validation-only selection, and worker enforcement.
- Validate proposed actions through API schemas and project checks; confirm each exact mutation separately and audit its decision/outcome.
- Return explanations with experiment IDs, trial IDs, or metric windows as evidence.

**Acceptance:** A real locally served pre-trained model through LangChain guides
pipeline steps, asks for missing inputs, suggests bounded tuning from saved
history, and supports confirmed experiment/tuning submission and comparison with
record evidence. Invalid/unauthorized actions fail at the intended boundary;
model failure leaves direct API use available. Deterministic tests and an opt-in
real local-model evaluation both pass; retain actual model/resource provenance.

### 5. Add monitoring and diagnosis

**Status:** Not started. Logs, health endpoints, and experiment metrics exist; production observations, Prometheus/Grafana, drift/quality history, and alerts do not.

- Export service latency, errors, queue depth, worker health, and training duration to Prometheus.
- Ingest sample inference observations and track prediction distributions, feature drift, and quality metrics where labels exist.
- Build Grafana dashboards and configurable alert windows and thresholds.
- Define an observable update interval and ingest observations while the sample workload runs; demonstrate dashboard/alert updates within that reviewed interval.
- Use LangChain and the local pre-trained model to summarize metric/log evidence and propose checks or fixes, distinguishing observed changes from possible causes.

**Acceptance:** The separate monitoring service receives a running workload's
observations, updates Prometheus/Grafana within the specified interval, and
exposes a triggered alert's metric/log window. LangChain/local-model summaries
cite evidence and propose fixes/checks without asserting an inferred root cause.
Missing/delayed labels remain visible. Logs/health alone do not meet course C6.

### 6. Generate reviewable pipeline code

**Status:** Not started. Checked-in Python demos are examples, not a generated-code capability or execution sandbox.

- Define supported snippet templates and record assumptions, dependency requirements, and provenance.
- Use LangChain with a local pre-trained language model to generate Python pipeline-integration snippets directly from conversational requests. Templates can guide or validate generation; static templates/examples alone do not meet course C7.
- Check syntax, supported imports, API usage, and secret handling.
- Present generated code for explicit review before any execution.
- Provide isolated execution with resource and network controls if execution is enabled.

**Acceptance:** Natural-language requests produce AI-generated Python snippets
through LangChain/local inference with recorded model/prompt provenance. Supported
snippets satisfy syntax, import, API, and secret-handling checks; unsupported
output is rejected. Show real-model examples and deterministic validation tests.
Execution remains optional and requires explicit review and isolation if enabled.

### 7. Prepare deployment and onboarding

**Status:** Partially delivered for the local backend. Docker/Compose, GitHub
Actions checks, tutorials, and validation records exist. Required separate domain
services, Kubernetes deployment, and deployment CI/CD remain outstanding (C2/C8);
shared-production controls and restore criteria are additional open work.

- Review and extract separately deployable model-management, tuning, and monitoring REST services; preserve public contracts and shared transactional ownership.
- Containerize the required services and extend Compose/local tutorials; add Kubernetes manifests with resources, probes, model/storage configuration, and external secret references for a documented test cluster.
- Demonstrate the supported replica scaling of stateless APIs, including request replay/project access across replicas. Preserve serial training workers and bound inference separately; API separation/scaling does not authorize extra concurrent training.
- Define authentication and project-level authorization, backup/restore, artifact retention, and recovery procedures before shared deployment.
- Add immutable dataset/object storage, schema migrations, and tested metadata/artifact restore procedures.
- Extend GitHub Actions checks into a CI/CD deployment gate and exercise rollout/smoke tests in the Kubernetes test cluster. Merely adding YAML does not establish deployment.
- Add conversation, monitoring, generated-code, troubleshooting, and operations guides as those workflows ship.

**Course acceptance:** A clean environment runs all required independent domain
services, uses the local model through LangChain, and completes the documented
workflow. Docker builds, supported stateless API replica scaling, and a
CI/CD-triggered Kubernetes test-cluster rollout/smoke test pass with retained
evidence. Tutorials cover common use and advanced
optimization. **Additional shared-production acceptance:** identity/access,
authenticated dependencies, immutable storage/retention, and a restore exercise
that resolves retained metadata/artifacts are verified before shared use.

## Immediate development priorities

1. Keep transactional parent ownership fencing and its real-MongoDB boundary regressions passing; the audited stale-child-write bugs are fixed.
2. Keep the controlled worker-loss/dependency-outage recovery gate passing in CI, including final evaluation and attempt exhaustion. Concurrent load and network partitions remain prerequisites for parallel execution.
3. Retain the provider-independent conversation tool contracts, project checks, explicit budgets, and idempotency tests in the [approved tool slice](docs/plans/2026-10-06-conversation-tools-plan.md).
4. Implement the approved local conversation plan, select/evaluate an installed pre-trained model, and implement only the approved scope: LangChain, guided dialogue/history, bounded suggestions, confirmed actions, and grounded explanations.
5. Review domain-service extraction early; deliver the three required independent REST services, monitoring with LangChain summaries/fixes, AI snippet generation, and Kubernetes/CI/CD evidence. These are course obligations, not optional commercial-scale work. Keep current serial CPU training limits.
6. Complete every row of the supplied course checklist and its onboarding demonstration. Track shared-production hardening and quantitative research claims separately.

The [audit](docs/project-status.md#next-work-in-order) records the source evidence and unfinished infrastructure work. No delivery dates or quantitative completion percentage are assumed.

## Testing strategy

**Latest retained conversation checks:** 402 local unit/API/training/tuning/tool
cases, 56 ordinary real-service cases, and ten isolated recovery cases, with
source hashes and raw results in the
[action-slice evidence](docs/evidence/2026-10-08-conversation-actions/results.json).
Earlier counts retain their own revisions in the
[status record](docs/project-status.md) and historical
[ten-iteration report](docs/verification.md#ten-iteration-validation-october-6-2026).
The target strategy still needs local-model, separate
service, monitoring, AI generation, Kubernetes/deployment, concurrent-load,
partition, restore, and generated-code isolation evidence.

- **Unit tests:** Schema validation, tuning budgets, objective selection, job transitions, authorization checks, and provider-independent tool dispatch.
- **Integration tests:** Real MongoDB and Redis, queued worker execution, index behavior, restart recovery, cancellation, and artifact persistence.
- **End-to-end tests:** Dataset registration through training, tuning, model version registration, monitoring, and conversational queries.
- **AI evaluations:** Representative prompts, incomplete requests, ambiguous objectives, hostile instructions embedded in retrieved records, unsupported actions, and evidence citation accuracy.
- **Operational tests:** Existing serial limits, local model timeouts/memory/context limits, queue/database outages, service routing, Kubernetes rollout, restore, and generated-code isolation when execution is enabled.

Use deterministic fixtures and a small synthetic dataset in normal CI. Keep
real local-model checks opt-in with explicit request/token/runtime/resource
budgets and an installed artifact; retain a successful run for course acceptance.
No paid API or model download is required during ordinary CI. Assess validated
actions, permissions, grounding, and snippet correctness rather than exact wording.

## Measurement and reporting

Treat all supplied resume percentages as hypotheses until measured. Establish baselines before optimizations and preserve benchmark scripts, environment details, raw results, and limitations.

| Claim to evaluate | Metric and experiment |
| --- | --- |
| 10x faster retrieval | Baseline median and p95 query latency divided by optimized latency on the same dataset, hardware, queries, and cache conditions |
| 30% less tuning time | Reduction in elapsed time to a fixed validation-quality threshold, across multiple seeds with equal resource budgets |
| 40% less debugging time | Reduction in time to correctly diagnose and resolve comparable seeded faults, with sample size and unresolved tasks reported |
| 25% higher coding efficiency | Define efficiency first; measure correct completed integration tasks per hour and report defects and review time |
| 50% higher model throughput | Increase in successful completed model workflows per hour under fixed compute, task mix, and quality requirements |

For reduction metrics, use `(baseline - assisted) / baseline`. For throughput improvements, use `(assisted - baseline) / baseline`. Report spread across runs and confidence intervals where sample sizes support them. Record failures, compute/resource usage, and known operating costs alongside speed; label unknown costs. State how human tasks were assigned to control for learning effects.

Only write resume bullets in the past tense after the relevant capability exists. Attach measured quantitative claims to their benchmark conditions. Until then, describe the platform as planned or in development.

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

## Completion criteria

The course deliverable is complete when every row of the
[course checklist](docs/course-requirements.md#requirement-coverage-and-acceptance-evidence)
has retained acceptance evidence. An engineer follows the tutorials to register
inputs, train/tune with LangChain suggestions, compare/register a version, inspect
live monitoring and its generated diagnosis, query history through a real local
pre-trained model, and obtain validated AI-generated Python snippets. The three
domain REST services run independently, Docker and CI/CD Kubernetes rollout/smoke
tests pass, and existing ownership/recovery contracts remain verified. Production
hardening and proposed resume percentages are separate claims with their own
evidence; they do not substitute for any course requirement.
