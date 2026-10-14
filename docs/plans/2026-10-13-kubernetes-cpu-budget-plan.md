# Fit classroom CPU reservations to the CI node

- Status: implemented; local and remote deployment verified
- Date: 2026-10-13
- Baseline: `40d8dc6`
- Human approval: Jacob's approved minimal deployable midterm implementation
- Independent review: separate boundary reviewer; different-vendor unavailable

## Confirmed mechanism and requirement

Remote deployment diagnostics show ten pods running while Grafana is Pending,
with `FailedScheduling: Insufficient cpu`. The first run timed out with only one
model API available but lacked diagnostics; do not assert its exact cause.
Eleven application pods currently reserve 100m each, or 1100m, before the node's
control-plane reservations. Extending readiness time cannot resolve admission.

Reserve 50m for each of the ten lightweight services/pods and 100m for the serial
worker: total 600m. Keep all existing CPU/memory limits, memory reservations,
probes, service counts and workflow assertions. A request is a scheduling/share
reservation, not measured usage or a concurrency guarantee. External Ollama compute
is unchanged. Retain direct two-pod replay and three actual tuning trials.

## Scope and alternatives

This corrects resources inside the approved local Kubernetes deployment scope.
Removing a required service/replica, weakening rollout gates or using a larger
paid runner would avoid proving the intended small classroom deployment. Resource
limits and serial workload constraints remain enforced. Higher simultaneous load
or a node with less than the required free reservations needs separate evidence.
No public API, persistence, default inference deadline or ownership contract changes.

## Implementation and verification

Update only CPU requests in the manifest, with worker 100m explicitly preserved.
Retain node allocatable CPU/memory in deployment results and failure diagnostics.
Independently check the 600m arithmetic and limits/replicas diff. Apply the manifest
to the named local cluster and verify readiness plus backend/direct-pod replay.
Then rerun the full remote checks/deployment/recovery job with the same gates.
Retain both failed remote runs, their diagnostic artifacts and final node capacity.
Validate source/config syntax, docs and whitespace before the requested commit/push.

## Human approval scope and outcome

Within Jacob's previously approved minimal deployment/resources direction; no
separate human review of this document is claimed. Broader configuration, ownership
or acceptance changes require renewed review. Outcome pending.

Local correction passes all deployment readiness, actual training/three-trial
tuning/version/monitoring smoke and forced same-ID replay through both new model API
pods. Separate same-vendor boundary review confirms ten times 50m plus one times
100m equals 600m; exactly nine request fields changed, with limits/memory/replicas/
probes intact. The total excludes system reservations and rollout surge.
Different-vendor review unavailable. Final [successful implementation CI](https://github.com/JacobHermsmeyer21/ML-Pipeline-Pro/actions/runs/38505646188) passes all five jobs. Its node has two allocatable CPUs; actual three-trial smoke and direct two-pod replay pass. This closes the measured scheduling failure without changing gates.
