# Prepare the CPU laptop for local deployment

- Status: awaiting human review; implementation pending
- Date: 2026-10-18
- Source baseline: `91b0aef` / `person-a/conversation-foundation`
- Request: correctness takes priority over speed; prepare the CPU laptop for the local class demo. Jacob selected a maximum five-minute wait for one complete AI reply.
- Human reviewer/approval: pending review of this design. The deployment target and waiting tolerance are confirmed; implementation of the timing changes below is not yet approved.
- Independent review: seek separate review of deadline arithmetic, cancellation and persisted ownership boundaries before declaring the change reviewed; reviewer availability unknown.

## Proposed behavior and purpose

Deploy the existing three-service application, local pinned Qwen model, serial
worker, MongoDB/Redis and monitoring on the Acer presentation laptop. Allow a
complete AI reply to take up to **300 seconds**, while retaining grounded facts,
strict generated-code checks, exact action confirmation and durable replay.
Use the existing local Kubernetes deployment and CI/CD path. Mark readiness only
after the complete workflow passes on that machine through the deployed gateway.

## Clarification and critique

Jacob confirmed the CPU laptop/local class demo and selected "Up to 5 minutes"
for one complete reply. This replaces speed as the immediate optimization goal;
it does not approve indefinite waiting or five minutes for each internal call.
The [single diagnostic](../evidence/2026-10-18-laptop-qwen-diagnostic/README.md)
shows a correct first read after 99.359 seconds, including 88.330 seconds prompt
processing. It does not establish a complete answer, snippets or monitoring.
Several internal calls may exhaust five minutes even when each call is valid.

The infrastructure already exists: [Kubernetes](../guides/kubernetes-demo.md),
[domain services](../guides/domain-services.md), [monitoring](../guides/monitoring-demo.md)
and the [combined tutorial](../guides/midterm-walkthrough.md). Rebuilding this
architecture or introducing an asynchronous inference queue is unnecessary for
one presenter submitting requests sequentially. Raising only an environment
variable cannot work: configuration caps, proxy/client waits and suite deadlines
also prevent the proposed workload. A smaller model already failed semantics.

Use the same evaluated model/runtime/prompt first. If any required result cannot
complete correctly within five minutes, retain the failure and revisit scope
with Jacob; do not silently extend the limit, replace outputs or drop scenarios.
The active session is on the Ryzen 7 workstation. Laptop execution remains a
separate required step; workstation results cannot close laptop acceptance.

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | Complete the original ten dialogue and seven snippet scenarios with their existing semantic assertions and no retries/output repair. | All selected cases pass under the explicitly identified laptop timing profile; failures and historical default-profile results remain retained. |
| F2 | Functional | Complete the deployed real-ID workflow: training, Bayesian tuning, inspection/history, proposed tuning, exact confirmation, draft/replay and measured monitoring advice. | Saved API bodies, IDs, metrics, hashes and human output review from the laptop gateway; generated Python is not executed. |
| N1 | Timing | Each successful complete AI reply returns within 300 seconds measured at the client, including all internal calls and persistence. | Per-request monotonic timings for every live scenario and deployed walkthrough; timeout/failure remains a failure. |
| N2 | Reliability | Expiry stops client waiting, preserves truthful saved state and never creates an automatic generation/submission retry or renews a turn's original deadline. | Deterministic boundary checks, real-MongoDB ownership/replay checks and an exercised deployed timeout with subsequent runner-idle inspection. |
| N3 | Deployment | Rebuild and run the existing local topology, two model API replicas and one serial worker, preserving data across a controlled restart. | Laptop rollout, backend smoke, direct replica replay, restart/readiness and artifact hash checks; AI requests remain sequential. |
| N4 | Provenance | Identify the source/image, machine, runtime, artifact/tokenizer, timing profile and actual outputs. | Safe retained evidence and a concise start/rehearsal guide; no claim based solely on pod readiness or backend smoke. |

## Constraints and scope

Preserve `/api/v1` schemas, scoped records, correlation IDs, submission keys,
immutable turn deadlines, transactional ownership fences, training/validation/test
separation and artifact integrity. No model pull, runtime upgrade, prompt/schema
change, generated-code execution or training concurrency change. Default chat
timeouts remain 20 seconds per model call and 60 seconds per turn. This plan
changes allowed configuration bounds and adds an explicit deployment profile.

Use the existing single-node storage and loopback-accessed API/Grafana demo.
Public hosting, a new frontend and production hardening remain outside the
[approved class scope](../project/midterm-scope.md). Existing data/volumes and
unrelated clusters are preserved. New routes or persistence states are unnecessary.

## Design

1. **Align explicit budgets.** Extend the two chat timeout validation ceilings in
   [settings](../../src/ml_pipeline_pro/config.py) to 300 seconds, retaining finite
   positive values and model timeout <= turn timeout. The opt-in
   `laptop-five-minute` profile selects **240 seconds per model call** and
   **270 seconds per complete turn**, leaving 30 seconds within the user's
   300-second response criterion for cleanup/response delivery. These are caps,
   not per-call allocations added together. Confirmed-action and dependency
   timeouts, model/tool-call counts and token limits remain unchanged.
2. **Carry budgets through deployment and clients.** Add explicit laptop Compose
   and Kubernetes overrides using the existing evaluated local-AI setup. Set the
   model and monitoring API timeouts consistently. Render the gateway's laptop
   configuration from its canonical configuration with a **310-second read
   timeout**, preserving routing, correlation IDs and disabled retries. Keep the
   existing base gateway configuration unchanged. The walkthrough's explicit
   timing-profile option uses a **300-second HTTP wait** for AI requests and
   records elapsed times; ordinary backend requests keep their existing budgets.
   Gateway/client socket waits are transport bounds, not evidence of a hard wall
   deadline. A successful response exceeding 300 seconds fails acceptance.
3. **Preserve failure correctness.** Instrument elapsed time at preparation,
   token admission, inference, cancellation and persistence boundaries before
   attributing the earlier API timeout overrun to a cause. Exercise expiry at the
   failing boundary under laptop load. Preserve original stored deadlines and
   owner checks; an interrupted request must remain inspectable by its existing
   identity. Inspect actual runner activity before any later request following
   cancellation. Any required execution/concurrency/state-machine redesign needs
   an updated plan and renewed review before implementation.
4. **Evaluate the same behavior under named timing profiles.** Add an explicit
   `--timing-profile laptop-five-minute` option to the existing local-model
   evaluations; default behavior/budgets stay unchanged. Reuse every original
   scenario and semantic assertion, including count/schema checks and generated
   draft validation. Record selected settings in the output. Bound the ten-case
   dialogue suite at **3300 seconds** and seven-case snippet suite at **2400
   seconds**, allowing their per-turn budgets plus setup/admission margin. Keep
   existing request/token/generation caps. These suite budgets can span many
   replies and are not the user's per-reply allowance. Report new-profile passes
   separately from the historical faster timing criterion.
5. **Rehearse and freeze.** Rebuild the image, deploy to a newly named local kind
   cluster, enable the installed pinned model/tokenizer, warm it explicitly, then
   run the complete walkthrough through the gateway. Retain output for human
   review. Record image identity/source revision and exact launch/port-forward
   steps; rehearse a normal stop/start with saved records and artifacts intact.
   Run build/tests before live inference, avoid concurrent model calls and do
   not simultaneously leave duplicate Compose/host AI stacks running.

Update [`.env.example`](../../.env.example), README configuration documentation,
local-AI/Kubernetes/walkthrough guides, evaluation fixtures and affected tests.
Keep historical workstation/laptop results distinguishable from new evidence.

## Acceptance and verification

Run the [fast gates](../../AGENTS.md#verification-commands) after implementation.
Test new allowed/rejected limits, unchanged defaults, profile selection/isolation,
multi-call total expiry, exact payload/token admission, proxy routing/error
behavior, client timings and replay without generation. Changed timing-bound
tests must cite the newly reviewed requirement; do not relax semantic assertions.
Validate rendered Compose/Kubernetes configurations and build the actual image.

Run [ordinary integration](../guides/verification.md#ordinary-integration) with
both `MLPP_RUN_INTEGRATION=1` and `MLPP_RUN_WORKER_INTEGRATION=1`, including
conversation store/action/service/dispatch, monitoring and draft coverage. Run
the [isolated recovery suite](../guides/verification.md#run-the-suite) serially
with only its separate recovery flag. Require the branch's deployment CI checks,
the actual laptop Kubernetes smoke/replica replay and the live evidence in F1-F2.
Do not run destructive recovery against the presentation cluster.

For timeout verification, retain request timing, saved interrupted/failed state,
subsequent history/replay and runner-idle evidence. A deterministic stalled
transport alone does not resolve the previously observed live overrun. Seek
separate boundary/arithmetic review; disclose unavailable review. Save safe raw
results under `artifacts/laptop-deployment-readiness/`, retain required evidence
under `docs/evidence/`, and update status/memory only to the scope actually proved.

## Risks and rollback

The five-minute target may fail on longer follow-up prompts, snippets or a loaded
laptop. Longer ownership deadlines delay interruption recovery; preserve their
original identities/expiry. CPU contention can affect API readiness and timeout
scheduling. A client timeout may leave the runtime computing. None is resolved
by configuration alone. Report the failing boundary and review the next action.

Rollback removes the opt-in deployment overrides and restores default clients;
it does not delete records, model weights, PVCs or artifacts. Let an existing
longer turn finish/expire before restarting into shorter settings. Preserve safe
failure evidence. Do not promise the demo is ready until every required gate and
human review has completed on the target arrangement.

## Human review and approval

Pending. Review covers the explicit five-minute laptop profile, increased allowed
configuration ceilings, coordinated proxy/client/evaluation budgets, diagnostic
instrumentation and the local deployment/rehearsal above. Jacob's target/wait
answers define the requirements; approval of this concrete implementation scope
must be recorded before application or deployment changes begin.

## Implementation outcome

Planning only. No application, gateway, evaluation assertion or deployed resource
has changed. Laptop gates, timeout verification, rehearsal and implementation
review remain outstanding. Commit/push of this plan is recorded in the session
handoff; it does not establish deployment readiness.
