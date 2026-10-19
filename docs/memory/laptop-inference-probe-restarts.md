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
awaits review; keep readiness truthful and retain the five-minute acceptance cap.

A separate direct dialogue gate passes eight cases, then Windows sleeps for about
80 minutes during the ninth and resumes on battery. That gate fails/incompletely
records the ninth; the tenth and snippets remain unrun. Its huge sleep-inclusive
timings cannot diagnose active inference speed or validate timely cancellation.
Actual runtime logs end idle. Rerun remaining gates only with AC/awake prerequisites.

Revisit after the reviewed deployment change and lightweight resource evidence,
then repeat the original complete walkthrough and full model gates. This finding
does not close the earlier live timeout-overrun or original-record reproduction gaps.
