# Laptop inference can outlast Kubernetes health availability

October 19, 2026: the approved five-minute profile on clean `533a2ed` permits a
correct actual-ID inspection in 210.532 seconds, but the full Kubernetes walkthrough
fails on its second turn. [Evidence](../evidence/2026-10-19-laptop-five-minute/README.md)
retains the original attempt, histories, boundary logs, Kubernetes events and runtime.

Kubernetes explicitly kills the gateway for failed liveness at 16:29:56 UTC.
Its container terminates at 16:30:47; the client stream drops at 16:30:47.681,
before the 240/270/300/310-second windows expire. The serving model API stays up
and saves an honest comparison transport-error reply at 16:30:50.246, with no
pending action. Gateway liveness proxies `/api/v1/health/live` through model API
and DNS; health-path DNS timeouts and broad probe delays are retained. Another,
non-serving model API pod also restarts. Exit 137 / reason Error does not prove OOM.

Do not increase timeouts again to address this disconnect. The broader resource
cause is unmeasured. Isolating gateway process liveness is a proposed narrow change,
not proof that CPU/VM/paging or application health delays are resolved. The
[deployment-health plan](../plans/2026-10-19-laptop-deployment-health-plan.md)
was subsequently approved and implemented; keep readiness truthful and retain the
five-minute acceptance cap. Its later failed acceptance is recorded below.

A separate direct dialogue gate passes eight cases, then Windows sleeps for about
80 minutes during the ninth and resumes on battery. That gate fails/incompletely
records the ninth; the tenth and snippets remain unrun. Its huge sleep-inclusive
timings cannot diagnose active inference speed or validate timely cancellation.
Actual runtime logs end idle. Rerun remaining gates only with AC/awake prerequisites.

After Jacob reconnects AC and requests continuation, a
[fresh complete standalone run](../evidence/2026-10-19-laptop-awake-gates/README.md)
passes all ten conversation and seven snippet scenarios. Maximum complete replies
are 184.875 and 229.219 seconds; both runners end idle. Windows records a sleep
between the gates, intersecting neither execution window. Application/harness/model
bytes and settings are unchanged. This supersedes the earlier incomplete model-gate
status only; the deployed gateway failure and live-expiry gap remain. Jacob accepts
the saved conversation examples and five drafts on October 19 in the
[human decision](../evidence/2026-10-19-laptop-awake-gates/human-review-decision.json).
Generated Python is never executed; Jacob later approves the deployment-health
design: "i approve, go for it".

The approved local `/gateway-live` change is pushed as `bf07213`; real nginx proves
upstream-independent liveness and 647 fast/63 ordinary cases plus all five CI jobs
pass. Yet the [new full walkthrough](../evidence/2026-10-19-laptop-gateway-health/README.md)
fails on its first AI request after 144.094 seconds. Even local liveness times out;
Kubernetes orders gateway restart at 21:41:45 UTC. Later state confirms count four
versus initial three; initial/final status snapshots lag those events. The serving
API logs shutdown and saves the transport-error turn in 167.506 seconds, within
270. Preserve the original idle=false slice and separately observed later idle=true.

Host available RAM reaches 557.81 MiB; the last successful node sample reports
CPU PSI some avg10=98.74 with MemAvailable 6,655,816 KiB. Page input peaks before
inference too. Gateway throttling is zero in successful samples. Gaps reach
34.588 seconds host / 79.125 seconds node; fixed PIDs miss llama-server and vmmem
CPU access is denied. No OOM, gateway quota exhaustion, swap-thrashing cause or
direct worker CPU attribution is established. Do not recommend more reply time
or claim resource allocation/model optimization is proved to fix delivery.

Stop after the first failed generation as approved; new ten/seven reruns remain
unrun, distinct from the preceding passes. The temporary wake request is released,
resource/thread/probe settings stay fixed and preserved cluster data remains.
Revisit through the [pending resource diagnosis plan](../plans/2026-10-19-laptop-resource-diagnosis-plan.md)
with actual worker identification and independent timestamped counters. This finding
does not close live timeout-expiry or original-record reproduction gaps.

Later user direction changes the experiment: Jacob requests ignoring health checks
and "a run or two with no limit" to measure completion time. The
[new diagnostic plan](../plans/2026-10-19-laptop-unbounded-diagnostic-plan.md)
records that approved intent and pending design review. Removing just HTTP waits
would leave model/host timers and the durable turn-expiry fence active. A true
unbounded diagnostic must explicitly distinguish new diagnostic ownership from
old saved finite deadlines; it cannot establish a normal five-minute gate pass.
The resource-only plan is deferred and unapproved. No new run or runtime change
has occurred while preparing this design.
