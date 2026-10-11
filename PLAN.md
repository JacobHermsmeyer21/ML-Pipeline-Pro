# ML Pipeline Pro Roadmap

## Objective and scope

Deliver the [course requirements](docs/project/course-requirements.md): model
management, bounded Bayesian tuning, monitoring, LangChain conversation with a
local pre-trained model, and AI-generated Python snippets. Separate domain REST
services, Docker, Kubernetes, CI/CD, tests, and onboarding are required.
Paid model APIs and custom language-model training are outside the required scope.

The initial backend works; the **full course deliverable remains incomplete**.
This roadmap orders work. Individual designs require explicit human approval;
roadmap entries do not approve implementation. Verified results and limitations
are recorded in [project status](docs/project/project-status.md).

## Implementation milestones

### 1. Establish the development foundation

**Status:** Initial scope complete: packaged FastAPI app, locked dependencies,
validated settings, health checks, structured logs, Docker Compose, and CI checks.

**Acceptance:** A clean checkout starts the local stack; readiness reports missing
dependencies; CI runs without model-provider credentials. Broader platform checks
and shared deployment controls remain open.

### 2. Deliver reproducible experiment tracking

**Status:** Initial CPU classification scope complete: project-scoped datasets,
models, experiments, versions, queued training, comparison, and verified artifacts.

**Acceptance:** Register inputs, train, inspect metrics, download artifacts, and
reproduce results within documented tolerance. Fit preprocessing on training rows,
select checkpoints by validation metrics, and keep test data out of selection.
Failed jobs report terminal errors. Immutable dataset storage, retention, broader
adapters, and standalone experiment cancellation remain open.

### 3. Automate bounded tuning

**Status:** Serial Optuna TPE tuning, cancellation, transactional ownership fixes,
and controlled worker-loss/dependency-outage recovery are delivered.

**Acceptance:** Enforce trial/runtime limits, retain trial results, choose the best
valid validation outcome, and evaluate its test split only after selection.
Report `skipped_budget` if final evaluation cannot fit. Recovery preserves reserved
configurations, experiment IDs, artifacts, and original deadlines, and rejects
stale writes. Keep real-service and recovery gates passing. Runtime enforcement is
cooperative with a hard task fallback. Concurrent-load and partition evidence are
required before increasing training concurrency.

### 4. Add conversational workflows

**Status:** Partial: 13 typed tools, locked LangChain dependencies, a tested local
adapter, durable storage, grounded reads, authenticated routes, and confirmed
action dispatch/recovery exist.
An explicit installed Qwen profile has verified token admission. The approved
[typed-completion protocol](docs/plans/2026-10-09-conversation-typed-completion-plan.md)
is implemented, but its selected 7B run passes only three of ten scenarios.
Successful model evaluation, independent review, and
clean-checkout onboarding remain open. The
[conversation plan](docs/plans/2026-10-06-conversation-workflows-plan.md) was approved
October 7, 2026; its outcome and the
[development guide](docs/guides/conversation-development.md) track each slice.

**Acceptance:** A real local model guides pipeline steps, asks for missing inputs,
uses recorded history to suggest bounded tuning, and supports individually
confirmed actions. Validate schemas, project access, budgets, and exact arguments;
retain decisions, outcomes, and evidence IDs. Invalid actions fail at the intended
boundary; direct API use remains available after model failure. Pass deterministic
tests and a bounded live-model evaluation with model/runtime/resource provenance.

### 5. Add monitoring and diagnosis

**Status:** Not started. Existing logs, health checks, and experiment metrics do
not establish live monitoring.

**Acceptance:** A separate monitoring REST service ingests sample observations,
exports operational and model metrics to Prometheus, and updates Grafana and alerts
within a reviewed interval. Include label availability, drift/quality history,
and metric/log windows. LangChain/local-model summaries cite evidence and propose
checks or fixes; inferred causes remain labelled as hypotheses.

### 6. Generate reviewable pipeline code

**Status:** A2's approved generation/validation and saved-draft implementation
exists. Real-model acceptance and review evidence are recorded in the
[A2 outcome](docs/plans/2026-10-08-person-a-snippet-generation-plan.md#implementation-outcome);
course closure still requires its full evidence and human review.

**Acceptance:** Conversational requests generate Python snippets through
LangChain/local inference. Record assumptions and model/prompt provenance; check
syntax, supported imports, API use, and secrets; reject unsupported output and
present drafts for human review. Static templates alone do not satisfy this
requirement. Retain real-model examples and deterministic validation. Execution is
optional and, if enabled, requires explicit review and resource/network isolation.

### 7. Prepare deployment and onboarding

**Status:** Partial: local Docker/Compose, CI checks, and backend tutorials exist.
Independent domain services, Kubernetes, and deployment CI/CD remain outstanding.

**Acceptance:** Extract separately deployable model-management, tuning, and
monitoring REST services under reviewed contracts. Preserve `/api/v1`, project
access, idempotency, and shared MongoDB ownership transactions. Containerize the
services; configure Kubernetes resources, probes, model/storage paths, and external
secrets. Exercise CI/CD rollout, smoke tests, and stateless API replica scaling in
a documented test cluster while retaining serial training. A clean-checkout
tutorial covers conversation, history-based optimization, monitoring, and generated
code. Before shared use, verify identity/access, authenticated dependencies,
immutable storage, retention/migrations, and metadata/artifact backup and restore.

## Immediate development priorities

1. Preserve passing ownership, artifact, idempotency, and serial recovery gates.
2. Finish the approved conversation scope and retain real local-model evidence.
3. Review service extraction and the pending monitoring/deployment designs;
   finish the approved snippet evidence and review work.
4. Complete all nine course checklist rows with retained evidence and onboarding.

The [two-person completion plan](docs/plans/2026-10-08-two-person-course-completion-plan.md)
records proposed owners and handoffs; the allocation and new designs await review.
Person A's existing conversation approval retains its recorded scope.

## Development workflow

Follow the [development method](docs/project/development-methodology.md): clarify
and challenge requirements, commit a dated plan, obtain human review, implement,
and verify. Use the [plan template](docs/plans/template.md),
[repository rules](AGENTS.md), and [technical memory](docs/memory/README.md).
Material design changes require renewed review. Documentation and mechanical
edits use the compressed edit/check loop.

See [architecture](docs/reference/architecture.md) for ownership and current
contracts, and [verification](docs/guides/verification.md) for checks and opt-in
service gates. Planned model, monitoring, service, deployment, concurrency, and
restore evidence must remain outstanding until exercised. Selected-case skips and
unavailable review are gaps, not passes.

## Measurement and reporting

[Measurement criteria](docs/project/measurement.md) define the proposed research
claims and experiments. Percentages remain hypotheses until measured; retain
baselines, seeds, hardware/configuration, raw results, failures, and limitations.
Historical test counts do not describe a new run.

## Completion criteria

Complete the project only when every [course checklist row](docs/project/course-requirements.md#requirement-coverage-and-acceptance-evidence)
has retained acceptance evidence. An engineer must be able to register inputs,
train/tune with LangChain suggestions, compare/register a version, inspect live
monitoring and diagnosis, query history with a real local model, and obtain
validated AI-generated snippets across the required independent services.
Docker, Kubernetes CI/CD, ownership, and recovery gates must pass. Quantitative
research claims and shared deployment hardening retain their own evidence.
