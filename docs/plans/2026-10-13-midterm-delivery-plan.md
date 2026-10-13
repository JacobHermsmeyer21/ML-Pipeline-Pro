# Minimal deployable midterm

- Status: approved scope; implementation in progress
- Date: 2026-10-13
- Source baseline: `28445bc` / `person-a/conversation-foundation`
- Request: all nine course requirements in a minimal working demo next week
- Human reviewer/approval: Jacob, October 13; see approval below
- Independent review: seek a separate boundary reviewer; no new review completed yet

## Proposed behavior and purpose

Deliver one reproducible classification walkthrough covering C1-C9 on one machine.
Keep existing training, Optuna tuning, persistence, artifact checks, the serial
worker and recovery scheduler. Complete three independent REST services, small
live monitoring, guided local-model workflows, the four existing Python profiles,
and local Kubernetes with exercised GitHub Actions rollout/smoke checks.

## Clarification and critique

Jacob confirmed all nine requirements are due for the midterm with a minimal demo.
Broader adapters/runtime compatibility, concurrent training, advanced drift,
automatic remediation, generated-code execution, a custom UI, public/cloud hosting
and research benchmarks are deferred. Supplied course instructions stay unchanged.

The retained original conversation gate passed 3/10 and A2 passed 6/7. Keep these
failures visible. Use guided inspection, training preparation and tuning workflows;
application code checks explicit inputs/budgets and human confirmation. Never
borrow missing limits from history or repair generated code. Schema-constrained
generation is a candidate to evaluate on the locked runtime, not proof of semantic
correctness or permission to weaken original gates.

Independent databases would break the tuning parent/child transaction. Separate
processes sharing code/image/database reduce extraction risk. Keep the compatibility
factory and existing fixtures. A4's unapproved 1,000/10,000-record workload is
deferred: demonstrate retrieval, pagination, scoping and index use at declared demo
scale without speed claims. Narrow A3 to one observed issue; retain older plans and
criteria without retrospectively declaring them met. No intent questions remain
for this approved scope; material deviations require renewed review.

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | Preserve HTTP contracts and native draft capability. | Existing API checks and reproduced native HTTP draft regression. |
| F2 | Functional | Independent model/conversation, tuning and monitoring services behind the public origin. | Owned-route factory checks; real routed workflow/replay/access checks. |
| F3 | Functional | Guided local-model dialogue with explicit inputs and actual history. | Original ten scenarios pass on final profile; human quality review. |
| F4 | Functional | Four existing LangChain/local-model Python profiles. | Full seven-case A2 gate and configured HTTP draft workflow; usefulness review. |
| F5 | Functional | Running sample workload, dashboard and grounded seeded-issue summary. | Measured update/issue timing; actual observations/logs; model summary and proposed checks. |
| F6 | Functional | Kubernetes test-cluster deployment and exercised CI/CD. | Rollout/smoke and two API replicas with replay; singleton serial worker. |
| F7 | Functional | Complete clean-checkout tutorial and retrieval evidence. | C1-C9 evidence index, commands, outputs and gaps. |
| N1 | Reliability | Preserve ownership, artifacts, access and deadlines. | Fast, ordinary and serial recovery gates; independent boundary review. |

## Constraints and scope

Preserve `/api/v1` schemas/errors/correlations, project-scoped references and
submission idempotency. Fit preprocessing on training rows; select using validation
and evaluate holdout after selection. Preserve tuning configurations/IDs/deadlines
and the same-transaction parent-write fence. Keep one CPU training job, verified
token/context admission, secret redaction and opt-in service/model gates. Drafts
require human review and never execute in the application.

## Design

Implement in separately checked/committed slices:

1. Correct the tutorial origin/current-state text. Forward `generate_snippet`
   through the native lazy lifecycle, retaining prepare, replay, budgets and close.
2. Add model-management/conversation and tuning factories with existing routers,
   repositories and shared middleware; retain `main:create_app` compatibility.
   Use thin public routing with shared MongoDB replica set, Redis, worker/scheduler
   and artifacts. Update extraction fixtures; never replace fenced DB writes
   with separate HTTP mutations.
3. Add a project-scoped monitoring REST API, timestamped observations, bounded
   summaries and Prometheus metrics. A declared producer measures actual sample
   workload latency/errors and records safe logs. Provision one Grafana dashboard
   and one threshold issue. Proposed demo refresh/scrape: 15 seconds; measure
   visibility against a 30-second target, without production guarantees. Identify
   injected delay. Local-model explanations cite supplied observations, label
   causes as hypotheses and never execute proposed fixes. Missing data/labels are
   unknown, not zero. Add persistence schemas/indexes and real-store coverage.
4. Narrow AI work to guided supported workflows and one evaluated installed
   profile, retaining durable history/actions and all four A2 profiles. Application
   code checks supplied inputs and retrieves actual validation history before
   interpretation. Preserve original gates and safe failure/direct API behavior.
5. Add single-node Kubernetes resources/probes/Secrets and persistent dataset/
   artifact paths. Deploy a tagged image in kind and run GitHub Actions rollout/
   smoke after checks. Demonstrate two API replicas; worker/scheduler stay singleton.
6. Execute a clean-checkout tutorial and retrieval/index checks. Retain source,
   model/runtime identity and raw evidence. Reserve final two project days for
   integration/documentation; scheduling guidance is not a delivery guarantee.

Document new routes/configuration in the API reference and `.env.example`.

## Acceptance and verification

Run standing fast gates and build package changes. Follow the
[verification guide](../guides/verification.md) for ordinary integration with both
`MLPP_RUN_INTEGRATION=1` and `MLPP_RUN_WORKER_INTEGRATION=1`; run affected isolated
recovery with `MLPP_RUN_RECOVERY_INTEGRATION=1` separately and serially. Keep original
assertions/scenarios. Added tests reach the affected HTTP, lifecycle, scope or
storage boundary. Retain command output/JUnit, source identity, workload/model and
observed timing. YAML, mocks, tutorials or combined successes across failed runs
do not establish acceptance. Record independent reviewer/scope/findings/resolutions;
missing services, review, human validation and remote CI remain gaps.

## Risks and rollback

Docker/hardware/runtime availability can block real gates; report and complete
unaffected work. Extraction can affect origins, mounts and recovery fixtures; keep
the compatibility factory and rerun real gates. Revert factories/routing without
rewriting records. Disable additive monitoring/AI features while preserving
observations, history and original artifacts. Never force-push.

## Human review and approval

Jacob confirmed "All nine, with a minimal working demo" and approved the scope
review: "ok, i like all of your reccomendations. add/edit the nessicary
documentation and get to work." This approves the smaller architecture/workflow
direction and its documentation/implementation. It does not approve removing a
course row, weakening tests, public hosting, code execution, independent DB writes
or concurrent training. Record renewed review for material deviations.

## Implementation outcome

Documentation scope recorded; application implementation pending. No course row
closed. Slice outcomes will record commands/evidence, test justification, reviews,
durable findings and commit/push results.
