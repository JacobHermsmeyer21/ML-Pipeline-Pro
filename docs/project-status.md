# Project audit and development status

**Audit date:** October 6, 2026. **Audited baseline:** `0e37e6e17614ae146e75a576c1f60c885ee79cd0` on `main`. **Package version:** `0.1.0`.

ML Pipeline Pro has a working local classification experiment and tuning backend. The initial feature scope of milestones 1-3 is implemented and its existing tests pass. The full MVP is still incomplete: conversational access, monitoring, generated code, and shared-deployment readiness remain. Recovery ownership findings below are open engineering work even though the initial tuning workflow is delivered.

This audit reviewed the tracked application modules, examples, tests/fixtures, dependency manifest/lockfile, Docker/Compose configuration, CI, and documentation. It also checked the saved validation evidence and local demo manifests, ran the current suites/demos, inspected the running services, and probed ownership boundaries in a disposable MongoDB database. Application behavior was not changed by this documentation update.

## Where development stands

| Milestone | Current state | Remaining scope |
| --- | --- | --- |
| 1. Development foundation | Initial scope complete | Broader supported-platform verification and operational hardening |
| 2. Reproducible experiment tracking | Initial CPU classification scope complete | Standalone cancellation, immutable dataset storage, retention, broader adapters |
| 3. Bounded tuning | Initial serial TPE scope complete | Recovery ownership fixes, stronger failure/restart tests, later parallel dispatch |
| 4. Conversational workflows | Not started; next feature milestone | Provider adapter, typed tools, dialogue/action records, grounded responses, evaluations |
| 5. Monitoring and diagnosis | Not started | Observations, Prometheus/Grafana, drift/quality summaries, alert evidence |
| 6. Reviewable code generation | Not started | Templates, validation/provenance, explicit review, optional isolated execution |
| 7. Deployment and onboarding | Local Docker/Compose and CI delivered | Identity/roles, infrastructure authentication, object storage, backup/restore, operations, Kubernetes |

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
| Job reliability | Durable dispatch state, unique submission/trial identities, atomic parent claims, leases/heartbeats, bounded attempts, replay of saved training | Ownership gaps below; physical worker loss and full recovery have not been exercised end to end |
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

### 1. High priority: parent ownership does not fence every tuning child write

Existing experiment completion and tuning job updates check worker tokens, and the suites cover several stale-owner rejection cases. Two related boundaries still permit operations from a worker whose parent tuning lease has been replaced:

1. [TrialRepository.claim](../src/ml_pipeline_pro/tuning_store.py) matches the child ID/project/status but does not validate the parent job's current token. [ExperimentRepository.claim](../src/ml_pipeline_pro/jobs.py), when passed a tuning job ID, also permits taking a running child without verifying the parent owner, even when the child's lease has not expired. After replacement, an old caller can reclaim these child records from the new worker.
2. [ExperimentRepository.finish_tuning_test](../src/ml_pipeline_pro/jobs.py) has no worker-token argument or parent ownership predicate. The execution layer checks ownership before calling it, but replacement can occur between that check and the database write. A stale result can then set `test_evaluated` and replace the selected experiment's metrics/artifact references.

**Probe evidence:** In a dedicated random `mlpp_audit_*` database, claim a tuning job as `old`, expire its lease, and claim it as `replacement`. Insert a running trial/experiment owned by `replacement`; child claim calls with `old` still return records owned by `old`. Insert a succeeded, unevaluated child; `finish_tuning_test` accepts the write while the parent is owned by `replacement`. All three repository operations were confirmed, and the disposable database was removed. Local results are retained in ignored `artifacts/project-audit/2026-10-06/repository-probes.json`.

This demonstrates missing guards at the repository boundary. It is not an observed failure in the existing serial queued workflow or a full concurrent takeover test. Nevertheless, the caller's separate ownership check is insufficient to guarantee stale-result rejection.

**Required follow-up:** Fence child claims and final evaluation persistence with parent ownership, using an atomic ownership/commit design that accounts for writes across collections. Add regression cases that pause the old worker at these exact boundaries, transfer ownership, then resume it. Reject old claims/commits while allowing the replacement to finish. Do this before increasing worker/trial concurrency.

### 2. Medium priority: recovery validation stops short of process-loss recovery

The recovery tests simulate storage errors and explicitly expire leases before invoking execution again. Live integration verifies queued execution and cancellation, but does not kill a worker during training/final evaluation and wait for Beat-driven recovery. Redis/MongoDB outages during heartbeats and late commits also need focused coverage. The host unit suite uses in-memory repositories, so passing it alone does not validate MongoDB ownership predicates.

**Required follow-up:** Add controlled worker termination/restart and dependency outage cases, verify scheduler redispatch and attempt exhaustion, and verify no duplicated successful results or accepted stale writes. Collect worker/scheduler coverage or document it separately; CI currently prints coverage without enforcing a threshold.

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

The current unit-only coverage output rounds combined statement/branch coverage to 77%. The earlier full-suite report measured 84.93% in the host process; it does not include worker/scheduler execution inside containers. These are different measurements and should not be treated as a coverage regression. See [test-validation.md](test-validation.md) for the original environment, counts, and repeat commands.

Both current suites emit the existing TestClient deprecation warning. No live model-provider evaluations, production workload benchmarks, physical worker-loss recovery tests, or restore exercises were run. Dependency advisory results are scoped to the audited releases and date, not a guarantee about application security.

## Next work, in order

1. **Correct the recovery ownership findings and add boundary regression tests.** Preserve the current serial limits until stale claims/final evaluation writes are rejected reliably.
2. **Start milestone 4 with a provider-independent tool contract.** Map experiment/tuning reads, comparison, submission, and cancellation onto existing schemas/project access; use deterministic provider stubs first.
3. **Add the conversational slice.** Configure the provider, persist project-scoped dialogue/action evidence, request missing inputs/budgets, and evaluate grounded responses and unauthorized/invalid actions.
4. **Implement milestone 5 monitoring.** Add operational metrics and sample inference observations before dashboards, alert windows, and evidence-linked diagnosis.
5. **Implement milestone 6 code generation.** Provide validated supported snippets with provenance and review boundaries; define isolation before enabling execution.
6. **Finish milestone 7 for shared deployment.** Identity/roles/TLS, authenticated services, immutable data/object storage, retention, restore tests, operational probes, deployment manifests, and onboarding.
7. **Run the measurement plan.** Establish baselines and reproducible workload results before using the proposed improvement percentages.

The next feature remains conversation; fixing recovery and measuring its behavior are prerequisites for expanding execution safely. The full release criteria remain in [PLAN.md](../PLAN.md#completion-criteria).

## Reading a local tuning manifest

A manifest containing `test_evaluated: false` and only validation metrics is expected for a tuning trial. Trial records keep validation-only outcomes even after selection. The winner's experiment receives the test metrics after final evaluation.

The service-free tuning demo writes trial artifacts under `artifacts/demo/EXPERIMENT_ID/local/`, then writes an updated winner manifest under `artifacts/demo/EXPERIMENT_ID/final/`. The original `local/manifest.json` remains unchanged, even for the winner. Use the artifact references in `artifacts/local-tuning/JOB_ID/summary.json` to find the final manifest. API clients should follow the selected experiment's current `artifacts` references or download endpoint. If `final_evaluation` is `skipped_budget`, no evaluated winner is available for version registration.
