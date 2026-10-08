# Two-person course completion plan

- Status: awaiting review; work allocation only
- Date: 2026-10-08
- Source baseline: `840d51c9c683da0a58d6631477af8e16c5faf0dc` / `main`, after reset and pull from `origin/main`
- Request: inspect the synchronized repository and divide remaining work between two people.
- Human reviewer/approval: pending for this allocation and new designs; existing conversation approval remains valid within its recorded scope.
- Independent review: the other person reviews each change; additional review of ownership/state/resource arithmetic must be recorded. No independent review occurred during this inspection.

## Proposed behavior and purpose

Person A owns AI workflows and their evidence. Person B owns domain services,
monitoring observations, and deployment. Both deliver tests and documentation for
their own features, and review the other's changes. Complete all nine
[course requirements](../course-requirements.md#requirement-coverage-and-acceptance-evidence)
without rewriting the working classification/training/tuning backend.

Inspection confirms an existing FastAPI tracking/tuning API, MongoDB indexes,
serial CPU training/Optuna tuning, durable recovery, 13 typed HTTP tools, Docker,
and GitHub Actions checks. [The manifest](../../pyproject.toml) has no LangChain
dependencies; [the application](../../src/ml_pipeline_pro/main.py) includes both
domain routers in one process. [Compose](../../compose.yaml) runs API, worker,
scheduler, MongoDB, and Redis rather than independent domain APIs.
There are no tracked local-model/dialogue, monitoring, snippet-generation, or
Kubernetes implementations. [CI](../../.github/workflows/ci.yml) checks code/Compose/recovery
but has no Kubernetes deployment path. These are source findings, not new test
results. The [historical validation](../project-status.md#conversation-tool-validation)
records 211 local, 21 ordinary integration, and ten recovery cases at its own
revision; those suites were not rerun for this plan.

## Clarification and critique

Use Person A/B until names, specialties, availability, and a deadline are supplied.
Assume comparable availability and use dependency checkpoints rather than dates
or an unsupported claim of equal effort. B has more infrastructure work; at each
checkpoint transfer a whole unstarted task if needed, retaining one owner.
A's retrieval-evidence task can move between people without changing AI contracts.

Splitting whole roadmap milestones would leave AI diagnosis waiting on monitoring
and deployment waiting on every feature. Split monitoring at its evidence
boundary and start service design alongside conversation work. Keep one shared
repository/image and transaction-capable MongoDB deployment where practical;
independent databases or a new training engine add risk without satisfying an
additional course requirement. A full browser UI and automatic code execution
are unnecessary for the requested course demonstration.

The remaining design decisions are deliberate review tasks: B proposes routing,
service lifecycles, monitoring inputs/windows/thresholds/refresh acceptance,
test-cluster storage and deployment topology; A proposes snippet inputs/output,
supported APIs, validation, provenance, and diagnosis behavior when evidence is
missing. Both agree on interfaces before implementation. Record defaults,
failures, access, size/rate limits, and exact acceptance scenarios in those plans.
Model artifact/runtime selection and target-machine evaluation are still open
within the [approved conversation plan](2026-10-06-conversation-workflows-plan.md).
This allocation does not silently decide those contracts or expand that approval.

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | Every outstanding course row has an accountable owner and a deliverable. | The task and coverage tables below map C1-C9 to evidence. |
| F2 | Functional | The two people can work in parallel after agreeing on shared interfaces. | Reviewed routing/evidence contracts; AI tests use matching fixtures until B's services are available. |
| N1 | Reliability | Existing project access, idempotency, selection, ownership, artifacts, and recovery remain intact. | Existing and added fast, real-service, ownership, recovery, and replica-replay checks pass. |
| N2 | Resource/evidence | Inference, monitoring, and deployment have reviewed limits and retained real executions. | Model evaluation, measured dashboard timing, and CI-triggered cluster rollout evidence; skips/gaps remain visible. |

## Constraints and scope

Preserve `/api/v1` schemas, consistent errors/correlation IDs, project scoping of
referenced records, and submission keys. Select checkpoints/winners using
validation; fit preprocessing only on training rows and evaluate test data after
selection. Keep worker/trial concurrency at one.

Preserve the [same-transaction tuning parent write](../memory/tuning-parent-fence.md),
reserved configurations/IDs, original tuning deadlines, and
[training artifact preservation](../memory/evaluation-artifacts.md).
REST service separation must not replace fenced repository writes with separate
HTTP mutations. Preserve [upstream evidence metadata](../memory/conversation-response-evidence.md),
locked dependencies, secret redaction, and opt-in live-service gates.

Deliver the local course/test-cluster workflow. Paid model APIs, language-model
training, public hosting, person-level identity, immutable object storage,
retention/restore, arbitrary partition/load research, parallel training, and
quantitative resume claims remain separately tracked in the
[audit](../project-status.md#deployment-and-operational-gaps) and
[measurement roadmap](../../PLAN.md#measurement-and-reporting).
Local deployment still needs datasets/artifacts available to the correct pods
and hash-verified downloads; deferring object storage does not waive that test.

## Design

### Accountable tasks

| Task / owner | Deliverable and code boundary | Dependency / completion evidence |
| --- | --- | --- |
| A1 / Person A | Implement the already approved conversation slice: `conversation_*`, LangChain/ChatOllama adapter, persisted dialogue/actions, bounded history-based tuning suggestions, confirmation and grounding; own its tests and local-model setup/tutorial. | Can begin within existing approval. Real model plus scripted-model, transaction-race, lost-response/restart, and existing regression gates satisfy the approved plan. Record artifact digest/license, runtime and resource observations. |
| A2 / Person A | Write/review a snippet-generation design, then implement model-generated Python, supported import/API checks, syntax validation, redacted provenance, rejection and human review; own examples/tests/tutorial. | A1 supplies the model adapter. Deterministic validation and retained real-model snippets pass; unsupported output rejects. No automatic execution. |
| A3 / Person A | Write/review diagnosis behavior with B, then consume monitoring metric/log windows through typed read interfaces and generate LangChain summaries with evidence-linked checks/fixes. Own AI interpretation and adversarial/grounding tests. | Interface can be mocked after the joint contract; real completion waits for B2. A seeded issue produces a cited summary; missing labels/evidence and uncertain causes are explicit. |
| A4 / Person A | Plan and run representative MongoDB retrieval evidence; write the advanced optimization/history tutorial and AI portions of final onboarding. Own the standalone evidence harness rather than domain repositories. | Use B1's stable routes. Demonstrate saved parameters/versions/trials/metrics and query plans; define dataset, queries, seeds, cache conditions and budgets before runs, retain latency results without promising a speedup. |
| B1 / Person B | Write/review service extraction, then expose independently deployable model-management and tuning APIs and preserve the public routing entry point. Own app factories/lifecycles, routing, existing domain stores, queue/worker integration and affected service fixtures. | Design reviewed before extraction. Each domain starts separately; routed requests preserve scoping, errors, replay and the transactional child fence. Existing ownership/recovery gates pass. A1 can continue against the current public API meanwhile. |
| B2 / Person B | Write/review the independent monitoring REST service, sample observation producer, worker/service metrics, prediction/drift/quality history with label availability, metric/log evidence windows, Prometheus/Grafana dashboards and alert timing. Own persistence, instrumentation, dashboards and service tests/tutorial. | Joint evidence contract first; stable deployment integrates with B1. A running workload and seeded issue meet the reviewed update/alert interval. Match A3's fixtures; logs/health alone cannot close this task. |
| B3 / Person B | Containerize all domain services; add test-cluster Kubernetes manifests, resources/probes/storage/model configuration and exercised GitHub Actions deployment/smoke checks. Own Docker/Compose, deployment files and operations/verification instructions. | Skeleton design/setup can run early; final evidence waits for B1/B2 and A1-A3. CI triggers a real cluster rollout; stateless API replica/replay tests pass while one training worker remains serial. YAML alone is insufficient. |
| B4 / Person B | Assemble the clean-checkout course demo and evidence index, rerun combined service/recovery gates, and update the course checklist/status only from retained runs. | A reviews and executes the tutorial from a clean checkout. All C1-C9 evidence is linked; unavailable services/models, selected-case skips and unresolved review remain gaps. |

### Shared interfaces and file ownership

Agree on two contracts first: (1) a stable trusted `/api/v1` origin/routing map
with project, API-key, correlation and idempotency propagation; (2) a versioned,
project-scoped monitoring evidence response carrying record/window identity,
timestamps, observed values, label availability and safe log references. B owns
the service contract/fixture; A reviews it and owns the model-facing adapter.
Bounded missing/stale/failed evidence behavior belongs in the reviewed design.
The approved chat/tool protocol remains unchanged unless explicitly reapproved.

A owns `conversation_*`, proposed snippet/diagnosis modules, `tools.py`,
`tool_schemas.py`, and `tool_transport.py`. B owns domain/service modules,
`main.py`, `connections.py`, deployment files, CI and shared integration fixtures.
A supplies the chat-router/lifespan patch for B to integrate.
For `config.py`, `logging.py`, `pyproject.toml`, `uv.lock`, `.env.example`, and
shared documentation, announce the intended edit and let one person integrate
at a time. A integrates the initial LangChain dependency lock; B adds later
monitoring/deployment dependencies after rebasing. Never hand-merge a lockfile.

Use separate task branches from current `origin/main`, short reviewed commits,
and rebase before touching shared files. Each author runs relevant checks and
pushes every major completed change to `origin`; the other person reviews it.
New routes/config require README endpoint/config documentation and relevant
schema/repository/fixture/integration updates in the same change.

### Dependency checkpoints

1. **Agree and review:** assign names/time, B drafts extraction/monitoring contracts,
   A reviews and starts approved A1; A drafts A2. Human approval precedes each new
   design's implementation. Validate model feasibility early.
2. **First parallel delivery:** A1 conversation and B1 domain services, preserving
   today's public API. Integrate router/client lifecycle changes together and
   verify access, replay, transaction races and recovery.
3. **Second parallel delivery:** A2 snippets plus B2 monitoring; A3 can develop
   against the agreed evidence fixture. B prepares B3's cluster path. A4 runs
   against stable domain APIs when capacity allows.
4. **Join and demonstrate:** integrate A3/B2, complete B3 with every feature,
   then B4's clean-checkout tutorial and course evidence audit. Rebalance whole
   pending tasks if either person is waiting; retain explicit review ownership.

The critical dependencies are A1 -> A2; B2 + A1 -> A3; B1/B2 + A1-A3 -> final
B3 evidence; all feature/evidence tasks -> B4. No task requires concurrent training.

### Separately tracked follow-up

These audit/roadmap gaps also have owners, but do not expand course acceptance.
Design/review them before implementation; shared-use controls precede shared use.

| Owner | Remaining work | Gate |
| --- | --- | --- |
| A | Person-level identity/roles and project-key lifecycle; B integrates TLS and authenticated dependencies. | Authorization/secret regressions and reviewed deployment access policy. |
| B | Immutable datasets, artifact storage/retention/deletion, migrations, coordinated backups and restore. | Restore resolves retained records and hash-valid files; preserve current CSVs meanwhile. |
| B | Worker/scheduler probes, concurrent-load and network-partition evidence; A reviews replay/claim invariants. | Retain serial execution until reviewed evidence supports a concurrency change. |
| A | Broader training adapters and standalone cancellation if requested, generated-code isolation if execution is requested, dependency/TestClient warning cleanup; B owns additional platform CI coverage. | Separately reviewed contracts and meaningful compatibility/failure checks. |
| A | Retrieval/tuning/diagnosis/coding-efficiency measurements; B owns workflow-throughput/load harnesses. | Reviewed comparable baselines, retained raw runs and limitations before quantitative claims. |

## Acceptance and verification

| Course row | Accountable owner(s) | Closing evidence |
| --- | --- | --- |
| C1 environment | A: dependencies/model setup; B: images | Clean locked installation including LangChain; documented local runtime works. |
| C2 services | B1/B2 | Three independent REST services and preserved domain/transaction boundaries. |
| C3 dialogue | A1 | Real local-model guided dialogue, missing-input handling, history and grounding. |
| C4 MongoDB | B1: regressions; A4: retrieval evidence | Existing schemas/indexes plus saved-record retrieval/query evidence; performance remains measured, not asserted. |
| C5 tuning | A1; B1 reviews invariants | User-confirmed history-grounded suggestions; serial optimizer, ownership, recovery and validation selection remain passing. |
| C6 monitoring | B2: observations/dashboard; A3: summaries | Reviewed live update/alert timing, seeded issue, evidence-linked LangChain diagnosis/fixes. |
| C7 Python generation | A2 | Real generated snippets, validation/provenance, rejection and review demonstrations. |
| C8 tests/deployment | B3/B4; A owns AI tests | Rebuilt images, fast/service/recovery checks, exercised CI/CD Kubernetes rollout/smoke and supported API scaling. |
| C9 onboarding | Both; B4 assembles, A verifies | Clean-checkout end-to-end tutorial and advanced optimization examples. |

Each application change runs the full [fast gate](../verification.md#fast-checks):
`uv sync --locked --extra training`, Ruff lint/format checks,
`uv run --locked --extra training pytest -m "not integration" --cov`, and
`uv pip check`. Packaging changes also run `uv build`.
Affected MongoDB/queue/worker/ownership/recovery changes run
[ordinary integration](../verification.md#ordinary-integration) with **both**
`MLPP_RUN_INTEGRATION=1` and `MLPP_RUN_WORKER_INTEGRATION=1`, and the
[isolated recovery suite](../verification.md#run-the-suite) serially with the
separate `MLPP_RUN_RECOVERY_INTEGRATION=1` gate. Preserve assertions and explain
any changed test against its requirement.

A1 retains the approved ten-scenario opt-in real-model evaluation and budgets;
new snippet/diagnosis evaluations extend it under their own reviewed plans.
Model installation/download does not happen in ordinary CI. B2 must establish
timing/threshold/capacity acceptance before measuring it; A4 must establish a
benchmark workload before runs. B3 records rollout image/source IDs, probes,
storage accessibility, replica count and replay behavior. Retain JUnit, safe
failure/state evidence, model/config identity and measured results in a shared
archive or CI; ignored local artifacts alone do not establish shared evidence.

The non-author reviews transaction predicates, state transitions, retries and
byte/token/rate arithmetic, preferably with an additional different-vendor
reviewer where available. Record reviewer, submitted revision, findings and
resolutions; disclose unavailable review without calling self-review independent.

## Risks and rollback

B's workload and shared-file contention can delay deployment: prepare the
cluster path early, review small slices, and transfer complete pending tasks
instead of dividing ownership inside one module. Model tool-calling feasibility
is an early A1 gate; inability to run it remains an acceptance gap.

Keep extraction and feature commits separate. Follow each feature's reviewed
disable/revert procedure, retain durable records and hash-valid artifacts, and
do not automatically replay unknown actions. Revert deployment/routing to a
known-compatible image/config without deleting MongoDB or volume contents.
Review mixed-version compatibility/migrations before rollout.

## Human review and approval

This request authorizes repository synchronization, inspection, and preparation
of the allocation. It does not approve new feature designs. The October 7
conversation approval remains recorded in its existing plan. Names, schedule,
allocation approval and new-design approvals remain pending; record reviewer,
date, scope and requested changes here or in the relevant feature plan.

## Implementation outcome

Planning artifact only; course features remain outstanding. Source inspection
used Windows/PowerShell at the baseline above. Reset/pull reached `origin/main`;
there were zero local-only commits. Unfinished tracked/untracked conversation
edits were removed from the working tree and preserved in named local stash
`Before requested origin reset 2026-10-08` (`4b5bfc62`). Ignored local files and
service volumes were retained. Stashed work is excluded from coverage and must
be reviewed and verified if reused for A1.

Preparation checks on October 8, 2026 (Windows/PowerShell, Python 3.11.5) passed:
17 Markdown documents, 204 local links/anchors, two Python fences, 18 PowerShell
fences, four Python example scripts, all nine template sections, all nine course
rows and all eight accountable tasks. Source checks confirmed 13 tools, the five
Compose services, absent outstanding modules/dependencies/deployment, existing
conversation approval and unchanged application sources. `git diff --check`
passed. Raw preparation evidence is local in ignored
`artifacts/two-person-plan-validation/`; it is not course acceptance evidence.

No application suites or independent implementation review were run for this
documentation-only change; no test assertions changed. Completion commit/push
is reported in the task response and Git history. Feature outcomes remain pending.
