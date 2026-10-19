# Attribute laptop scheduling stalls before changing resources

- Status: awaiting human review; no new inference or resource change authorized
- Date: 2026-10-19
- Source baseline: `bf07213` on `person-a/conversation-foundation`
- Request: next step after the approved health implementation's failed live demo
- Human reviewer/approval: pending; prior health approval does not approve this run
- Independent review: seek separate review of sampling/budget arithmetic; different-vendor availability unknown

## Proposed behavior and purpose

Run one bounded diagnostic of the unchanged deployed demo with complete inference
worker identification and independent host/node sampling. Determine whether CPU
scheduling, host memory/file paging or the Kubernetes transport dominates the
health stall before selecting a resource change. This plan approves investigation
only. It supplies evidence for a later single-variable fix, not assumed success.

## Clarification and critique

The [new evidence](../evidence/2026-10-19-laptop-gateway-health/README.md) confirms
local nginx liveness failure and a restart during an AI turn completed server-side
in 167.506 seconds. More reply time does not prevent this mechanism. Four inference
threads are active; host available memory reaches 557.81 MiB, while successful node
samples show CPU pressure and ample MemAvailable. The missed worker PID, inaccessible
VM counters and 79-second observation gaps prevent causal attribution. Gateway
cgroup throttling remains zero in successful samples. Do not choose larger WSL
memory limits, lower model thread counts or relaxed probes from those facts alone.
Earlier two/three-thread prompt screens were slower and did not establish deployed
health benefits; see [prior findings](../memory/qwen-prompt-processing-cost.md).

The simplest alternative is another unchanged retry, but it would preserve the
measurement blind spot. A smaller model would add semantic acceptance work. Change
the measurement boundary first. Scope questions are resolved conservatively:
retain topology/model/budgets; stop after one failed generation; no OS/WSL changes,
application restarts to improve a score, background-app termination or A/B trial.
Human review decides whether this bounded diagnostic is worth another laptop run.

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Measurement | Identify actual inference worker and VM/host boundary before inference. | PID, creation time, parent identity and executable basename; exact runner/runtime/model/threads; explicit access checks, no full command-line/environment dump. |
| F2 | Functional | Preserve original workflow and public contracts. | Original walkthrough, same actual-ID scenario assertions, zero automatic retries, unchanged budgets/settings/source hashes, saved history/deadline and artifact/replay identities. |
| N1 | Observation | Bound observer overhead and expose gaps. | Two-minute idle baseline; independent 10-second host and 30-second node samples; actual monotonic/UTC windows, validity codes and collector CPU/duration. |
| N2 | Reliability | Distinguish request delivery from inference and probe health. | Client/server/runtime times plus local/upstream probe events and later container status; no omission of stale snapshots or failed requests. |

## Constraints and scope

Preserve serial execution, two model API replicas and domain separation. Retain
240/270/300/310-second windows, original call/token/context limits, installed 7B
digest, prompts, four inference threads and readiness/liveness thresholds. No API
schema, ownership, concurrency, submission, training-selection or persistence
change. Generated code is saved/validated only. Existing saved artifacts/PVCs and
stopped Compose volumes remain intact. Actual expiry under load is outside this
plan; it still needs a separate reviewed protocol.

## Design

Add `scripts/diagnose_laptop_resources.py`, extend the local
`evaluations/laptop_resource_observer.ps1` and update the laptop guide. Discover the real worker
after one explicit installed-model empty warmup; validate its creation time and
CPU/working-set access before the measured run. Track known PIDs cheaply, detect
exit/replacement and rediscover only then. Record unavailable vmmem access; use
node counters for the Linux boundary without equating their CPU with Windows.
Do not stop other user applications. Record aggregate competing CPU/memory use
with process names and totals only, omitting unrelated paths and command lines.

Separate lightweight host CPU/memory/disk sampling from node and DNS operations.
Prepare one node-local read-only collector before inference so repeated Docker/
kubectl exec startup does not serialize critical counter capture. Record CPU PSI,
memory/IO PSI, /proc CPU/memory/vmstat and mapped container CPU/memory counters.
Retrieve its timestamped payload after the run; timestamp retrieval separately.
Use one small collector, 30-second nominal cadence, no API mutation. Bound the
combined host/node capture to 2100 seconds and 10 MiB total across all files,
whichever arrives first; reaching either cap makes measurement incomplete rather
than deleting earlier samples. This covers 120 seconds of baseline, at most
1800 seconds of walkthrough and at most 120 seconds of post-run observation,
with 60 seconds of collection margin. Start that clock after warmup. If it cannot start,
retain setup failure and perform no inference. Do not change cgroups or node config.

Validate both collectors with 120 seconds of idle sampling. Require actual worker
CPU/working-set counters to be accessible, valid host counters, at least ten host
and four node samples, no host gap above 20 seconds or node gap above 60 seconds,
and no measured collector CPU above 0.1 average core over that idle window. These
are measurement preconditions, not new application acceptance thresholds. If unmet,
stop and report incomplete instrumentation; do not adapt sampling mid-run and
claim comparable evidence. VM direct access may remain explicitly unavailable.

Then run exactly one original `examples/midterm_walkthrough.py` against the named
cluster with `--timing-profile laptop-five-minute --confirm-demo-proposal` and a
fresh output directory. Preserve all earlier execution archives. One measured
walkthrough is the maximum; no fresh standalone ten/seven gates or A/B comparison
is included. Any later comparison must name one controlled variable and baseline
in a separately reviewed update before execution.

## Acceptance and verification

Implement and inspect the harness, validate Python/PowerShell syntax and cleanup,
and run applicable lint/format checks before deployment use. Test sample parsing,
PID replacement and gap reporting with deterministic recorded inputs; never use
those tests to claim live resource attribution. Run all required fast gates before
committing application/script changes. No ownership/queue/recovery change is planned;
ordinary and isolated recovery evidence stays historical unless those paths change.

AC/awake prerequisites, one installed runtime and observed runner idleness are
mandatory. A temporary thread-scoped system-required request may span the run,
cleared in finally without changing power policy. Retain warmup, baseline and
inference windows separately. Client ceiling 300 seconds per complete reply and
1800-second outer walkthrough safety bound remain unchanged. Stop on the first
failed generation; inspect idle read-only every five seconds for at most 120 seconds
after command completion, without initiating another model call. At that deadline,
retain busy/unknown state and stop only owned collectors/port-forwards; do not kill
the model. A
late subprocess return is recorded as overrun, never evidence of timely expiry.

Retain raw source hashes/commands/settings, counter validity, actual sample gaps,
events and status before/during/after, original saved deadline, histories and
client/server/runtime timings. Derive process CPU from same-PID creation-time
matched deltas, normalize against elapsed time explicitly and report missing
values rather than zeros. Seek separate review of arithmetic, process replacement,
node collector cleanup and conclusions; disclose unavailable independent vendor.

Investigation succeeds when it either captures enough synchronized worker/host/node
evidence to justify a specific next hypothesis or explicitly narrows the remaining
blind spot. It does not establish the resource root cause merely by correlation,
nor close laptop/course acceptance without a successful full reviewed workflow.

## Risks and rollback

Collectors can perturb this slow machine; retain baseline overhead and gaps. File
page-ins, guest MemAvailable and Windows available RAM describe different boundaries.
Keep failed or missing observations visible. Stop own collectors/port-forwards and
clear own temporary wake request in finally. Preserve runtime, cluster, PVCs, models
and saved deadlines; do not terminate an active generation to clean up observations.
No product or system resource setting changes, so rollback removes only this
diagnostic tooling after retained evidence is checked.

## Human review and approval

Pending. This follows the approved health plan's first-failure stop condition.
Approval would cover only this fixed-setting diagnostic and its measurement tools.
A resource allocation, thread/probe/model change or controlled comparison would
require an updated plan and renewed review.

The separate OpenAI `timing_review` agent reviews this plan read-only. Its findings
correct the capture budget to cover baseline/workload/post-run windows, define the
total payload cap and bound later idle polling. Same-vendor review only;
different-vendor review is unavailable. It performs no execution or service change.

## Implementation outcome

Not implemented or executed. Prior health implementation and failed acceptance are
retained in the linked evidence; preparing this plan does not authorize another run.
