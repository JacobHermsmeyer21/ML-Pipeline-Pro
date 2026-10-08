# Project audit and development status

**Audit date:** October 6, 2026. **Audited baseline:** `0e37e6e17614ae146e75a576c1f60c885ee79cd0` on `main`. **Package version:** `0.1.0`.

**Documentation source check, October 8, 2026:** baseline `c28ae06`. The
conversation workflow design was approved October 7, but this checkout still has
no LangChain dependencies, model adapter, chat routes, or dialogue/action store.
The dated validation below is historical; no application suite was rerun for this
documentation consolidation. [Verification](verification.md) owns execution setup;
[workflows](workflows.md) owns runnable tutorials.

ML Pipeline Pro has a working local classification experiment and tuning backend. The initial feature scope of milestones 1-3 is implemented and its existing tests pass. The full MVP is still incomplete: conversational access, monitoring, generated code, and shared-deployment readiness remain. The baseline audit's recovery ownership bugs are fixed, and controlled process-loss/dependency-outage validation is delivered. Concurrent-load/partition validation and storage lifecycle work remain open.

The baseline audit reviewed the tracked application modules, examples, tests/fixtures, dependency manifest/lockfile, Docker/Compose configuration, CI, and documentation. It also checked the saved validation evidence and local demo manifests, ran the baseline suites/demos, inspected the running services, and probed ownership boundaries in a disposable MongoDB database. That audit changed documentation only; subsequent application fixes and their checks are documented in [ownership fix validation](#ownership-fix-validation).

## Course scope alignment

On October 6, 2026 the user supplied the nine
[course implementation instructions](course-requirements.md) and requested
documentation correction against source baseline `ba6334f`. The course target
uses LangChain with local pre-trained inference; a paid external model API or
training a code language model is not required. The unapproved OpenAI draft was
revised in the [conversation plan](plans/2026-10-06-conversation-workflows-plan.md);
per-action confirmation and retained dialogue/evidence were approved October 7; their implementation remains outstanding.

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

## Where development stands

| Milestone | Current state | Remaining scope |
| --- | --- | --- |
| 1. Development foundation | Initial scope complete | Broader supported-platform verification and operational hardening |
| 2. Reproducible experiment tracking | Initial CPU classification scope complete | Standalone cancellation, immutable dataset storage, retention, broader adapters |
| 3. Bounded tuning | Initial serial TPE scope, transactional ownership fixes, and controlled recovery gate complete | Concurrent load/network partitions, later parallel dispatch |
| 4. Conversational workflows | Provider-independent tools implemented; LangChain/local-model conversation pending | Pre-trained local adapter, guided dialogue/history, tuning suggestions, confirmed actions, real-model evaluation |
| 5. Monitoring and diagnosis | Not started | Separate REST service, live observations/visualization, defined update interval, LangChain summaries and evidence-linked proposed fixes |
| 6. Reviewable code generation | Not started | LangChain/local-model Python generation, validation/provenance, human review; execution optional |
| 7. Deployment and onboarding | Existing local Docker/Compose and CI checks delivered | Required independent domain services and Kubernetes/deployment CI/CD/tutorials; additional shared-production controls and restore |

These states describe delivered scope, not a percentage estimate or a production-readiness certification. Detailed acceptance criteria are in [PLAN.md](../PLAN.md#implementation-milestones).

## Implemented behavior and limits

| Area | Verified implementation | Current boundary |
| --- | --- | --- |
| API foundation | FastAPI app factory, versioned routes, validated settings, async clients, consistent errors/correlation IDs, JSON logs and redaction | One application; no conversation or monitoring routes |
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

The current deployment is modular rather than separate domain services:

- [Tracking API](../src/ml_pipeline_pro/api.py) and [tracking store](../src/ml_pipeline_pro/tracking.py) own datasets, models, experiments, and model versions.
- [Tuning API](../src/ml_pipeline_pro/tuning_api.py), [store](../src/ml_pipeline_pro/tuning_store.py), and [execution](../src/ml_pipeline_pro/tuning_execution.py) own tuning jobs/trials and call tracking repositories for training results.
- [Queue configuration](../src/ml_pipeline_pro/queue.py) and [worker tasks](../src/ml_pipeline_pro/worker.py) handle dispatch/execution/recovery. Redis has no Celery result backend; MongoDB supplies API-visible status.
- [Training](../src/ml_pipeline_pro/training.py) reads a hash-checked CSV and writes artifacts through [artifacts.py](../src/ml_pipeline_pro/artifacts.py).

The six domain collections all include project IDs, UTC timestamps, and a schema version. MongoDB stores the record ID as `_id`; API schemas expose `id`.

| Collection | Stored identity/outcome | Implemented indexes |
| --- | --- | --- |
| `datasets` | Name/version, local URI, SHA-256, feature/target/split columns, class count, split row counts | Unique project/name/version; project/created time/ID |
| `models` | Name, framework, task, architecture | Unique project/name; project/created time/ID |
| `experiments` | Input IDs/config, submission fingerprint, status/claims/leases, metrics, dependencies, artifact references, tuning linkage, test-evaluation flag | Unique project/submission key; project/status or model/created time; recovery; project/created time/ID |
| `model_versions` | Model/version, source experiment, checkpoint reference, dependencies | Unique project/model/version; project/created time/ID |
| `tuning_jobs` | Objective/space/budgets, claims/deadlines, reservation/progress, selected result, final evaluation/stop reason | Unique project/submission key; project/status/created time; recovery; project/created time/ID |
| `trials` | Job ID, zero-based `number`, fixed parameters/config/experiment ID, status/metrics/objective/duration/error | Unique project/job/number |

Indexes are created lazily for the APIs and explicitly in worker tasks. There are no application schema migration or retention procedures yet. Conversations, action audit records, monitoring summaries, and alerts are planned collections, not existing persistence features.

## Open audit findings

Findings 1 and 2 retain the original audit diagnosis and their delivered follow-up.
They are resolved within the serial, controlled recovery scope described below.
The source CSV and deployment gaps remain open; arbitrary partitions and
concurrent-load safety remain unverified.

### 1. High priority: parent ownership does not fence every tuning child write

**Status: fixed after the baseline audit.** The description and probe evidence below
preserve the original finding. [Ownership fix validation](#ownership-fix-validation)
documents the implementation and regression results.

Existing experiment completion and tuning job updates check worker tokens, and the suites cover several stale-owner rejection cases. Two related boundaries still permit operations from a worker whose parent tuning lease has been replaced:

1. [TrialRepository.claim](../src/ml_pipeline_pro/tuning_store.py) matches the child ID/project/status but does not validate the parent job's current token. [ExperimentRepository.claim](../src/ml_pipeline_pro/jobs.py), when passed a tuning job ID, also permits taking a running child without verifying the parent owner, even when the child's lease has not expired. After replacement, an old caller can reclaim these child records from the new worker.
2. [ExperimentRepository.finish_tuning_test](../src/ml_pipeline_pro/jobs.py) has no worker-token argument or parent ownership predicate. The execution layer checks ownership before calling it, but replacement can occur between that check and the database write. A stale result can then set `test_evaluated` and replace the selected experiment's metrics/artifact references.

**Probe evidence:** In a dedicated random `mlpp_audit_*` database, claim a tuning job as `old`, expire its lease, and claim it as `replacement`. Insert a running trial/experiment owned by `replacement`; child claim calls with `old` still return records owned by `old`. Insert a succeeded, unevaluated child; `finish_tuning_test` accepts the write while the parent is owned by `replacement`. All three repository operations were confirmed, and the disposable database was removed. Local results are retained in ignored `artifacts/project-audit/2026-10-06/repository-probes.json`.

This demonstrates missing guards at the repository boundary. It is not an observed failure in the existing serial queued workflow or a full concurrent takeover test. Nevertheless, the caller's separate ownership check is insufficient to guarantee stale-result rejection.

**Required follow-up:** Fence child claims and final evaluation persistence with parent ownership, using an atomic ownership/commit design that accounts for writes across collections. Add regression cases that pause the old worker at these exact boundaries, transfer ownership, then resume it. Reject old claims/commits while allowing the replacement to finish. Do this before increasing worker/trial concurrency.

### 2. Medium priority: recovery validation stops short of process-loss recovery

**Baseline finding; addressed by the [controlled recovery gate](#process-loss-and-dependency-outage-validation).** At the audit baseline, recovery tests simulated storage errors and explicitly expired leases before invoking execution again. Live integration verified queued execution and cancellation, but did not kill a worker during training/final evaluation and wait for Beat-driven recovery. Redis/MongoDB outages during heartbeats and late commits also needed focused coverage. The host unit suite uses in-memory repositories, so passing it alone does not validate MongoDB ownership predicates.

**Delivered follow-up:** Controlled worker termination/restart and dependency outage cases now verify scheduler redispatch, attempt exhaustion, preserved training/artifacts/deadlines, and rejection of an expired final commit. The earlier real-MongoDB transaction takeover tests separately reject stale child writes. Worker/scheduler execution is evidenced by logs and state assertions; host coverage still excludes those container processes. CI prints coverage without enforcing a threshold.

### 3. Medium priority: reproducibility depends on keeping the source CSV

Dataset registration stores a content hash and local relative URI, not an immutable data snapshot. Workers reject changed bytes, which protects evaluation integrity, but overwriting or removing a registered file prevents rerunning that version. Manifests contain dataset metadata, not CSV content. Artifacts from failed/replaced attempts and queued tests have no cleanup policy.

**Required follow-up:** Define immutable dataset/version storage and dataset/artifact retention before shared use. Coordinate metadata and artifact backups, and verify restore resolves every retained reference. Keep original files available in the meantime.

### 4. Documentation drift corrected by this update

The previous README described implemented tuning/model tracking as proposed, showed future assistant/monitoring infrastructure as the architecture, and still listed a tuning guide as future work. The plan mixed actual and proposed record/API fields. One integration quickstart omitted the training extra and worker flag, which could skip queued tests or fail direct tuning recovery. Walkthroughs also assumed a preconfigured Windows workspace and did not stop artifact/version commands after unsuccessful polling. These have been updated; historical validation evidence remains tied to its original commit.

### Deployment and operational gaps

These are unfinished delivery requirements, not newly reproduced failures:

- Compose pins the environment to development, uses unauthenticated local MongoDB/Redis defaults, and has no TLS or user/role authorization. A static project key map is the only implemented API access control.
- Readiness probes MongoDB/Redis only. Worker and scheduler services have no configured healthchecks; a ready API can have no progressing worker.
- Worker CPU/memory/task limits and a non-root container are implemented. Generated-code execution, network restrictions, and a dedicated sandbox are not.
- Training deadlines are per attempt; tuning's overall deadline survives recovery and starts on the first claim. Checks are cooperative, with Celery soft/hard task limits of 620/630 seconds. Queue wait is not bounded by these budgets.
- Object storage, backup/restore, retention/deletion, schema migrations, Kubernetes manifests, production rollout procedures, and concurrent-load/capacity benchmarks are absent.
- Python 3.11-3.14 is allowed by the manifest; CI verifies 3.11/3.13 on Linux and this audit uses Windows 3.11. Python 3.12/3.14 and macOS have no recorded CI matrix checks.
- The current suite emits a Starlette deprecation warning for its HTTPX TestClient adapter. It is non-failing and should be addressed in a tested dependency/test-client update.

## Validation evidence

The audit ran against the source baseline above and the existing local Compose stack; it did not rebuild the stack. The baseline's successful Compose CI job separately verifies a rebuilt image.

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

The baseline audit's unit-only coverage output rounds combined statement/branch coverage to 77%. The earlier full-suite report measured 84.93% in the host process; it does not include worker/scheduler execution inside containers. These are different measurements and should not be treated as a coverage regression. See the [historical ten-iteration report](verification.md#ten-iteration-validation-october-6-2026) for the original environment, counts, and repeat commands.

Both current suites emit the existing TestClient deprecation warning. No live model-provider evaluations, production workload benchmarks, physical worker-loss recovery tests, or restore exercises were run. Dependency advisory results are scoped to the audited releases and date, not a guarantee about application security.

## Next work, in order

The [approved conversation tool slice](plans/2026-10-06-conversation-tools-plan.md)
is delivered. Retain its schema, access, budget, retry, and evidence checks.

1. **Implement the [approved local conversation plan](plans/2026-10-06-conversation-workflows-plan.md) within its approved scope.** Use LangChain/local pre-trained inference, guided dialogue/history, bounded tuning suggestions, missing-input handling, evidence, and separately confirmed actions. Select/evaluate the local artifact; implementation was approved October 7, 2026; the adapter and acceptance runs remain outstanding.
2. **Review required domain-service extraction.** Deliver independently deployable model-management, tuning, and monitoring REST APIs; preserve `/api/v1`, project access, and the shared MongoDB ownership fence. Separate services are a course requirement, independent of training concurrency or commercial scale.
3. **Implement milestone 5 monitoring.** Demonstrate running observations and dashboard/alert updates within a reviewed interval, then LangChain summaries and proposed fixes grounded in metric/log evidence.
4. **Implement milestone 6 AI code generation.** Generate Python integration snippets from conversation using LangChain/local inference, validate/provide provenance, and retain review boundaries. Templates alone are insufficient; execution remains optional.
5. **Finish course deployment and documentation.** Containerize the required services; exercise GitHub Actions CI/CD rollout/smoke tests in a Kubernetes test cluster. Complete clean-checkout onboarding and advanced optimization tutorials, then verify every row of the course checklist.
6. **Complete additional shared-production work before shared use.** Identity/roles/TLS, authenticated services, immutable storage, retention/deletion, restore tests, operational probes, and public deployment procedures remain open.
7. **Run the measurement plan.** Establish reproducible baselines before using proposed improvement percentages. These claims do not replace course acceptance evidence.

Keep transaction ownership and controlled recovery gates passing in CI. The next
feature is the reviewed local conversation slice. Preserve serial CPU training
until concurrent-load and partition behavior are measured, including during
service extraction. Course completion and additional production scope remain
distinct in [PLAN.md](../PLAN.md#completion-criteria).

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

The [recovery suite](verification.md#worker-and-dependency-recovery-validation) adds ten isolated Compose cases with a dedicated
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

The [provider-independent library](workflows.md#conversation-tool-layer) implements 13 existing
API operations for reads, comparison, bounded submission, and tuning cancellation.
The host binds project credentials, mutation permission, correlation, and retry
keys separately from tool arguments. Missing submission budgets/objectives are
reported before dispatch. Public records carry evidence references; incomplete
record identity/time metadata is rejected rather than generated by schema defaults.
There is no provider-backed dialogue, `/chat` route, or conversation/action store.

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
[approved plan outcome](plans/2026-10-06-conversation-tools-plan.md#implementation-outcome)
records commands, versions, source/image provenance, review scope, and limitations.
CI now uploads unit and ordinary JUnit reports alongside its recovery evidence;
its post-push outcome is separate from local validation. No independent
implementation review or live-provider evaluation is claimed.

## Reading a local tuning manifest

A manifest containing `test_evaluated: false` and only validation metrics is expected for a tuning trial. Trial records keep validation-only outcomes even after selection. The winner's experiment receives the test metrics after final evaluation.

The service-free tuning demo writes trial artifacts under `artifacts/demo/EXPERIMENT_ID/local/`, then writes an updated winner manifest under `artifacts/demo/EXPERIMENT_ID/final/`. The original `local/manifest.json` remains unchanged, even for the winner. Use the artifact references in `artifacts/local-tuning/JOB_ID/summary.json` to find the final manifest. API clients should follow the selected experiment's current `artifacts` references or download endpoint. If `final_evaluation` is `skipped_budget`, no evaluated winner is available for version registration.

## Documentation consolidation: October 8, 2026

Audited all 19 Markdown files at `c28ae06`; consolidated them into 16.
Classification, tuning, and tool tutorials now share `docs/workflows.md`.
Recovery instructions and the original ten-iteration report now share
`docs/verification.md`. Removed the five replaced files and updated incoming
links. README owns setup, endpoint discovery, and the document map; this status
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
