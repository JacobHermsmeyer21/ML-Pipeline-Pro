# Monitoring replay and local deployment boundaries

October 13 minimal course delivery; [design](../plans/2026-10-13-monitoring-deployment-plan.md).
Independent monitoring stores immutable samples, bounded windows and separate
model interpretations. Real MongoDB tests exercise insert races, complete replay,
changed-body conflicts, project references and a 101-record indexed query.

Normalize record metadata/observation time to UTC milliseconds before first
response: BSON truncation otherwise changes replay. Check existing samples before
fresh-time admission, preserving old accepted replay. Capture summary query bounds
at the same precision. Missing labels remain unknown; partial windows are explicit.

Diagnosis must identify its own instructions/format, not chat provenance. Recursively
redact public provenance/advice, including nested configured secrets. No tools,
automatic changes, artifact writes or model selection in diagnosis/monitoring.

MongoDB's singleton Kubernetes Service must be headless and publish startup
addresses; an ordinary ClusterIP cannot map the replica set's own node. Keep shared
MongoDB transactions and one serial worker/scheduler (`Recreate`). Force submission
replay through both individual model API pods to prove replica behavior.

On kind node resume, early CoreDNS unavailability caused MongoDB's saved
`mongo:27017` member to fail self-identification. Ping remained successful while
`db.hello().isWritablePrimary` was false and dataset writes returned 503. Publish
startup addresses and use the same initialization/writable check in a bounded
startup probe, allowing process restart without forced reconfiguration or PVC
deletion. See the [startup fix](../plans/2026-10-13-kubernetes-mongo-startup-plan.md).

Warm the installed local model explicitly with the same 8192-token context. Empty
warmup without matching context can precede another runner reload; application
20-second deadlines remain unchanged. Cold/busy local-model failures remain saved.
Do not infer universal capacity from a classroom workload or grammar acceptance.

The smaller 3B candidate had compatible token admission but passed only five/ten
dialogue and one/seven snippet cases; it was excluded. Earlier 7B attempts exceeded
20 seconds on the tuning draft; final original ten/seven gates pass after observed
throughput improved. A separate 30-second diagnostic needed no call over 20 seconds;
no deadline was changed. Cause of timing variation is unestablished. Keep all runs
with source/profile identities; grammar is not semantic quality or capacity proof.

The CI node could not schedule its eleventh pod with 1100m application CPU requests.
Use 50m for ten lightweight pods plus 100m for the serial worker (600m total), leaving
control-plane reservations separate. Limits, worker count and replay gates stay intact;
this fixes admission rather than proving peak concurrent demand. See the [CPU plan](../plans/2026-10-13-kubernetes-cpu-budget-plan.md).


October 19 dashboard verification found that a configured `refresh=15s` alone did
not establish live updates in pinned Grafana 12.1.1. An initially empty solo panel
stayed empty after Prometheus had the new measurements. The visible-page trace
contained one query window. Explicit `timepicker.refresh_intervals` including
`15s` restored a second advancing window after 15 seconds, consistent with the
[refresh-picker construction](https://github.com/grafana/grafana/blob/v12.1.1/public/app/features/dashboard-scene/serialization/transformSaveModelToScene.ts#L357).
The UI summary also required its own bounded, non-overlapping refresh; otherwise
it still reported no observations after charts populated. Selection/project and
request fences reject stale reads, and summary polling preserves existing frames.
The [fresh-version browser boundary](../evidence/2026-10-19-dashboard/README.md)
starts with no data, then records real samples and observes automatic graph and
summary updates without user refresh. Recheck actual query timing and that
transition after Grafana/configuration changes; HTTP 200 and an iframe load event
alone do not establish chart rendering or refreshing.
