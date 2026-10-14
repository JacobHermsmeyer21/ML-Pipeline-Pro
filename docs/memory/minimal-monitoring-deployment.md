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
dialogue and one/seven snippet cases; it was excluded. The current 7B tuning draft
still exceeds the unchanged 20-second limit. Retain failed and earlier accepted
runs with their source/profile identities; structural grammar is not semantic quality.
