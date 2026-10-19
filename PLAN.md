# ML Pipeline Pro Roadmap

## Objective and scope

Deliver the [course requirements](docs/project/course-requirements.md): model
management, bounded Bayesian tuning, monitoring, LangChain conversation with a
local pre-trained model, and AI-generated Python snippets. Separate domain REST
services, Docker, Kubernetes, CI/CD, tests, and onboarding are required.
Paid model APIs and custom language-model training are outside the required scope.

The **minimal class demo has retained evidence for all nine requirements**.
October 14 CPU-laptop reproduction remains unsuccessful: the latest dialogue and
snippet gates fail, and the walkthrough times out before its first tool read.
The October 14 Ryzen 7 / RX 9070 run passes all ten/seven original AI scenarios
and the full rebuilt-service tutorial in 20.35 seconds after startup/warmup.
See the [workstation evidence](docs/evidence/2026-10-14-rx9070-walkthrough/README.md),
archived October 15. CPU-laptop acceptance and its observed timeout overrun remain
unresolved; retain the existing limits and distinguish the presentation machines.

The [October 19 plugged-in laptop rehearsal](docs/evidence/2026-10-19-laptop-rehearsal/README.md)
passes backend and independent monitoring checks, but the full AI walkthrough
still fails at its first inspection. Independent diagnosis and Python draft
attempts also time out. That rehearsal used the default timing profile. Jacob
subsequently approved the [five-minute implementation](docs/plans/2026-10-18-laptop-deployment-readiness-plan.md)
on October 19; coordinated budgets and timing instrumentation are implemented,
with [new-profile laptop evidence](docs/evidence/2026-10-19-laptop-five-minute/README.md)
now retained. The first inspection passes in 210.532 seconds, but a liveness-triggered
gateway restart breaks the next turn before its reply deadline. A later
[fresh AC model run](docs/evidence/2026-10-19-laptop-awake-gates/README.md) passes
all ten dialogue and seven snippet scenarios; the earlier interrupted run remains
retained. All five implementation CI jobs pass. Full deployed laptop
acceptance remains open. Jacob approves the [deployment-health follow-up](docs/plans/2026-10-19-laptop-deployment-health-plan.md),
implemented as `bf07213`: all 647 fast/63 ordinary cases and five CI jobs pass.
The [new full walkthrough](docs/evidence/2026-10-19-laptop-gateway-health/README.md)
still fails on its first AI request after 144.094 seconds; even local gateway
liveness stalls and Kubernetes restarts it. The server saves the turn within
167.506 seconds. Resource attribution remains incomplete; the
[bounded diagnostic plan](docs/plans/2026-10-19-laptop-resource-diagnosis-plan.md)
awaits review. No further timeout/resource/model changes are made.

The [October 13 midterm scope](docs/project/midterm-scope.md) is the current
target: all nine requirements in one minimal local demonstration. Jacob approved
the [delivery plan](docs/plans/2026-10-13-midterm-delivery-plan.md); its bounded
architecture/workflows replace the broader immediate ambitions.
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
The opt-in pinned 7B guided profile passes the original ten-scenario gate,
uses actual saved history/current budgets and preserves exact confirmation.
Separate boundary review, human examples and a clean-checkout walkthrough are
recorded in [delivery evidence](docs/evidence/2026-10-13-midterm-delivery/README.md).
Earlier native failures and local timing variation remain retained. The
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

**Status:** Minimal scope demonstrated: independent monitoring API, immutable
observations, measured CPU workload, Prometheus threshold/15-second scraping,
Grafana dashboard and evidence-linked local-model advice. Human usefulness reviewed.
Wider drift, notification routing and automatic fixes remain deferred.

**Acceptance:** A separate monitoring REST service ingests sample observations,
exports operational and model metrics to Prometheus, and updates Grafana and alerts
within a declared/measured interval. Use one running sample workload, one dashboard
and one seeded threshold issue with explicit label availability and bounded
metric/log evidence; advanced drift is deferred. LangChain/local-model summaries cite evidence and propose
checks or fixes; inferred causes remain labelled as hypotheses.

### 6. Generate reviewable pipeline code

**Status:** A2's approved generation/validation and saved-draft implementation
exists. All seven original local-model cases pass on the final guided 7B run,
with four validated draft profiles and no execution. Human review of retained
examples and separate boundary review are recorded in [delivery evidence](docs/evidence/2026-10-13-midterm-delivery/README.md).
Historical failures remain in the [A2 outcome](docs/plans/2026-10-08-person-a-snippet-generation-plan.md#implementation-outcome).

**Acceptance:** Conversational requests generate Python snippets through
LangChain/local inference. Record assumptions and model/prompt provenance; check
syntax, supported imports, API use, and secrets; reject unsupported output and
present drafts for human review. Static templates alone do not satisfy this
requirement. Retain real-model examples and deterministic validation. Execution is
optional and, if enabled, requires explicit review and resource/network isolation.

### 7. Prepare deployment and onboarding

**Status:** Three independent domains, local Docker/Kubernetes deployment,
actual two-pod replay, startup recovery and clean-checkout onboarding pass.
Final remote deployment/ordinary/recovery [successful implementation CI](https://github.com/JacobHermsmeyer21/ML-Pipeline-Pro/actions/runs/38505646188) passes with the measured CPU
reservation correction. Shared/public production controls retain their separate scope.

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

Jacob requested a local dashboard by 11 pm ET on October 19, with CSV datasets,
agent-guided training and attractive embedded Grafana graphs. The
[dashboard plan](docs/plans/2026-10-19-local-dashboard-plan.md) awaits human review;
it is not implementation approval or completion evidence. Its desktop scope is
separate from the laptop investigation below.

Jacob confirmed October 18 that the October 20 presentation will use the CPU
laptop. Reliable AI on that machine is the immediate blocker; workstation success
does not establish laptop readiness. The [current audit](docs/project/2026-10-18-repo-audit.md)
maps delivered Person B tasks and the remaining two-day priorities.

1. Preserve passing ownership, artifact, idempotency, and serial recovery gates.
2. Retain completed deployment CI and its prior failed attempts with source identity.
3. Reproduce the bounded class preflight before presentation; preserve resource limits.
4. Keep broader production/research work deferred beyond the minimal all-nine demo.

The [two-person completion plan](docs/plans/2026-10-08-two-person-course-completion-plan.md)
records historical proposed owners/handoffs. The October 13 delivery plan now owns
approved midterm scope; broader unapproved A3/A4 ambitions are deferred.
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
Large retrieval workloads and research measurements are deferred; demonstrate
saved-record retrieval/index use without speedup claims.

## Completion criteria

Complete the project only when every [course checklist row](docs/project/course-requirements.md#requirement-coverage-and-acceptance-evidence)
has retained acceptance evidence. An engineer must be able to register inputs,
train/tune with LangChain suggestions, compare/register a version, inspect live
monitoring and diagnosis, query history with a real local model, and obtain
validated AI-generated snippets across the required independent services.
Docker, Kubernetes CI/CD, ownership, and recovery gates must pass. Quantitative
research claims and shared deployment hardening retain their own evidence.
