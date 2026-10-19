# Preserve gateway liveness during laptop inference

- Status: implemented; live laptop acceptance failed and remains incomplete
- Date: 2026-10-19
- Source baseline: `533a2ed` on `person-a/conversation-foundation`
- Request: follow-up to Jacob's approved five-minute implementation and demo rerun
- Human reviewer/approval: Jacob approved on October 19, 2026: "i approve, go for it".
- Independent review: same-vendor read-only implementation/evidence review by
  `timing_review` completed; different-vendor review unavailable

## Proposed behavior and purpose

Keep the existing five-minute laptop ceiling and give the gateway a process-local
liveness endpoint in the opt-in laptop profile. Gateway readiness must continue to
report upstream availability. Collect synchronized resource/health evidence during
the original workload so wider API/DNS stalls can be diagnosed. The goal remains a
complete, correct laptop demo within the approved budgets.

## Clarification and critique

The [retained run](../evidence/2026-10-19-laptop-five-minute/README.md) confirms
liveness-triggered gateway termination and client delivery failure, before the
reply deadline. The serving model API completes an honest transport-error reply;
the initial inspection passes in 210.532 seconds. Source confirms gateway liveness
currently proxies through model API and DNS. More reply time does not fix this
failure. A separate model API pod also restarts; broad resource pressure is not
attributed. A gateway-only change may therefore be insufficient.

Choose the explicit laptop profile for this narrow change, leaving the canonical
deployment's health defaults unchanged until separately reviewed. Keep existing
application liveness thresholds, replica/resource settings and truthful readiness.
Do not disguise failed readiness as success or add automatic inference retries.
Avoid immediate model/prompt/thread changes: the immediate delivery mechanism is
measured, whereas their benefit here is untested. CPU/VM/paging attribution is an
investigation result, not an assumption of this design.

The operator must supply AC power and an awake laptop for acceptance. The separate
dialogue gate slept during case nine; it is a failed/incomplete run, not a new model
semantic failure or active CPU benchmark. No OS power policy change is proposed.
No unresolved product-intent question is required for the profile-only design;
human approval of this expanded health scope is the remaining decision.

Later [fresh AC model gates](../evidence/2026-10-19-laptop-awake-gates/README.md)
pass all original ten/seven scenarios without an application or model change;
recorded sleep intersects neither new execution window. This supplies standalone
model acceptance and leaves the diagnosed deployed gateway failure unchanged.
Jacob accepts the new saved outputs on October 19 in the
[human decision](../evidence/2026-10-19-laptop-awake-gates/human-review-decision.json).
That earlier decision accepts the saved outputs. Jacob subsequently approves this
deployment-health design on October 19: "i approve, go for it".

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | Laptop gateway liveness is local to nginx and independent of upstream/DNS. | Real nginx with unavailable upstream/DNS: local endpoint 200 while API health/readiness fails. |
| F2 | Functional | Readiness, API schemas/errors, correlation IDs, routing, no-retry mutations and saved ownership/deadlines remain truthful and unchanged. | Negative routing checks, rendered-manifest assertions, ordinary integration and original replay/replica smoke. |
| N1 | Reliability | No liveness-triggered gateway restart interrupts the original live workflow. | Same hardware/model/profile, one serial original walkthrough, pod events/restarts and client/server timings retained. |
| N2 | Measurement | Distinguish observed health failures from unmeasured resource hypotheses. | Timestamped host/VM/runtime/probe/DNS samples, provenance, access failures and sample gaps; no unsupported cause claim. |
| N3 | Performance/correctness | All required complete replies meet 300 seconds with unchanged semantics. | Original ten dialogue, seven snippet and complete actual-ID walkthrough gates; no repaired output or omitted failure. |

## Constraints and scope

Preserve serial CPU execution, two model API replicas, domain separation, locked
dependencies, installed model identity, prompts, token/call limits and exact-action
confirmation. Preserve dataset splits, validation selection, artifact hash/size,
project scoping and submission idempotency. No paid model API, new weights, generated
code execution, prompt optimization, inference thread change, resource/probe-threshold
increase or platform power-policy change is included.

## Design

In [the laptop renderer](../../src/ml_pipeline_pro/laptop_deployment.py), add an
exact nginx location `/gateway-live` returning a small local 200 response with the
existing correlation-header behavior. Change only the rendered Kubernetes gateway
liveness path to that location. Keep startup/readiness paths and thresholds as
currently defined; local liveness does not imply dependency readiness. The endpoint
is outside `/api/v1`, is not model/tool evidence and must never trigger inference.
The canonical manifest/gateway and default deployments remain unchanged. Document
the opt-in endpoint in README and the profile guide; test the rendered output.

Before rerunning inference, record available physical/commit memory, Ollama and
VM/process CPU, disk paging indicators, container/cgroup throttling and Kubernetes
health/events with monotonic and UTC times. Prefer low-frequency, payload-free
observation over repeated heavy process enumeration. Record unavailable counters
and actual sample gaps; observation itself may perturb a slow laptop. Save the
executed observer source/hash and raw samples. Do not start a second AI stack or
concurrent generation. Keep original timeout instrumentation.

If application/DNS stalls or restarts persist, retain the failure and stop at the
first failed generation. Inspect runner-idle evidence. Resource/scheduling changes
or relaxed application probes require an updated design and renewed review;
successful local gateway liveness alone does not close N1–N3.

## Acceptance and verification

Run all [fast gates](../../AGENTS.md#verification-commands), package build, render
validation and affected gateway tests before deployment. The negative nginx test
must actually make upstream/DNS unavailable and verify truthful failure through
the existing API path, alongside local liveness success and no model calls. Check
that default rendering and all unrelated probe/replica/resource settings are unchanged.

Rebuild the real image; verify installed module hashes and effective budgets. Run
all 63 ordinary real-service cases with both opt-in flags. Run isolated recovery
serially if any application ownership/queue/recovery path changes; otherwise retain
the existing ten-case result without claiming new recovery execution. Exercise the
original Kubernetes rollout, backend/replica replay and saved-record/artifact
stop/start check on preserved data or a separately named fresh test cluster.

With AC connected and the laptop kept awake, explicitly warm the same pinned
model, run the unchanged complete walkthrough and original ten/seven gates using
`--timing-profile laptop-five-minute`. Start each gate only after observed runner
idleness. Original case counts/assertions, 300-second complete-reply cap and
3300/2400-second suite budgets remain binding. Keep every failure and unrun case;
do not resume halfway through the interrupted prior suite and call it a full pass.
The earlier plan's live under-load deadline-expiry requirement remains open and
is outside this health change's acceptance. It needs a separately reviewed
diagnostic protocol specifying the real-runtime expiry precondition, workload,
call/turn/client hard-stop budgets and expected saved/history/replay outcomes
before execution. No such diagnostic is approved by this follow-up plan. A
successful ordinary request, client disconnect or deterministic fake does not
satisfy that earlier requirement. Preserve its status as an acceptance gap.

Retain events/restart counts before/during/after, raw response/history/deadline
evidence, measured resource gaps and source/runtime identifiers. Seek targeted
review of health separation, timeout arithmetic and remaining state/recovery claims;
record reviewer findings and limitations. Human review of new generated outputs
and complete course acceptance remains required.

## Risks and rollback

A local gateway endpoint can remain healthy while APIs are unavailable; this is
why readiness remains upstream-dependent. Other pods may still stall or restart
under inference. Observers may perturb performance or lack access. Sleep, battery
mode and absent counters invalidate corresponding performance attributions.

Rollback restores the prior rendered laptop gateway/probe configuration after
in-flight turns finish or expire. Preserve model weights, records, PVCs and
artifacts. Neither rollout nor rollback may extend a saved original deadline or
repair/retry failed generation.

## Human review and approval

Jacob approved on October 19, 2026: "i approve, go for it", responding to the
prepared gateway-health plan. Approval covers the opt-in gateway-local liveness
endpoint/probe change, unchanged truthful readiness, synchronized resource/health
evidence, required checks and the original laptop deployment/model/demo reruns.
The five-minute budgets, model/prompts, application probe thresholds, replicas,
resources, serial execution and original ownership/deadlines remain binding.
The separate live-expiry experiment remains outside this plan's approved scope.

## Implementation outcome

Implementation and verification were authorized; implementation is pushed as
`bf07213`. The live acceptance run fails; see the
[complete result and raw evidence](../evidence/2026-10-19-laptop-gateway-health/README.md).
The original five-minute implementation remains committed; its laptop acceptance
is incomplete. See the [durable finding](../memory/laptop-inference-probe-restarts.md).

Same-vendor `timing_review` read-only review confirmed the reporting corrections
and narrow health scope. Its remaining finding identified an unspecified live-expiry
experiment. That experiment is now explicitly excluded from this approval scope
and remains an outstanding requirement of the earlier five-minute plan; an ordinary
successful workflow cannot close it. Different-vendor review remains unavailable.

The opt-in renderer now adds exact local `/gateway-live` and changes only the
laptop Kubernetes gateway's liveness path. Canonical/default deployments,
readiness/startup, application probes, thresholds, resources, replicas, retry
policy and all timing/model limits remain unchanged. New manifest assertions
compare those settings against canonical definitions; a new case checks exact
local rendering and preservation of canonical source bytes. No test was weakened.

Pre-live verification passes: locked sync, lint, formatting, all 647 fast cases
(73 integration deselected, 81% rounded coverage, 151.00 seconds), dependency
compatibility and package build. All 18 focused checks pass. Real nginx returns
local 200 during proven upstream NXDOMAIN and refused TCP while upstream health,
readiness and non-exact `/gateway-live/` return correlated 503; no model is invoked.
All 63 ordinary integration cases pass against the rebuilt Kubernetes deployment
with both required flags (87.58 seconds, no selected skips). Both model API pods
and the tuning/monitoring APIs import installed modules whose hashes match the
checkout; AI settings remain 240/270 seconds. Rollout preserves prior saved records,
artifact hashes/sizes and submission identity. Backend/replica smoke also passes.

The separate OpenAI `timing_review` agent finds no concrete defect in the submitted
renderer, assertions and real-nginx check. Its read-only review verifies meaningful
NXDOMAIN/TCP-refusal preconditions and preserved health/routing/replica constraints;
it executes no service. Different-vendor review is unavailable. Live continuity and
resource attribution remain execution requirements, not established by this review.

Retained setup/verification incidents: the first focused attempt lacks its output
parent; the first nginx attempt fails at Docker port discovery on an internal
bridge. Their corrected executions preserve every success assertion. The first
full format check finds unformatted displayed draft examples from prior evidence;
Ruff formats only the presentation, verified AST-equivalent to the five raw saved
strings. Original model reports/archive and human decision remain unchanged. The
post-rollout collector initially tries a completed historical pod; separate active
installation verification checks all four running, non-deleting API pods instead.
The actual rollout and preserved-data comparison had already succeeded. These
incidents and raw command exits will be retained with final live evidence.

uv's workspace-cache warning remains recorded. Archive inspection finds zero
`.uv-cache` entries and confirms the updated renderer in the wheel. No ownership,
queue, worker or recovery logic changes, so the prior complete isolated recovery
result is retained without claiming a new recovery execution. The controlled node
restart and full instrumented walkthrough/model reruns are recorded separately.
The controlled named-node stop/start now passes in 112.531 seconds, preserving
identical saved records, artifact hashes/sizes and submission replay identity.

The unchanged full walkthrough on clean `bf07213` fails at its first AI inspection:
client `RemoteProtocolError` after 144.094 seconds. Local `/gateway-live` itself
times out; Kubernetes orders gateway restart at 21:41:45 UTC. Later pod status
confirms restart count four versus initial three, old container completion at
21:42:28 and replacement start at 21:42:33. Preserve lagging initial/final snapshots
instead of inferring no restart. The serving API also logs shutdown during broad
probe failures, then persists the turn after 167.506 seconds, below 270. Its saved
tool-transport-error reply has no verified facts, pending action or submission.
This does not establish model semantic failure, deadline exhaustion or timely
cancellation. The original runtime slice's idle=false remains unchanged; a later
timestamped read independently observes idle=true. No generation is retried.

F1/F2 checks pass, but N1/N3 fail. N2 yields useful measurements with gaps: host
available memory reaches 557.81 MiB and node CPU PSI some avg10 reaches 98.74 in
the last successful read, while gateway cgroup throttling remains zero in three
successful samples. Host/node gaps reach 34.588/79.125 seconds, direct vmmem CPU
access fails and the selected PIDs miss the actual inference worker. Page input
also peaks before inference. No particular resource cause or OOM is proved.

Per this plan's first-failure condition, fresh ten/seven gates are unrun; prior
complete standalone passes remain separately retained. All five implementation CI
jobs pass. AC is connected and the temporary keep-awake request is released without
changing power policy. No resource, model, thread or API probe setting is changed.
The separate live-expiry experiment and full laptop/course acceptance remain open.
The [resource diagnosis plan](2026-10-19-laptop-resource-diagnosis-plan.md) is a
reviewable next step, awaiting approval before another measured inference run.
