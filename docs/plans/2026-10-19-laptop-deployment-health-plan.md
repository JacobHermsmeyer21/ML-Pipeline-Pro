# Preserve gateway liveness during laptop inference

- Status: awaiting human review; no implementation authorized by this plan
- Date: 2026-10-19
- Source baseline: `533a2ed` on `person-a/conversation-foundation`
- Request: follow-up to Jacob's approved five-minute implementation and demo rerun
- Human reviewer/approval: pending; five-minute approval does not cover probe redesign
- Independent review: same-vendor read-only evidence review by `timing_review`;
  targeted implementation review required; different-vendor availability unknown

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

Pending. Jacob approved the five-minute timing/deployment plan on October 19;
this newly diagnosed gateway health design has not been approved. No production
or local probe, resource or concurrency change has been made under this plan.

## Implementation outcome

Not implemented. The current change records evidence and a reviewable follow-up.
The original five-minute implementation remains committed; its laptop acceptance
is incomplete. See the [durable finding](../memory/laptop-inference-probe-restarts.md).

Same-vendor `timing_review` read-only review confirmed the reporting corrections
and narrow health scope. Its remaining finding identified an unspecified live-expiry
experiment. That experiment is now explicitly excluded from this approval scope
and remains an outstanding requirement of the earlier five-minute plan; an ordinary
successful workflow cannot close it. Different-vendor review remains unavailable.
