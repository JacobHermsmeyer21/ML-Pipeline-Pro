# Prepare the CPU laptop for local deployment

- Status: implemented; live laptop acceptance incomplete after retained failed rerun
- Date: 2026-10-18
- Source baseline: `91b0aef` / `person-a/conversation-foundation`
- Request: correctness takes priority over speed; prepare the CPU laptop for the local class demo. Jacob selected a maximum five-minute wait for one complete AI reply.
- Human reviewer/approval: Jacob approved this complete five-minute plan on October 19, 2026: "ok I approve the 5 min plan, implement it and rerun the demo test".
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

Jacob approved on October 19, 2026: "ok I approve the 5 min plan, implement it
and rerun the demo test". Approval covers the explicit five-minute laptop profile, increased allowed
configuration ceilings, coordinated proxy/client/evaluation budgets, diagnostic
instrumentation and the local deployment/rehearsal above. Correctness assertions,
the complete-reply ceiling, original deadlines and ownership fences remain binding.

## Implementation outcome

October 19 implementation is complete under Jacob's approval. The explicit
profile, coordinated deployment/client budgets and payload-free boundary logs are
implemented; verification and live laptop acceptance are being recorded separately.
Default budgets and every semantic assertion remain unchanged. New assertions
require complete replies to meet the selected client timing criterion. New tests
check finite configuration ceilings, profile isolation, shared multi-call expiry,
cancellation, failed/late response retention and deployment routing/replica safety.

Separate read-only review by the `timing_review` agent (same OpenAI vendor;
different-vendor review unavailable) covered timeout arithmetic, cancellation
scopes, persisted ownership/replay, rendering and the original semantic gates.
Its P1 finding identified missing Kubernetes backend DNS qualification; the
renderer now preserves all three service FQDNs, with exact regression assertions.
Its P2 finding identified automatic continuation after failed evaluation calls;
the laptop profile now stops after the first failed case and retains the unused
scenario list. Original failure/count gates remain binding. Review did not execute
services; live cancellation, actual runner idleness and full acceptance remain
execution requirements. No ownership/state-machine/concurrency redesign was made.

Verification before the implementation commit: locked sync, Ruff lint/format,
dependency compatibility and package build pass. The full fast run passes 644
cases (73 integration deselected, 81% rounded coverage); 23 final focused checks
also pass, including two subsequently added profile/late-response regressions.
All 63 ordinary integration cases pass against the rebuilt laptop Compose stack;
all installed application-module hashes match the checkout and both AI domains
use 240/270-second budgets. Local links/anchors and 13 PowerShell examples pass.

The first full recovery execution passes nine cases and fails one at the existing
90-second `docker compose start worker` command limit before its final-evaluation
recovery assertions. Its saved job remains evaluating; no recovery pass is inferred.
After preserving/stopping the old presentation stack, the unchanged boundary
passes alone in 63.92 seconds and a fresh full isolated run passes all ten cases
in 349.15 seconds. No assertion, command limit or application source was changed
between these runs. The original incident and raw logs remain retained; its
underlying Docker/scheduling cause is unresolved. The presentation volumes remain
intact. Live model gates, Kubernetes rollout/restart and the complete walkthrough
are the next execution steps and are not established by these checks.

uv warns that its workspace cache may enter the source package. Archive inspection
finds zero cache entries and confirms both new modules in the wheel; build exits
zero. This warning is recorded rather than suppressing it or changing packaging.

Live execution on committed `533a2ed` is now retained in the
[five-minute evidence](../evidence/2026-10-19-laptop-five-minute/README.md).
Kubernetes backend smoke, direct replay through both model API pods and a controlled
node stop/start with identical saved records and verified artifact hashes pass.
Initial cold dependency rollout and multi-platform import failures remain recorded;
continued checks use the unchanged rollout limits. All five implementation CI jobs pass.

The full plugged-in walkthrough fails: its first correct inspection completes in
210.532 seconds, but the comparison/proposal request loses client delivery after
132.937 seconds when Kubernetes terminates the gateway for failed liveness. The
serving model API persists an honest tool transport-error reply after 135.566 seconds,
with no facts, proposal or submission. The immediate delivery failure is confirmed;
the wider probe/DNS delay resource cause is unmeasured. Original 270-second deadlines
remain intact. Runtime logs end idle. Proposal confirmation, generated Python and
measured diagnosis are not reached; F1/F2 and full readiness are not established.

The separate dialogue gate passes eight cases then fails during a recorded Windows
sleep in the ninth; the tenth remains unrun. AC changes from connected to battery.
The 4902.953-second case duration includes sleep and cannot measure active CPU
inference or verify timely expiry. The original snippet gate is unrun in this profile.
Live under-load deadline expiry and human quality review remain open. No failure
was repaired, retried or converted to a skip/pass. A separate same-vendor evidence
review validates archive/source hashes, JUnit/CI counts and the restart sequence;
its reporting findings add gate-specific sleep/power context and avoid claiming the
exact internal tool socket mechanism. Different-vendor review remains unavailable.

The implementation is committed and pushed as `533a2ed`; its scope is delivered,
but acceptance is incomplete. No additional timeout/probe/resource/model change
was made. The [deployment-health follow-up](2026-10-19-laptop-deployment-health-plan.md)
requires renewed human review before implementation, as required for a material
deviation from this timing design. See the [durable finding](../memory/laptop-inference-probe-restarts.md).
