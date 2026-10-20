# Project audit and development status

## Current snapshot: October 19, 2026

Documentation reconciled against application revision `28c22fb` on `main`.
This refresh changes documentation only; test counts below come from retained
executions, not a new application test run. The
[course checklist](course-requirements.md) distinguishes minimal delivery from
machine-specific acceptance, independent review and production/research work.

The local browser workspace now supports raw CSV preparation with editable
training-fitted encoding/classes and stratified splits, saved column-subset
versions, serial classification/tuning, verified artifacts/model versions,
conversations/confirmed actions/drafts, embedded Grafana and permanent
dataset/classifier deletion. Model-management, tuning and monitoring are separate
REST services sharing MongoDB transactions, Redis and storage. Deletion preserves
shared inputs and conversation/draft history; column editing preserves retained
cells, row order, splits and transforms in a new immutable version.

The latest combined feature verification records **740 fast, 104 ordinary and ten
isolated recovery cases passing**, plus five real browser-driven worker runs,
artifact checks and uncertain-save/parent-deletion recovery. See
[column evidence](../evidence/2026-10-19-dataset-columns/README.md). Separately,
[deletion evidence](../evidence/2026-10-19-permanent-deletion/README.md) covers
21 transaction/process cases, a 125-run cascade, four process-death boundaries
and actual shared-volume native-lock exclusion. Independent review of these
boundaries and human usefulness review of the completed dataset controls remain
outstanding. The subsequent `28c22fb` change is dashboard markup cleanup; the
retained application counts belong to the preceding implementation tree.

AI acceptance remains machine/profile-specific. The
[October 19 RX 9070 desktop run](../evidence/2026-10-19-desktop-demo/README.md)
passes original ten/seven gates and the bounded walkthrough in 21.953 seconds,
excluding startup/warmup. The
[CPU-laptop standalone gates](../evidence/2026-10-19-laptop-awake-gates/README.md)
pass ten/seven with the five-minute profile and Jacob's acceptance of examples.
Its [bounded Kubernetes walkthrough](../evidence/2026-10-19-laptop-gateway-health/README.md)
still fails during gateway health loss/restart. Two later
[unbounded direct-AI diagnostics](../evidence/2026-10-19-laptop-unbounded/README.md)
pass complete workflows in 789.906/641.016 seconds with application probes removed;
the slowest replies exceed the finite 270-second turn window. Normal settings
and probes were restored. Finite-profile/full gateway acceptance, real under-load
expiry and resource-cause attribution remain open.

## Where development stands

| Milestone | Current delivered scope | Remaining scope |
| --- | --- | --- |
| 1. Development foundation | Locked Python/uv environment, FastAPI, MongoDB replica set, Redis/Celery and checks | Wider platform/runtime compatibility and operational hardening |
| 2. Reproducible experiment tracking | Serial CPU classification, training-fitted preparation, immutable managed datasets/column versions, artifacts, evaluated versions and permanent erasure | Standalone cancellation, scheduled retention, migrations/restore and broader adapters; direct operator files must remain unchanged |
| 3. Bounded tuning | Serial Bayesian TPE, validation selection, reserved identities/deadlines, transactional parent ownership and controlled recovery | Concurrent-load/partition evidence and any later parallel dispatch |
| 4. Conversational workflows | Local LangChain/Qwen, grounded reads/history, guided gates, exact confirmed actions and saved replay | Bounded deployed laptop acceptance, remaining independent boundary review and wider intent/runtime reliability |
| 5. Monitoring and diagnosis | Separate API, actual observations, bounded summaries, 15-second Prometheus/Grafana and evidence-cited local-model advice | General drift, durable aggregates/alert lifecycle and automatic remediation |
| 6. Reviewable code generation | Four model-generated Python profiles, AST/API validation, saved provenance/replay and reviewed examples | Review every new draft; generated-code execution remains outside delivered scope |
| 7. Deployment and onboarding | Three domain APIs, Docker/Compose, kind/Kubernetes smoke/replica replay, CI/CD, tutorials and local browser workspace | Complete bounded laptop AI workflow, final dataset-control reviews and shared-production controls |

These are delivered capabilities with stated limits, not a percentage estimate or
production-readiness certification. [Plans](../../PLAN.md#implementation-milestones)
retain their reviewed design/milestone scope. Dated records below preserve the
earlier missing features and failures; the snapshot above supersedes their
present-tense status claims where later evidence exists.

## Dated implementation and audit history

October 19 column editing: the approved dashboard/API change adds input selection
before encoding and **Edit columns** for saved numeric/raw-prepared datasets.
Edits create new versions with unchanged retained cells, labels, split membership
and frozen transforms. All 740 fast, 104 ordinary and ten isolated recovery cases
pass; Chrome verifies five real worker runs, uncertain-save recovery and training
after parent/child deletion on shared storage. The existing local dashboard is
updated. Independent review and human usefulness review remain outstanding.
[Evidence and boundaries](../evidence/2026-10-19-dataset-columns/README.md) do not
close other course or CPU-laptop AI gaps.

October 19 raw CSV improvement: the approved preparation plan adds original-file
import, editable categorical encoding/class IDs and automatic stratified 70/15/15
splits. Actual browser controls train the unchanged drug200 with both default and
edited mappings; saved recipe hashes, custom tuning/final evaluation, agent and
monitored inference are verified. All 710 fast, 77 ordinary and ten isolated
recovery cases pass without selected skips. Human usefulness/independent boundary
review remain outstanding. [Evidence and limits](../evidence/2026-10-19-dataset-preparation/README.md)
supersede the numeric-only dashboard limitation, not historical laptop/course gaps.

October 19 desktop dashboard: the approved prototype is implemented as a working
local workspace at `/dashboard/`, with scoped CSV uploads/shared worker storage,
training/results/artifact/version controls, local-agent history and exact decisions,
reviewable Python drafts and real embedded Grafana graphs. All 684 fast, 75
ordinary integration and ten isolated recovery cases pass without selected skips.
Chrome verifies the real dataset-to-model journey, uncertainty/double-click/project
boundaries, graph/summary automatic refresh and both desktop layouts. Jacob approves
the visual direction. Independent boundary review and a separately executed full
usability checklist remain outstanding. [Evidence and limits](../evidence/2026-10-19-dashboard/README.md)
are separate from the laptop runs below; no broader course completion is claimed.

October 19 diagnostic direction: Jacob requests health checks stop interrupting
work and one or two no-limit runs to observe completion time. The
[diagnostic design](../plans/2026-10-19-laptop-unbounded-diagnostic-plan.md) records
that intent. Jacob approved the written unbounded-ownership/direct-AI design with
"go for it". Implementation `1152aa8` passes 661 fast, 73 ordinary integration
and all 10 isolated recovery cases, with no selected skips, plus all five CI jobs.
Both [complete unbounded diagnostic workflows](../evidence/2026-10-19-laptop-unbounded/README.md)
pass on clean `1152aa8` in 789.906 and 641.016 seconds. Their slowest replies,
276.594/273.719 seconds, exceed the former 270-second turn but stay below the
300-second client. Both exact proposal/draft replays and confirmed bounded tuning
pass; generated Python remains unexecuted and new output quality awaits human
review. Marked-null saved turns complete with parent fencing; no container restarts
across the two runs. Background infrastructure readiness failures still occur.
AI delivery uses verified direct API origins with application probes removed,
so finite-profile/full gateway acceptance and live expiry remain open. Normal
five-minute settings/probes are restored; records/artifacts remain preserved and
the temporary wake request is released. The fixed-setting resource investigation
is deferred, never approved or executed; these timings do not prove a resource
cause, a latency upper bound or a need for a client ceiling above five minutes.

October 19 health follow-up: Jacob approves the local gateway-health plan. Implementation
`bf07213` passes 647 fast and 63 ordinary integration cases, real nginx negative
checks, preserved-data node restart and all five implementation CI jobs. The
[new live demo](../evidence/2026-10-19-laptop-gateway-health/README.md) still fails
on its first AI inspection after 144.094 seconds. Local `/gateway-live` also stalls
and Kubernetes orders a restart. The server persists a tool-transport-error reply
after 167.506 seconds, below the original 270-second deadline. N1/N3 remain failed;
new ten/seven reruns stop before execution under the approved fail-stop condition.
Earlier complete standalone model passes and human acceptance remain distinct.
Resource observations show host memory and node scheduling pressure, with missing
worker/VM CPU attribution and large gaps; no OOM or specific resource cause is
proved. Budgets, model/thread/resources/API probe thresholds remain unchanged.
The [next diagnostic plan](../plans/2026-10-19-laptop-resource-diagnosis-plan.md)
awaits approval; full laptop/course and real under-load expiry acceptance stay open.

Later October 19, after Jacob reconnects AC and requests continuation: the original
ten conversation and seven snippet scenarios all pass on the CPU laptop with the
five-minute profile. Maximum complete replies are 184.875 and 229.219 seconds.
The fresh full gates run on clean `dbc9a86`; all 54 common source/harness/lockfile
hashes match the preceding implementation. AC is connected at both ends of each
gate, neither execution window intersects recorded sleep, and both runners end
idle. Five generated drafts pass validation and are never executed. Jacob reviews
and accepts the saved conversation examples and drafts on October 19: "ive reviewed,
looks good. what is next". See [fresh evidence and exact outputs](../evidence/2026-10-19-laptop-awake-gates/README.md).
The earlier sleep-interrupted gate and failed deployed walkthrough below remain
retained. Full deployed laptop acceptance, gateway-health remediation and live
under-load deadline-expiry evidence remain outstanding.

October 19 five-minute laptop rerun on clean `533a2ed`: the correct first
inspection passes in 210.532 seconds. The complete Kubernetes walkthrough fails
on the comparison/proposal turn: liveness-triggered gateway termination breaks
client delivery after 132.937 seconds, before the selected reply windows expire.
The serving API persists an honest internal transport-error reply, with no facts,
proposal or submission. Broader probe/DNS delays have no confirmed resource cause.
Backend smoke, two-pod replay, preserved-record/artifact node restart and all five
implementation CI jobs pass; original cold-rollout/import failures remain retained.
A separate fixture dialogue gate passes eight cases before Windows sleeps during
the ninth; that suite fails/incompletely records the ninth, the tenth is unrun,
and snippets remain unrun. Sleep-inclusive timings are not active CPU benchmarks.
See [the complete evidence](../evidence/2026-10-19-laptop-five-minute/README.md).
The five-minute implementation is delivered; complete laptop and live-expiry
acceptance remain open. The [deployment-health plan](../plans/2026-10-19-laptop-deployment-health-plan.md)
was subsequently approved and implemented; its later failed live acceptance is
recorded above. Resource settings remain unchanged.

October 19 five-minute profile implementation: Jacob approved the
[existing design](../plans/2026-10-18-laptop-deployment-readiness-plan.md). The
opt-in profile coordinates 240-second model, 270-second turn, 300-second client and
310-second gateway bounds; defaults, ownership and semantic gates remain unchanged.
All 644 full fast cases and 23 final focused cases pass; package build, lint/format
and dependency compatibility pass. All 63 ordinary integration cases and a fresh
complete ten-case isolated recovery run pass. The preceding recovery run retained
one Docker CLI restart timeout; its unchanged boundary also passes separately,
without an assertion or timeout change. The underlying stall cause is unresolved.
Separate same-vendor source review identified
and resolved Kubernetes backend DNS rendering and evaluation continuation after
failure. Deployment, live cancellation and complete laptop acceptance are
distinguished in the later evidence above; fast checks alone do not verify them.

October 19 plugged-in presentation-laptop rehearsal on clean `e605e24`: the
existing deployed sources match the checkout and all ten services are running.
Training, three-trial tuning, versions/submission replay and independent measured
monitoring pass. The complete walkthrough fails on its first AI inspection:
HTTP 504 after 87.885 seconds, with an interrupted saved turn and no tool reads.
Independent diagnosis returns 503 / `chat_timeout` after 30.188 seconds; a Python
draft request times out at the client after 90.187 seconds with no saved snippet.
Prometheus retains the version's issue and firing alert; Grafana serves its
dashboard. Runner cancellation/idle is observed, but timeout-overrun attribution
and full laptop acceptance remain open. No application, timeout or model changes
were made; the five-minute profile is still planning only. See the
[complete rehearsal record](../evidence/2026-10-19-laptop-rehearsal/README.md).

October 18 repository audit against `cb67bb8`: Jacob confirmed the October 20 demo
will use the CPU laptop. Minimal Person B services/monitoring/deployment/tutorial
work is already implemented; reliable laptop AI is the immediate blocker. Fresh
598 fast, 63 ordinary and ten serial recovery cases pass without selected skips;
lint/format/dependency checks and all five remote CI jobs also pass. The
[audit and priorities](2026-10-18-repo-audit.md) and
[new verification evidence](../evidence/2026-10-18-repo-audit/README.md)
distinguish current checks from earlier laptop failures/workstation acceptance.

October 15 evidence update, for the October 14 run on clean `add6862`: the Ryzen 7
7800X3D / RX 9070 workstation passes all ten original dialogue scenarios, all seven
snippet scenarios, and the complete rebuilt-service AI walkthrough in 20.35 seconds
after startup/warmup. The requested F1 fact, history-based proposal, explicit
bounded approval, successful tuning, saved draft/replay and monitoring diagnosis
all pass. Prometheus detects the seeded issue and Grafana serves the dashboard.
See the [retained workstation run](../evidence/2026-10-14-rx9070-walkthrough/README.md).
This establishes fresh-record live correction/tutorial acceptance on that machine;
the CPU-laptop timeout mechanism, original-record reproduction and separate
boundary review remain open. New generated outputs still require human review.

October 14 branch reconciliation: the working branch now includes the three
published commits through `377f64b`; `origin/main` is already an ancestor. Four
overlapping local/published edits were reconciled, preserving the published
inspection guard and its project/evidence checks. The evaluation observers now
retain host fact references before the SDK drops tool-message names, while still
checking the exact transmitted schema. See the [reconciliation record](../evidence/2026-10-14-branch-sync/README.md)
for new checks, merge decisions and the current handoff.

October 14 delivery assessment (superseded by the later records above): the
bounded backend, three services, monitoring,
generated-code pipeline and deployment path are implemented, with retained
October 13 acceptance and later passing service/CI evidence. Reliable AI operation
on the CPU laptop remains outstanding: the latest full gates pass only 2/10
dialogue and 0/7 snippet cases, and the post-reboot walkthrough times out before
its first tool read. Timely timeout enforcement under that load needs diagnosis.
The workstation run above now supplies successful fresh-record real-model
walkthrough evidence; original-record reproduction and separate boundary review
remain open. Production hardening and larger research
claims remain deferred. Historical inventories below retain their dated scope.

October 14 correction: Jacob approved the
[requested inspection facts plan](../plans/2026-10-13-requested-inspection-facts-plan.md)
after a later demo omitted a requested structured fact. The narrow guided schema
and decoded-reply guard are implemented with scripted boundary coverage;
[new verification evidence](../evidence/2026-10-14-requested-inspection-facts/README.md)
keeps real-service/model acceptance and separate review outstanding. The earlier
delivery evidence below does not verify this correction or guarantee every demo run.

Later October 14: the correction's complete remote CI succeeds, including 63
ordinary integration cases without skips. User-authorized laptop prerequisite
installation is complete; Windows requires a restart to activate WSL virtualization.
The pinned 7B local gates on this CPU laptop fail (2/10 dialogue, 0/7 snippets).
[Setup and retained failures](../evidence/2026-10-14-prerequisite-setup/README.md)
keep these limits separate from prior GPU success and passing scripted/service CI.

After the restart, rebuilt Docker services and **63 local ordinary integration
cases pass without skips**. Direct backend smoke and measured monitoring also pass.
The real AI walkthrough times out at its first inspection; the saved turn is
interrupted with no tool reads. Model prompt evaluation takes 113.524 seconds on
CPU; the API's late 504 also leaves timeout enforcement under these conditions
unverified. [Post-reboot evidence](../evidence/2026-10-14-post-reboot-validation/README.md)
retains the failure and separates it from successful backend checks.

Current minimal delivery (October 13): three independent APIs, guided local 7B,
Bayesian tuning/history, generated Python, measured monitoring and Docker/Kubernetes
are implemented. Final original ten/seven model gates, human examples, 570 fast,
63 ordinary and ten serial recovery cases pass. Locked dependency/build checks pass.
Fresh checkout/environment/storage completes the real AI walkthrough; Kubernetes
also passes actual AI and direct submission replay through both individual API pods.

The tested MongoDB startup failure now recovers through its bounded process probe,
preserving records/configuration. Remote deployment diagnostics exposed insufficient
CPU reservation capacity; the corrected 600m application budget retains limits,
all service/replica counts and every test gate. Final [successful implementation CI](https://github.com/JacobHermsmeyer21/ML-Pipeline-Pro/actions/runs/38505646188) passes on a node with two allocatable CPUs.
See [delivery evidence](../evidence/2026-10-13-midterm-delivery/README.md), the
[combined guide](../guides/midterm-walkthrough.md) and [course checklist](course-requirements.md).

Earlier model slowdowns/failures, rejected 3B candidate, startup attempts and remote
failures remain historical evidence. No timing guarantee, larger-scale speedup,
universal model reliability or production readiness is claimed. Jacob's approved
[midterm scope](midterm-scope.md) defers broader unapproved A3/A4 features.

**Audit date:** October 6, 2026. **Audited baseline:** `0e37e6e17614ae146e75a576c1f60c885ee79cd0` on `main`. **Package version:** `0.1.0`.

The dated audits below retain their original coverage/failures; the current delivery
summary above supersedes their missing-feature status only within the reviewed
minimal scope. Historical test counts do not describe the final run.

**Documentation source check, October 8, 2026:** baseline `c28ae06`. The
conversation workflow design was approved October 7, but that checkout still had
no LangChain dependencies, model adapter, chat routes, or dialogue/action store.
The dated validation below is historical; no application suite was rerun for this
documentation consolidation. [Verification](../guides/verification.md) owns execution setup;
[workflows](../guides/workflows.md) owns runnable tutorials.

ML Pipeline Pro has a working local classification experiment and tuning backend. The initial feature scope of milestones 1-3 is implemented and its existing tests pass. The full MVP is still incomplete: conversational access, monitoring, generated code, and shared-deployment readiness remain. The baseline audit's recovery ownership bugs are fixed, and controlled process-loss/dependency-outage validation is delivered. Concurrent-load/partition validation and storage lifecycle work remain open.

The baseline audit reviewed the tracked application modules, examples, tests/fixtures, dependency manifest/lockfile, Docker/Compose configuration, CI, and documentation. It also checked the saved validation evidence and local demo manifests, ran the baseline suites/demos, inspected the running services, and probed ownership boundaries in a disposable MongoDB database. That audit changed documentation only; subsequent application fixes and their checks are documented in [ownership fix validation](#ownership-fix-validation).

## Course scope alignment

On October 6, 2026 the user supplied the nine
[course implementation instructions](course-requirements.md) and requested
documentation correction against source baseline `ba6334f`. The course target
uses LangChain with local pre-trained inference; a paid external model API or
training a code language model is not required. The unapproved OpenAI draft was
revised in the [conversation plan](../plans/2026-10-06-conversation-workflows-plan.md);
per-action confirmation and retained dialogue/evidence were approved October 7.
The implementation slices below retain their separate evidence and open gates.

The final course workflow requires three independently deployable domain REST
services, LangChain guidance/suggestions, live monitoring/visualization with
generated summaries and proposed fixes, AI-generated Python snippets, and
Kubernetes with exercised deployment CI/CD. The existing one-API Compose stack,
logs/health, and checked-in examples do not establish those requirements. See the
[coverage checklist](course-requirements.md#requirement-coverage-and-acceptance-evidence)
for evidence needed to close all nine rows. Commercial shared-production
hardening and proposed resume improvement percentages are separate work.

This correction changes documentation only. Existing validation below retains
its original dates/revisions; it is not a new application run or proof of course
completion. Feature implementation still requires explicit review of its plan.

Person A's October 8 [conversation foundation](../guides/conversation-development.md) adds
strict request/public-action/model-reply schemas, canonical finite-JSON
fingerprints, the injected model interface/native tool descriptions, approved
chat settings, and locked LangChain dependencies. The next A1 slice adds a local
LangChain/Ollama adapter and SDK/HTTP boundary tests. The durable store now has
real-MongoDB claim/replay/takeover coverage. The bounded host loop grounds supplied
API facts and preflights saved proposals. Authenticated routes and exact-action
dispatch now add parent-fenced decisions, bounded same-key retries and killed-chat-
process recovery. October 9-10 installed-artifact token verification is retained;
all live acceptance attempts failed. Existing tracking/tuning contracts and worker
behavior are preserved.
Validation for these slices is recorded in the
[approved plan's outcome](../plans/2026-10-06-conversation-workflows-plan.md#implementation-outcome);
the earlier counts below remain historical.

## Implemented behavior and limits

Historical October 6 backend inventory follows; current delivered capabilities
are summarized above and in the [architecture reference](../reference/architecture.md).

| Area | Verified implementation | Current boundary |
| --- | --- | --- |
| API foundation | FastAPI app factory, versioned domain/conversation routes, validated settings, async clients, consistent errors/correlation IDs, JSON logs and redaction | One application; no monitoring routes or verified live-model setup |
| Dataset registration | Local CSV validation, SHA-256, class/feature metadata, explicit nonempty splits | References existing files; no upload, immutable copy, remote URI, or split generation |
| Data format | 1-128 numeric feature columns; contiguous training class IDs starting at zero; 2-64 classes | No categorical/text/image features, regression, missing-value imputation, or framework selection |
| Model registration | Project-scoped PyTorch classification MLP records | One hidden layer; model registration stores metadata, not a trained model |
| Training | CPU Adam training, fixed seed, train-only normalization, first best validation-F1 checkpoint, final test accuracy/macro F1 | Single adapter; 1-500 epochs, 1-600 seconds per training attempt; cooperative checks |
| Experiment workflow | Idempotent submission, filtered/paginated reads, same-dataset validation comparison, artifact download, explicit version registration | No standalone cancel/delete/update API, inference server, deployment, or automatic promotion |
| Tuning | Seeded Optuna TPE over learning rate/batch size/hidden units; maximized validation F1 or accuracy; persisted reservations/trials | 1-50 trials, 2-600 seconds overall, concurrency exactly 1; no arbitrary parameters or minimization |
| Selection and evaluation | Test labels excluded from preprocessing/checkpoint/trial selection; only the selected tuning checkpoint receives final holdout metrics | Final evaluation can be skipped when budget expires; registration is then blocked |
| Job reliability | Durable dispatch state, unique submission/trial identities, atomic parent claims, transactional child ownership, leases/heartbeats, bounded attempts, replay of saved training; controlled worker kills and dependency restarts recover through Beat | Serial CPU scope; concurrent load and arbitrary partitions remain untested |
| Artifacts | Atomic writes under project/experiment/attempt directories; downloads verify hash and size | Local storage only; no cleanup, retention, backup, or remote storage adapter |
| Project access | Required project header, project-scoped references, optional constant-time API-key checks; keys mandatory in production settings | Development without keys trusts caller-selected projects; no user identity, roles, or key lifecycle |
| Local deployment | Non-root app image; API/worker/Beat/MongoDB/Redis; localhost ports; persistent volumes | Development configuration; CPU/memory/concurrency limits apply to the worker |

The checked-in example has 120 synthetic rows: 80 train, 20 validation, and 20 test. Passing accuracy/F1 checks on this deliberately small dataset demonstrate workflow behavior, not real-world model quality.

Training and tuning share the `training` queue. Beat schedules recovery every 15 seconds, but the recovery task runs in the same worker that handles training. Queue wait and scheduler-task wait are outside the training/tuning runtime budgets. Under load, recovery cannot be assumed to happen within 15 seconds.

## Architecture and durable records

The October 6 deployment was modular rather than separate domain services. This
inventory describes that baseline; the current three-service topology and added
dataset/lifecycle/conversation/monitoring records are in the
[architecture reference](../reference/architecture.md).

- [Tracking API](../../src/ml_pipeline_pro/api.py) and [tracking store](../../src/ml_pipeline_pro/tracking.py) own datasets, models, experiments, and model versions.
- [Tuning API](../../src/ml_pipeline_pro/tuning_api.py), [store](../../src/ml_pipeline_pro/tuning_store.py), and [execution](../../src/ml_pipeline_pro/tuning_execution.py) own tuning jobs/trials and call tracking repositories for training results.
- [Queue configuration](../../src/ml_pipeline_pro/queue.py) and [worker tasks](../../src/ml_pipeline_pro/worker.py) handle dispatch/execution/recovery. Redis has no Celery result backend; MongoDB supplies API-visible status.
- [Training](../../src/ml_pipeline_pro/training.py) reads a hash-checked CSV and writes artifacts through [artifacts.py](../../src/ml_pipeline_pro/artifacts.py).

The six domain collections all include project IDs, UTC timestamps, and a schema version. MongoDB stores the record ID as `_id`; API schemas expose `id`.

| Collection | Stored identity/outcome | Implemented indexes |
| --- | --- | --- |
| `datasets` | Name/version, local URI, SHA-256, feature/target/split columns, class count, split row counts | Unique project/name/version; project/created time/ID |
| `models` | Name, framework, task, architecture | Unique project/name; project/created time/ID |
| `experiments` | Input IDs/config, submission fingerprint, status/claims/leases, metrics, dependencies, artifact references, tuning linkage, test-evaluation flag | Unique project/submission key; project/status or model/created time; recovery; project/created time/ID |
| `model_versions` | Model/version, source experiment, checkpoint reference, dependencies | Unique project/model/version; project/created time/ID |
| `tuning_jobs` | Objective/space/budgets, claims/deadlines, reservation/progress, selected result, final evaluation/stop reason | Unique project/submission key; project/status/created time; recovery; project/created time/ID |
| `trials` | Job ID, zero-based `number`, fixed parameters/config/experiment ID, status/metrics/objective/duration/error | Unique project/job/number |

At that baseline, indexes were created lazily for APIs and explicitly in workers;
there were no migration/retention procedures. Conversation/action storage and
monitoring were still planned. They are now implemented; monitoring summaries
derive on read, while general durable aggregates/alert lifecycle remain deferred.

## Open audit findings

This section retains the October 6 audit mechanisms and follow-up evidence.
Ownership and controlled recovery were subsequently fixed/verified; managed
immutable uploads and explicit deletion now address part of the original storage
gap. Direct operator-file references, scheduled retention/restore and arbitrary
partition/concurrent-load behavior remain limited. See the current snapshot above.

Findings 1 and 2 retain the original audit diagnosis and their delivered follow-up.
They are resolved within the serial, controlled recovery scope described below.
The operator-source-file and shared-production gaps remain open; arbitrary
partitions and concurrent-load safety remain unverified. Managed uploads and
local Kubernetes delivery are covered by later evidence above.

### 1. High priority: parent ownership does not fence every tuning child write

**Status: fixed after the baseline audit.** The description and probe evidence below
preserve the original finding. [Ownership fix validation](#ownership-fix-validation)
documents the implementation and regression results.

Existing experiment completion and tuning job updates check worker tokens, and the suites cover several stale-owner rejection cases. Two related boundaries still permit operations from a worker whose parent tuning lease has been replaced:

1. [TrialRepository.claim](../../src/ml_pipeline_pro/tuning_store.py) matches the child ID/project/status but does not validate the parent job's current token. [ExperimentRepository.claim](../../src/ml_pipeline_pro/jobs.py), when passed a tuning job ID, also permits taking a running child without verifying the parent owner, even when the child's lease has not expired. After replacement, an old caller can reclaim these child records from the new worker.
2. [ExperimentRepository.finish_tuning_test](../../src/ml_pipeline_pro/jobs.py) has no worker-token argument or parent ownership predicate. The execution layer checks ownership before calling it, but replacement can occur between that check and the database write. A stale result can then set `test_evaluated` and replace the selected experiment's metrics/artifact references.

**Probe evidence:** In a dedicated random `mlpp_audit_*` database, claim a tuning job as `old`, expire its lease, and claim it as `replacement`. Insert a running trial/experiment owned by `replacement`; child claim calls with `old` still return records owned by `old`. Insert a succeeded, unevaluated child; `finish_tuning_test` accepts the write while the parent is owned by `replacement`. All three repository operations were confirmed, and the disposable database was removed. Local results are retained in ignored `artifacts/project-audit/2026-10-06/repository-probes.json`.

This demonstrates missing guards at the repository boundary. It is not an observed failure in the existing serial queued workflow or a full concurrent takeover test. Nevertheless, the caller's separate ownership check is insufficient to guarantee stale-result rejection.

**Required follow-up:** Fence child claims and final evaluation persistence with parent ownership, using an atomic ownership/commit design that accounts for writes across collections. Add regression cases that pause the old worker at these exact boundaries, transfer ownership, then resume it. Reject old claims/commits while allowing the replacement to finish. Do this before increasing worker/trial concurrency.

### 2. Medium priority: recovery validation stops short of process-loss recovery

**Baseline finding; addressed by the [controlled recovery gate](#process-loss-and-dependency-outage-validation).** At the audit baseline, recovery tests simulated storage errors and explicitly expired leases before invoking execution again. Live integration verified queued execution and cancellation, but did not kill a worker during training/final evaluation and wait for Beat-driven recovery. Redis/MongoDB outages during heartbeats and late commits also needed focused coverage. The host unit suite uses in-memory repositories, so passing it alone does not validate MongoDB ownership predicates.

**Delivered follow-up:** Controlled worker termination/restart and dependency outage cases now verify scheduler redispatch, attempt exhaustion, preserved training/artifacts/deadlines, and rejection of an expired final commit. The earlier real-MongoDB transaction takeover tests separately reject stale child writes. Worker/scheduler execution is evidenced by logs and state assertions; host coverage still excludes those container processes. CI prints coverage without enforcing a threshold.

### 3. Medium priority: reproducibility depends on keeping the source CSV

Dataset registration stores a content hash and local relative URI, not an immutable data snapshot. Workers reject changed bytes, which protects evaluation integrity, but overwriting or removing a registered file prevents rerunning that version. Manifests contain dataset metadata, not CSV content. Artifacts from failed/replaced attempts and queued tests have no cleanup policy.

**Required follow-up:** Define immutable dataset/version storage and dataset/artifact retention before shared use. Coordinate metadata and artifact backups, and verify restore resolves every retained reference. Keep original files available in the meantime.

October 19 follow-up: managed upload/preparation and column-version publication
now retain immutable files, and reviewed permanent deletion handles explicit
cascades. This original finding still applies to externally registered operator
files; scheduled retention and coordinated backup/restore remain open.

### 4. Documentation drift corrected by this update

The previous README described implemented tuning/model tracking as proposed, showed future assistant/monitoring infrastructure as the architecture, and still listed a tuning guide as future work. The plan mixed actual and proposed record/API fields. One integration quickstart omitted the training extra and worker flag, which could skip queued tests or fail direct tuning recovery. Walkthroughs also assumed a preconfigured Windows workspace and did not stop artifact/version commands after unsuccessful polling. These have been updated; historical validation evidence remains tied to its original commit.

### Deployment and operational gaps

Current shared-deployment gaps, reconciled October 19; these are separate from
the demonstrated local course deployment:

- Compose pins the environment to development, uses unauthenticated local MongoDB/Redis defaults, and has no TLS or user/role authorization. A static project key map is the only implemented API access control.
- Readiness probes MongoDB/Redis only. Worker and scheduler services have no configured healthchecks; a ready API can have no progressing worker.
- Worker CPU/memory/task limits and a non-root container are implemented. Generated-code execution, network restrictions, and a dedicated sandbox are not.
- Training deadlines are per attempt; tuning's overall deadline survives recovery and starts on the first claim. Checks are cooperative, with Celery soft/hard task limits of 620/630 seconds. Queue wait is not bounded by these budgets.
- Object storage, coordinated backup/restore, scheduled retention, general schema migrations, production rollout procedures and concurrent-load/capacity benchmarks remain outstanding. Kubernetes manifests/test-cluster CI/CD and explicit dataset/model erasure are delivered. Managed uploads are immutable; directly registered operator files are still external dependencies.
- Python 3.11-3.14 is allowed by the manifest; CI verifies 3.11/3.13 on Linux and this audit uses Windows 3.11. Python 3.12/3.14 and macOS have no recorded CI matrix checks.
- The current suite emits a Starlette deprecation warning for its HTTPX TestClient adapter. It is non-failing and should be addressed in a tested dependency/test-client update.

## Validation evidence

Historical October 6 validation follows. Latest combined feature counts and
machine/profile-specific AI evidence are linked in the current snapshot above.
The original audit ran against the source baseline above and the existing local
Compose stack; it did not rebuild the stack. The baseline's successful Compose
CI job separately verifies a rebuilt image.

| Check | Audit result |
| --- | --- |
| Unit/API/real-training/tuning suite | 126 passed, 9 integration cases deselected; no selected-case skips |
| Live MongoDB/Redis/API/worker integration suite | 9 passed, 126 unit cases deselected; both opt-in flags enabled |
| Ruff lint/format | Passed; 50 Python files already formatted |
| Installed dependency compatibility | All 86 installed packages compatible |
| Packaging | Source distribution and wheel built with cached build dependencies; all 24 application modules present and ignored local files excluded |
| Locked runtime dependency audit | No known vulnerabilities reported for auditable packages; CPU-suffixed PyTorch skipped by the advisory lookup |
| Separate normalized PyTorch release audit | `torch==2.14.1`: no known vulnerabilities reported |
| Service-free examples | Training succeeded; tuning completed five trials and final holdout evaluation |
| Saved ten-iteration evidence | Summary/statistics inspected; 1,350 passes, zero failures/errors/skips against `3bf71af` |
| GitHub baseline CI | [0e37e6e run](https://github.com/JacobHermsmeyer21/ML-Pipeline-Pro/actions/runs/37541937953): Python 3.11/3.13 checks and Compose smoke all successful |
| Repository ownership probes | Confirmed the open findings above; dedicated database cleaned up |
| Documentation checks | 52 local links/anchors valid, README covers all 21 API operations, and 17 PowerShell examples parse successfully |

The baseline audit's unit-only coverage output rounds combined statement/branch coverage to 77%. The earlier full-suite report measured 84.93% in the host process; it does not include worker/scheduler execution inside containers. These are different measurements and should not be treated as a coverage regression. See the [historical ten-iteration report](../guides/verification.md#ten-iteration-validation-october-6-2026) for the original environment, counts, and repeat commands.

Both current suites emit the existing TestClient deprecation warning. No live model-provider evaluations, production workload benchmarks, physical worker-loss recovery tests, or restore exercises were run. Dependency advisory results are scoped to the audited releases and date, not a guarantee about application security.

## Next work, in order

1. **Close bounded deployed CPU-laptop acceptance.** Preserve successful standalone and unbounded results separately from the failed gateway workflow. Diagnose resource/availability and live expiry at the failing boundary; the fixed-setting resource plan is deferred, not approved. Any changed budgets, defaults or ownership need renewed reviewed scope.
2. **Finish dataset-control review.** Obtain human usefulness review of completed preparation/column/deletion controls and independent review of the new lifecycle/publication/cleanup boundaries. Retain the passing browser, transaction/process and recovery evidence without calling self-review independent.
3. **Rehearse the selected demo machine/profile.** Verify current images/storage, actual-ID history/tuning/draft/monitoring behavior and new generated outputs. The bounded workstation walkthrough is the retained complete bounded result; model gates alone do not prove the laptop deployment.
4. **Complete shared-production controls before shared use.** Identity/roles/TLS, authenticated infrastructure, scheduled retention, migrations, coordinated restore, operational probes and public deployment procedures remain open. Explicit deletion and immutable managed uploads do not close all storage lifecycle needs.
5. **Run reviewed research measurements before claiming improvements.** Larger retrieval/query benchmarks and proposed speedup/quality percentages remain unverified; they are separate from course acceptance.

Keep transaction ownership, submission replay and controlled recovery gates passing.
Preserve serial CPU training until concurrent-load/partition evidence supports a
reviewed change. The [course checklist](course-requirements.md) records demonstrated
minimal scope and remaining acceptance limits; roadmap/design plans remain unchanged.

## Ownership fix validation

Tuning child insertion, claims, heartbeats, completion, final holdout persistence,
and interrupted-child cleanup now use a MongoDB transaction. Each transaction
increments an internal `ownership_revision` on the matching parent token before
mutating the child. This parent write forces conflicts with takeover, cancellation,
and terminal job updates; reading the token alone under snapshot isolation would
leave the original race. Expired parent leases cannot authorize child writes.
Cleanup without a token is allowed only for a failed/cancelled parent with no owner.
Standalone experiment tasks cannot claim tuning children.

Compose now initializes a single-node `mlpp` replica set for transaction support.
Existing local volumes are retained on recreation. Host clients need
`?directConnection=true` to connect through the published port while the replica
set advertises `mongo:27017`. External databases must be replica sets or sharded
clusters to run tuning.

Ten new integration regressions establish an old-owner transaction snapshot, pause
before its parent/child write, replace the parent owner, and resume the old worker.
Each rejected mutation leaves child state unchanged, preserves the original
deadline, and allows the replacement to proceed. These tests cover both audited
child claims and final test persistence, plus insertion, completion, heartbeat,
and cleanup. They use real MongoDB; the in-memory suite also follows the stricter
repository contracts. Physical worker termination and real dependency outage
coverage were separate open work at this stage; they are now covered by the
[subsequent recovery gate](#process-loss-and-dependency-outage-validation).

The execution-boundary tests also exposed a manifest overwrite during final
evaluation: training and evaluation used the same attempt directory, so an
uncommitted evaluated manifest invalidated the recorded trial hash. Evaluation
now writes under a separate `WORKER_TOKEN-evaluation` directory. The checkpoint
and trial manifest remain intact until the evaluated references are committed;
recovery can retry evaluation after either storage failure or rejected ownership.
A real-MongoDB replay case interrupts final persistence and verifies the original
artifacts remain readable, training is reused, and the deadline is preserved.

Validation on October 6, 2026: **129 local tests and all 20 real-service cases
passed**, with no selected-case skips. The integration run used a rebuilt isolated
five-service Compose stack and included queued training/tuning, active cancellation,
verified downloads, and model registration. Ruff lint/format, all 86 installed
packages' dependency compatibility, and 56 local documentation links/anchors
also passed. JUnit reports are retained in ignored
`artifacts/bugfix-validation/`. The existing TestClient deprecation warning remains.

## Process-loss and dependency-outage validation

The [recovery suite](../guides/verification.md#worker-and-dependency-recovery-validation) adds ten isolated Compose cases with a dedicated
image built from the current checkout. It kills the whole worker container with
`SIGKILL` during a real optimizer step, selected-checkpoint evaluation, or final
manifest persistence. Beat redispatches work after natural lease expiry. The tests
never edit leases or invoke recovery/execution directly.

Recovered searches preserve reservation configurations/experiment IDs and both
original deadlines, reuse completed training, retain validation-only trial
metrics, and evaluate exactly one winner. Both standalone and tuning jobs fail
after two actual worker losses in the test configuration; tuning children close
without scheduling another trial. Hash-verified downloads remain available.

MongoDB is stopped during tuning ownership checks and final commit. The ownership
watch records an actual driver error. A final transaction can retry internally;
the test verifies that the expired owner's eventual commit is rejected before the
replacement completes, with no repeated training. Redis is stopped during both
submission types: the API returns `503`, retains one queued record, and Beat
dispatches it after Redis restarts without a client resubmission.

Validation on October 6, 2026: **129 local tests, 20 ordinary real-service tests,
and all ten controlled recovery cases passed**, with no selected-case skips.
Ruff lint/format, locked dependency consistency, installed compatibility for all
86 packages, and local documentation links passed. Evidence is retained in ignored
`artifacts/recovery-validation/`, including JUnit, MongoDB snapshots, and service
logs. CI now runs the recovery gate and uploads its evidence. The new CI run's
outcome is separate from this local validation.

The gate retains one CPU, 1 GiB, and one concurrent worker job. Test leases are ten
seconds and the attempt limit is two; production defaults remain thirty seconds
and three attempts. It uses separate ports, database, image, and volumes from the
development stack. Container execution remains outside host coverage statistics.
Concurrent load, arbitrary partitions, and restore exercises remain open.

## Conversation tool validation

The [provider-independent library](../guides/workflows.md#conversation-tool-layer) implements 13 existing
API operations for reads, comparison, bounded submission, and tuning cancellation.
The host binds project credentials, mutation permission, correlation, and retry
keys separately from tool arguments. Missing submission budgets/objectives are
reported before dispatch. Public records carry evidence references; incomplete
record identity/time metadata is rejected rather than generated by schema defaults.
At that tool-slice revision there was no provider-backed dialogue, `/chat` route,
or conversation/action store. The later A1 storage step is recorded above.

Validation on October 6, 2026: **211 local tests, 21 ordinary real-service cases,
and all ten isolated recovery cases passed**, with no selected-case skips. The
82 new local cases cover catalog validation, real-app project access, budgets,
retry/conflict/cancellation, response evidence, transport failures, and redaction.
The new real-service workflow submits/retries training/tuning, queries trials,
compares validation results, and cancels active tuning through the HTTP tools.

Ruff lint/format, locked sync, installed compatibility for 86 packages, package
build/contents, local documentation links/anchors, Python/PowerShell example
syntax, and the deterministic service-free example passed. The existing
TestClient deprecation warning remains. Packaging emitted a cache-location
warning; archive inspection confirmed no ignored caches/tools/venv/artifacts were
included. Host coverage rounds to 78% and excludes container worker execution.

Local evidence is retained in ignored `artifacts/conversation-tools-validation/`
and `artifacts/recovery-validation/mlpp-recovery-36e59baff6e4/`. The
[approved plan outcome](../plans/2026-10-06-conversation-tools-plan.md#implementation-outcome)
records commands, versions, source/image provenance, review scope, and limitations.
CI now uploads unit and ordinary JUnit reports alongside its recovery evidence;
its post-push outcome is separate from local validation. No independent
implementation review or live-provider evaluation is claimed.

## Reading a local tuning manifest

A manifest containing `test_evaluated: false` and only validation metrics is expected for a tuning trial. Trial records keep validation-only outcomes even after selection. The winner's experiment receives the test metrics after final evaluation.

The service-free tuning demo writes trial artifacts under `artifacts/demo/EXPERIMENT_ID/local/`, then writes an updated winner manifest under `artifacts/demo/EXPERIMENT_ID/final/`. The original `local/manifest.json` remains unchanged, even for the winner. Use the artifact references in `artifacts/local-tuning/JOB_ID/summary.json` to find the final manifest. API clients should follow the selected experiment's current `artifacts` references or download endpoint. If `final_evaluation` is `skipped_budget`, no evaluated winner is available for version registration.

## Documentation consolidation: October 8, 2026

Audited all 19 Markdown files at `c28ae06`; consolidated them into 16.
Classification, tuning, and tool tutorials shared `docs/workflows.md` at that
revision (now the [workflow guide](../guides/workflows.md)). Recovery instructions
and the original ten-iteration report shared `docs/verification.md` (now the
[verification guide](../guides/verification.md)). Removed the five replaced files
and updated incoming links. README owns setup, endpoint discovery, and the document map; this status
record owns capability/evidence inventories; the course checklist owns acceptance;
PLAN.md owns milestones and measurement criteria. Removed repeated README
summaries and roadmap inventories. Retained separate design approval/outcome
records and short technical memory findings under the development method.

Corrected stale conversation-approval statements against the October 7 approval
record. Labelled the baseline audit and resolved ownership/recovery findings so
historical test counts cannot be read as a new run. Source inspection confirmed
21 API operations, the single domain API, the 13-tool library, and the absence of
LangChain, monitoring, code generation, and Kubernetes implementation. Outstanding
course requirements remain outstanding; no application behavior changed.

Documentation checks passed: all 16 Markdown documents' local links/anchors,
18 PowerShell code blocks parsed, both Python examples matched their previously
verified source exactly, and README covered all 21 API operations. Self-review
checked the moved historical results and plan approval/acceptance records against
the originals. Raw checker, results, and baseline provenance are retained locally
in ignored `artifacts/docs-consolidation/`. Python syntax was not re-parsed because
this checkout has no usable Python environment; the example code is unchanged.
No application, real-service, recovery, or model evaluation suite was run for
this documentation-only change. Whitespace and commit/push results are reported
in the completion handoff.

## Documentation organization: October 9, 2026

Reorganized documentation against source baseline `ef9d6bd`. Setup, workflow,
conversation development, and verification guides live in `docs/guides/`;
API/architecture details live in `docs/reference/`; requirements, methodology,
status, and measurement criteria live in `docs/project/`. The
[documentation index](../README.md) describes each folder. Dated plans, memory,
and raw evidence retain their existing folders.

Rewrote the root README as a short introduction and quick start, and PLAN as a
milestone roadmap. Moved detailed setup, the complete endpoint inventory,
architecture/ownership notes, and research measurement criteria into dedicated
documents. Preserved course obligations, outstanding acceptance work, approval
records, historical results, and repository contracts; updated local references,
including AGENTS.md, to the new paths.

Documentation verification covers all 30 Markdown files' local links/anchors,
both Python examples, all 23 PowerShell examples, Compose configuration syntax,
and the API reference's 25 operations against source. Source inspection checked
setup against Compose, settings, the package manifest, and CI. The checker,
original snapshot, and raw results are retained locally in ignored
`artifacts/docs-reorganization/`. No application, live-service, recovery, or model
evaluation suite was run for this documentation-only change.

## Person A local token admission: October 9, 2026

Continued approved A1 work after the documentation reorganization on `a4bdbe4`.
Installed explicit Ollama/Qwen profiles under ignored local storage and added a
checksum-pinned, artifact/runtime/template-specific counter with lazy API setup.
Retained runtime rendering/count and overflow observations verify selected token
admission. The default adapter remains unavailable without an injected counter.

All six live attempts failed acceptance. After prompt revisions, the stock 7B
profile reached five passing scenarios, its explicit JSON-tools profile reached
six, and the 14B profile reached three. The ten original scenarios and strict
parser/assertions are unchanged. Template formatting was confirmed and corrected
in explicit profiles, but structured reply and budget-understanding failures
remain. C3/C5, independent review and complete conversation onboarding stay open.

Final host checks passed: 420 fast cases (77% coverage), 56 ordinary integration
cases with both flags, ten serial recovery cases, locked sync, Ruff lint/format,
dependency compatibility and source/wheel builds. Selected gates had no skips or
failures. The wheel includes 37 application modules and excludes model/cache data.
[The A1 outcome](../plans/2026-10-06-conversation-workflows-plan.md#person-a-selected-tokenizer-and-failed-live-evaluation-october-9-2026)
and [shared evidence manifest](../evidence/2026-10-09-qwen-counter/results.json)
retain raw results, source/package/profile identity and provenance limitations.
No remote CI or concurrent-capacity result is claimed. Review here is self-review;
a typed completion tool is a pending design hypothesis, not an implemented fix.

## Person A typed completion experiment: October 10, 2026

The user approved the [typed-completion plan](../plans/2026-10-09-conversation-typed-completion-plan.md)
before implementation on `74a9158`. The adapter now binds `finish_conversation`
alongside the 13 domain tools and translates one strictly validated completion
to the existing reply schema. Full-schema byte admission and exact SDK token
admission include all 14 functions. The public catalog, routes, persisted schemas,
confirmed action dispatch and worker limits remain unchanged.

All 446 fast cases (77.29% host coverage), 58 ordinary integration cases with both
flags and ten serial isolated recovery cases passed without failures or selected
skips. Locked sync, Ruff lint/format, dependency checks and package builds passed;
the wheel contains all 37 application modules and archives exclude model/private
paths. Twenty-six added fast cases and two real-store cases cover strict parsing,
completion isolation, context/token limits, redaction, grounding, persistence and
replay. The new 14-function runtime probe admitted 7,680 input tokens plus 512
reserved output at context 8,192; 7,681 was blocked before inference.

**The unchanged ten-scenario local-model gate failed: three passed, seven failed.**
It used the existing explicit 7B JSON-tools profile and unchanged budgets, without
retries or repairs. Saved proposals show a wrong per-trial budget and reuse of
missing limits. Five turns reported `model_invalid_response`; a separate read-only
diagnostic observed 23 repeated native reads ending at the output limit. No
mutation was dispatched. These observations do not establish successful guided
dialogue, history-based suggestions, latency or capacity.

[The retained evidence](../evidence/2026-10-10-typed-completion/results.json)
includes raw JSON/JUnit/native exits, runtime and source/package provenance,
diagnostic responses and recovery snapshots/logs. All final application/test
source hashes match across the fast, ordinary, recovery and live runs. Independent
review remains unavailable; review here is implementing-assistant self-review.
A1/C3/C5, human model-quality review and complete clean-checkout onboarding remain
open. The protocol experiment is implemented; another reliability approach needs
a reviewed plan. No new 14B acceptance run or model training is claimed.

## Person A snippet generation: October 10, 2026

The repository user approved the [A2 plan](../plans/2026-10-08-person-a-snippet-generation-plan.md)
and requested implementation; its approval was committed/pushed as `74b47f8`.
The implementation generates four supported Python integration profiles through
the existing LangChain/local-model stack, checks a closed AST/API grammar, and
saves accepted drafts or fixed rejection results with model/input/usage/time
provenance. All drafts require human review. Generation spends one additional
call inside the original turn deadline/limit and never executes code or submits
a domain action. Native bindings include 15 functions; public domain tools stay 13.
Old schema-v1 turns without snippet output remain readable.

All 506 fast cases, 61 ordinary integration cases with both required flags, and
ten serial isolated recovery cases pass without failures or selected skips.
Locked installation, lint/format, dependency checks, package build and
documentation/example/API checks pass. The wheel contains 40 canonical modules
and source packaging excludes private/model/cache paths. Three new real-store
cases verify accepted/rejected draft replay, foreign-project rejection, no
action/domain dispatch and absence of invented evidence in old records.

**A2 real-model acceptance remains incomplete: six of seven scenarios pass.**
The final training draft omitted `Idempotency-Key` and was rejected. The previous
run passed training but failed comparison and missing-input specificity.
Earlier runs and a separate diagnostic are retained; validation assertions,
scenarios and budgets were not relaxed, and no Python was repaired or executed.
The A2 evaluation does not replace A1's original ten-scenario quality gate.

[The retained evidence](../evidence/2026-10-10-a2-snippets/results.json) records
source hashes, actual SDK/runtime token observations, safe generated outputs,
native exits, JUnit/text logs, package/container identities and recovery evidence.
The first live run lacks rejected raw code; later runs and the diagnostic retain
redacted model steps. Independent review and human usefulness review remain
outstanding, along with full A2/C7 acceptance and clean-checkout onboarding.
A3/A4 remain awaiting approval. Self-review is not independent review.

## Documentation refresh: October 19, 2026

Reconciled the README/index, guides, API/architecture references, current course
coverage and relevant memory against `28c22fb` and retained execution evidence.
Plans and the supplied course instructions are unchanged. `.env.example` edits
only explain existing capabilities; configuration values and application code
are unchanged. Historical audit/model failures retain their original provenance.

Documentation validation checks all 78 non-plan Markdown documents: 778 local
links, including 103 anchor references, resolve; 61 PowerShell, seven JSON and
seven Python examples parse. The endpoint inventory covers all 41 unique
OpenAPI method/path operations across compatibility/model/tuning/monitoring
factories. Configuration defaults/ceilings and the retained 740/104/10 test
results, 21 deletion cases and five browser worker runs were checked against
source/raw reports. Compose examples render and `git diff --check` passes.
No application, live-service or model suite was rerun for this documentation-only
change; earlier results remain scoped to their saved revisions and environments.
