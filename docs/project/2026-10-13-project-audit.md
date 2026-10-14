# Project audit and Person A handoff: October 13, 2026

This is the initial audit of `7754826`, retained as historical evidence. Subsequent
approved midterm implementation and verification are tracked in [current status](project-status.md),
[course coverage](course-requirements.md) and [delivery evidence](../evidence/2026-10-13-midterm-delivery/README.md).

Person A stopped after implementing A2 Python snippet generation, with its live
acceptance still failing. A1 conversation quality also remains unresolved. A3
diagnosis and A4 retrieval/onboarding have written plans awaiting approval and
no delivered implementations. The classification/tracking/tuning backend works
within its existing serial CPU scope; the full course deliverable is incomplete.

## Audited revision and published state

Audited application revision: `7754826a054ea70882b3ac9a53179d215ccb4cf8`
on `person-a/conversation-foundation`. The last application commit is
`7754826`, **Implement reviewed Python snippet generation with retained model
gaps**, October 10, 2026, 8:53 p.m. America/New_York.

After fetching origin, the branch had zero local-only or remote-only commits.
It contains 13 commits beyond `origin/main` (`f0ec2ad`), with no incoming main
commits. Person A's work is published on its branch but has not been merged into
main. Origin advertises only main and this Person A branch; no Person B branch
or subsequent Person B implementation is visible there. The working tree was
clean before this audit. Preserved stash work is excluded from delivered scope.

This audit inspected course requirements, all task/approval records, the source
and test inventory, critical application boundaries, deployment/CI, tutorials,
and retained model/service evidence. It reran fast checks, packaging and a
targeted HTTP diagnostic. Application code and test assertions were unchanged.
This is a source/evidence audit with a reproduced defect, not an independent
implementation review or an exhaustive security/concurrency proof.

## Where Person A left off

The [two-person allocation](../plans/2026-10-08-two-person-course-completion-plan.md#accountable-tasks)
assigns A the AI workflows and evidence, and B services/monitoring/deployment.

| Task | Implemented or prepared | What prevents completion |
| --- | --- | --- |
| A1: conversations and history-based suggestions | Locked LangChain/ChatOllama integration; typed tools; exact selected-profile token admission; grounded reads; MongoDB turns/proposals; chat/history/action routes; confirmation, replay and recovery; native typed completion | Last original live conversation gate passed only 3/10. Reliable guidance, missing-input handling, correct tuning budgets and status/evidence handling remain unproven. Independent review, human quality review and clean-checkout onboarding remain outstanding. |
| A2: generated Python | Four profiles: list experiments, compare experiments, submit training, submit tuning. Local-model generation, restricted AST/API validation, saved review-required drafts/provenance, shared turn budgets and deterministic/store tests | Last seven-case live gate passed 6/7. Training draft omitted `Idempotency-Key` and was rejected. Earlier runs failed different cases, so combining their individual successes would not prove acceptance. Human usefulness review and independent boundary review remain outstanding. |
| A3: monitoring diagnosis | [Plan prepared](../plans/2026-10-08-person-a-monitoring-diagnosis-plan.md) | Human approval and B2's monitoring evidence contract pending; no monitoring service or diagnosis implementation. |
| A4: retrieval evidence and AI onboarding | [Plan prepared](../plans/2026-10-08-person-a-retrieval-evidence-plan.md) | Reviewed workload/budgets, representative query plans/latency evidence and complete AI onboarding pending; execution has not begun. |

A1 approval is recorded October 7; typed completion and A2 approvals are recorded
October 10. A2 approval does not approve A3/A4. The allocation itself still says
awaiting review. These approval states do not prevent investigation or the
already approved work from continuing within its recorded scope.

The last original A1 gate is the
[October 10 typed-completion run](../evidence/2026-10-10-typed-completion/results.json),
before A2. Seven scenarios failed: guided read, comparison/history suggestion,
missing runtime, missing objective, missing tuning limits, hostile record and
queued/status evidence. Its saved tuning proposal used 40 seconds per trial
instead of the requested 10, and missing-limits handling borrowed old limits.
An additional diagnostic observed repeated reads ending at the output limit.
No mutation was dispatched by the evaluation.

The [A2 evidence](../evidence/2026-10-10-a2-snippets/results.json) retains four
failed suite runs, ending at 6/7. It explicitly records that the original A1 gate
was not rerun. A2 therefore neither repairs nor supersedes A1 acceptance.
All 40 current application module hashes match the A2 evidence manifest.
Archive CRC checks and all 103 A2 / 202 typed-completion indexed member hashes
pass. This establishes evidence integrity and source identity, not model quality.

## New findings from this audit

### Medium: the native Ollama HTTP lifecycle loses snippet generation

[The HTTP client lifecycle](../../src/ml_pipeline_pro/conversation_api.py)
wraps an `OllamaConversationModel` instance or subclass in `_LazyOllama`, which
exposes `generate` and `close` but no `generate_snippet`.
[ConversationService](../../src/ml_pipeline_pro/conversation_service.py)
discovers snippet support from that exposed method. With the wrapper, it sets
the snippet generator to `None` and saves a failed `model_unavailable` turn when
the model requests a draft.

The [retained endpoint probe](../evidence/2026-10-13-project-audit/snippet_route_probe.py)
uses the canonical app factory/lifespan, the real `/api/v1/chat` route, a scripted
Ollama subclass and the existing in-memory test store. The same scripted model
succeeds when passed directly to the host service (one generation call), but the
HTTP path returns a failed turn with zero snippet generation calls. A factory
control that does not trigger `_LazyOllama` also succeeds through HTTP.

Scope matters: the documented
[Qwen composition adapter](../../src/ml_pipeline_pro/conversation_qwen_counter.py)
is **not** an Ollama subclass and exposes `generate_snippet`; that factory avoids
this specific wrapper defect. The bare default adapter also intentionally lacks
a verified token counter, so the reproduced draft failure is relevant once a
configured native adapter/factory reaches generation. This probe used no live
inference, MongoDB writes or domain HTTP requests. No fix was made in this audit.

### Medium: the snippet tutorial targets the wrong port for its setup

[Local model setup](../guides/local-model-setup.md) starts the Qwen chat API on
8001, using the existing backend on 8000. The
[snippet request example](../guides/snippet-generation.md#request-and-inspect-a-draft)
posts to 8000. Following those instructions leaves the example targeting the
backend, where chat defaults to disabled, rather than the configured chat API.
Use the configured chat origin when reproducing the workflow; the published
example needs correction and a clean-checkout run.

### Low: an active conversation guide still says typed completion awaits approval

The end of [conversation development](../guides/conversation-development.md)
describes typed completion as proposed and awaiting approval, although its
[plan outcome](../plans/2026-10-09-conversation-typed-completion-plan.md#implementation-outcome)
records approval and implementation on October 10. Historical dated status
sections remain historical; current tutorial instructions should match the
approved implementation and retain its quality failure.

## Whole-project course coverage

The [course checklist](course-requirements.md#requirement-coverage-and-acceptance-evidence)
remains the acceptance source. No row is newly closed by this audit.

| Course requirement | Current source/evidence state | Remaining acceptance |
| --- | --- | --- |
| C1: environment/libraries | Locked uv environment, PyTorch, PyMongo, LangChain/Ollama and model setup exist; today's existing environment sync passes | Complete clean-checkout installation/runtime evidence |
| C2: separate services | One FastAPI app mounts tracking, tuning and conversation; Compose has API, worker, scheduler, MongoDB and Redis | B1/B2 independent model-management, tuning and monitoring REST services with preserved ownership/public contracts |
| C3: guided local-model dialogue | Host/store/routes/actions and token admission implemented | A1 original ten-scenario live gate and reviews/onboarding |
| C4: MongoDB tracking | Initial classification scope stores parameters, versions, trials and metrics with indexes and project scoping | A4 representative retrieval/query-plan evidence; preserve persistence regressions |
| C5: intelligent bounded tuning | Serial Optuna TPE, saved trials, cancellation, validation selection and recovery implemented | Reliable A1 history-grounded local-model suggestions and confirmed actions |
| C6: monitoring/diagnosis | Experiment metrics, health and logs exist | B2 observations, Prometheus/Grafana, measured refresh/alerts, plus A3 grounded summaries/fixes; these implementations are absent |
| C7: AI Python generation | A2 generation/validation/persistence code and partial real-model evidence exist | Full single-run live acceptance, HTTP-path evidence, independent and human usefulness review |
| C8: deployment/testing | Fast/API/integration/recovery tests, Docker/Compose and GitHub Actions checks exist | B3 Kubernetes manifests, exercised CI/CD rollout/smoke and supported stateless API replica scaling; deployment path is absent |
| C9: documentation/onboarding | Backend workflows and partial AI/setup guides exist | A4/B4 clean-checkout end-to-end tutorial, advanced history optimization, monitoring and service/Kubernetes demonstration |

The existing backend preserves training-only preprocessing, validation-based
checkpoint/winner selection, test evaluation after selection, project scoping,
submission keys, hash/size-checked artifacts, reserved tuning identities/deadlines,
and the shared MongoDB parent-write transaction fence. These have source and
historical regression evidence; today's fast suite does not independently
revalidate real MongoDB takeover or killed-process recovery.

Separate shared-use gaps remain: immutable dataset snapshots, artifact retention,
schema migrations and coordinated backup/restore; person-level identity/roles,
TLS and authenticated MongoDB/Redis; worker/scheduler healthchecks; concurrent
load and arbitrary network partitions. Registered CSVs are references plus
hashes, so deleting or replacing their bytes prevents reproducible reruns.
Readiness only pings MongoDB/Redis and does not establish worker progress.
Keep training concurrency at one. See the
[operational gap record](project-status.md#deployment-and-operational-gaps).
There is no retained evidence supporting the proposed research improvement
percentages, and no new remote CI or vulnerability-advisory scan is claimed.

## Verification and limits

Today's [retained audit evidence](../evidence/2026-10-13-project-audit/results.json)
records Windows/Python 3.11.5, source identity, commands, raw output hashes,
package inspection and the probe. The workspace-local uv binary was used with
the workspace cache; dependency sync/build were offline.

- Locked dependency sync, Ruff lint/format and installed compatibility pass.
- **506 fast tests pass**, 71 integration/recovery cases deselected, no selected
  skips/failures. Host combined statement/branch coverage rounds to 79%; it
  excludes container execution and cannot establish transaction correctness.
- Package build passes. Inspection verifies all 40 canonical modules in the
  wheel and excludes private environment/cache/model directories from the sdist.
  uv emitted a cache-inside-source warning; inspected package contents exclude it.
- Compose configuration validates through the existing standalone Compose binary.
  Docker CLI plugin discovery under an isolated configuration failed, and the
  default Docker daemon connection was unavailable; neither is a passing runtime
  or deployment check.
- Local Markdown links/anchors, fenced Python/PowerShell syntax, API endpoint
  documentation and `git diff --check` are validated for the final audit change.

MongoDB (27017), Redis (6379), backend (8000) and Ollama (11434) were unreachable;
ordinary integration, isolated recovery and live-model gates were **not rerun**.
The retained October 10 A2 record reports **61 ordinary integration** and **10
recovery** passes, without selected skips, against application hashes matching
this checkout. Those are historical results. Independent review, successful
clean-checkout onboarding and current remote CI status were not established.

## Recommended restart point

1. Resume A1/A2 acceptance work on the published Person A branch. Confirm the
   configured chat HTTP path and its documented origin, address native-wrapper
   capability loss where applicable, and diagnose the saved quality failures.
   Keep original scenarios, assertions and budgets fixed; material model/protocol
   changes need the existing plan/review loop.
2. Retain a passing complete A2 gate and rerun the original A1 gate against the
   final source/model profile. Obtain independent boundary review and human
   quality/usefulness review, then verify the AI tutorial from a clean checkout.
3. Review A3/A4 before implementation. Agree with B on B2's project-scoped
   monitoring evidence contract; A3 real acceptance depends on that service.
4. B still needs service extraction, monitoring, Kubernetes/deployment CI/CD and
   final onboarding. Coordinate shared files and the A/B merge, preserving the
   current transaction/recovery contracts; do not treat branch publication as
   integration into main or course completion.

The audit documentation/evidence commit and its push result are reported in the
handoff response and Git history. No application fix or course closure is claimed.
