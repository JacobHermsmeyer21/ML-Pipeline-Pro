# Project review and full demo — October 20, 2026

Reviewed application revision: `4704f2e` (published `origin/main`). The working
branch, `person-a/conversation-foundation`, was clean and 26 commits behind main;
it was fast-forwarded without rewriting history. The review covers the course
checklist, active architecture, recent dashboard/Claude changes, persistence and
training boundaries, deployment configuration, tests and retained execution evidence.
It is a source review and fresh execution record, not an independent concurrency
review or a security certification. Application code and test assertions are unchanged.

## Assessment

The project implements the minimal course feature set: separate model, tuning and
monitoring APIs; durable project-scoped MongoDB records; serial PyTorch training
and Optuna tuning; local LangChain/Ollama dialogue and generated drafts;
Prometheus/Grafana; Docker/Kubernetes configuration and CI. The Astro dashboard
now exposes CSV preparation, immutable column versions, training, exact action
confirmation and permanent deletion. Public Vercel/Modal deployment remains a
draft design, not a delivered service.

Implementation is ahead of current deployment acceptance. The retained workstation
demo succeeds, and standalone laptop model gates succeed with the five-minute
profile. Neither establishes a passing complete bounded gateway workflow on this
CPU laptop. The current Kubernetes startup transaction defect is separately
confirmed and still present in the deployment configuration.

## Findings, in priority order

1. **High — fresh Kubernetes startup can report ready and then reject writes.**
   [The manifest](../../deploy/kubernetes/stack.json) still uses
   `mongodb://mongo:27017/?directConnection=true`. The
   [retained controlled reproduction](../memory/mongodb-preinit-sessions.md)
   confirms that an early RSGhost handshake can retain unsupported-session state:
   ping succeeds after election, but the first lifecycle-fenced dataset transaction
   returns storage 503. The [repair plan](../plans/2026-10-19-kubernetes-mongodb-sessions-plan.md)
   awaits approval. Preserve transactions and test the pre-initialization connection
   boundary; a warm-server pass does not close this defect.
2. **High — complete bounded AI delivery on this laptop remains open.** The
   [laptop evidence](../memory/laptop-inference-probe-restarts.md) records gateway
   restarts and replies exceeding the finite turn window. Two probe-free/direct-AI
   unbounded workflows pass, but those are diagnostics. A new bounded run must
   retain gateway routing, probes and semantic assertions. This review does not
   propose another timeout increase or infer a resource cause from slow responses.
3. **Medium — the README's “full stack” command starts only compatibility services.**
   Its bare `docker compose up` starts API, worker, scheduler, MongoDB and Redis.
   It does not activate the three-domain topology, uploads, Grafana/Prometheus or
   local AI. Those need the overlays documented in the
   [dashboard guide](../guides/dashboard.md#start-on-this-desktop).
   A new user following only that installation block cannot reproduce the
   advertised complete workflow. The README does disclose disabled chat/uploads
   later, but the initial installation label overstates that command's coverage.
4. **Medium — Claude support has no retained live generation acceptance.** The
   [adapter plan](../plans/2026-10-20-claude-chat-backend-plan.md#implementation-outcome)
   records injected-client tests and a successful model-list request, with no
   Messages call. Actual dialogue, tools, snippet and monitoring behavior therefore
   remain unverified for that provider. The course still requires the local
   LangChain path; Claude is an optional backend, not evidence for that requirement.
   This run uses the installed local model and makes no paid model calls.
5. **Medium — separate boundary review remains incomplete.** The
   [dataset-controls guide](../guides/dashboard.md) and Claude plan retain open
   independent review gaps. Existing ownership/recovery tests and self-review
   cannot replace the requested separate review of deletion/publication locks,
   state transitions or the new provider boundary. No independent reviewer was
   available in this execution.

## Source-grounded strengths and boundaries

- [Training](../../src/ml_pipeline_pro/training.py) fits normalization on training
  rows and selects epochs on validation metrics. Final test evaluation follows
  selection. [Preparation](../../src/ml_pipeline_pro/dataset_preparation.py)
  preserves train-fitted encodings and uses integer stratified holdout counts.
- [Factories](../../src/ml_pipeline_pro/main.py) provide separately deployable
  domain APIs while retaining compatibility routes. Shared transactional tuning
  ownership and serial worker execution remain the documented contracts.
- The [dashboard](../../src/ml_pipeline_pro/dashboard_api.py) serves committed
  build assets with explicit CSP hashes. Its new Playwright suite mocks API
  responses; its passes demonstrate browser behavior, not actual training or AI.
- Monitoring distinguishes measured samples from seeded delays and generated
  interpretation. Snippets are validated drafts and never automatically executed.
- Native filesystem locks/shared durable storage are real deployment constraints.
  The public hosting design must resolve them before implementation; a static
  frontend deployment alone would not deliver the application.

## Fresh verification before the demo

Host: Windows, AMD Ryzen 3 3350U / Radeon Vega 6 CPU laptop. The user explicitly
requested continuing on battery. The old `mlpp-laptop-five-minute-control-plane`
test-cluster container was stopped with its data preserved, avoiding duplicate
application stacks. Its default kubectl context was absent; the initial inspection
using that context failed and is not a Kubernetes verification result.

- Locked dependency sync: pass after allowing package network access. Initial
  sandbox network failures are retained separately; they are not product failures.
- Ruff lint: pass. Ruff formatting: pass, 275 files. Installed dependency
  compatibility: pass.
- Fast suite and package build: running when the source report was first written;
  final results will be recorded below. No test assertion or opt-in gate was changed.
- Node 24 and a browser were not found in the standard installed locations.
  Frontend build/browser results are outstanding until actually executed.
- Full ordinary, isolated recovery, Kubernetes and real-model results below must
  come from this run; historical records keep their own revision and environment.

## Demo execution and final verification

Pending. Run the documented five-minute Compose/local-model path with current
source, actual dataset/model IDs, serial workers, exact bounded-proposal approval,
saved history/draft replay, verified artifacts and measured monitoring. Generated
Python must remain unexecuted. Report any failure at its observed boundary and
keep successful backend checks separate from full AI acceptance.

Raw local captures are under `artifacts/review-demo-20261020/`; retained evidence
and final commit/push status will be linked after execution.
