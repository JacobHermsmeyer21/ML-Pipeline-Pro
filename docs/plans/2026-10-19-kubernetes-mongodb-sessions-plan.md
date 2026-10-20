# Select the initialized MongoDB replica set before Kubernetes application work

- Status: awaiting review; implementation pending
- Date: 2026-10-19 (America/New_York)
- Source baseline: `72eb069` / `main`
- Request: resolve the Kubernetes dataset-registration 503 left after the CI kernel fix
- Human reviewer/approval: Jacob; pending for the specific configuration below
- Independent review: no application concurrency, ownership or transaction implementation
  changes; diagnostic and diff review required, no independent review claimed

## Proposed behavior and purpose

Kubernetes application clients must select the initialized `mlpp` replica-set
primary before ping/readiness can admit work. Change the shared Kubernetes
ConfigMap URI from `mongodb://mongo:27017/?directConnection=true` to
`mongodb://mongo:27017/?replicaSet=mlpp`. Add a real, isolated startup regression
to the Kubernetes CI job before its existing full deployment smoke gate.

## Clarification and critique

The [local Kubernetes reproduction and controlled startup](../evidence/2026-10-19-kubernetes-mongodb-sessions/README.md)
confirm `ConfigurationError: Sessions are not supported by this MongoDB deployment`.
The old direct connection can open an application connection while MongoDB is
still `RSGhost`. PyMongo records `supports_sessions=false` from that connection's
handshake because the member is not readable yet. Later ping succeeds through the
same pool after initialization, but an explicit session/transaction still fails.
The earlier warm-Mongo probes missed this required pre-initialization handshake.

In the controlled comparison, one client using the old URI pings before
initialization and fails its later dataset transaction; another created before
initialization with `replicaSet=mlpp` refuses the early ping and succeeds at its
first transaction once the same server becomes primary. Installed PyMongo source
confirms the handshake capability and explicit-session check.

Replica-set discovery is valid inside Kubernetes: the existing headless Service
and saved member both use reachable `mongo:27017`, and initialization already names
the set `mlpp`. The [driver documentation](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/connect/connection-targets/)
describes selecting a replica set with its name. Retaining direct mode plus only
a set-name check can still admit a named but unreadable member; normal primary
selection matches the application's transaction requirement.

Do not add a sleep, retry the dataset mutation, restart clients after an error,
weaken transaction fencing, or relax the smoke assertion. A session-aware public
readiness redesign would be broader than this diagnosed deployment configuration
correction. Host development and Compose retain their current direct connections:
host clients cannot necessarily resolve the advertised internal `mongo` hostname,
and Compose already waits for writable MongoDB before starting its applications.
No unresolved product intent remains beyond review of this configuration default.

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | An application client created before replica initialization must not report MongoDB ping ready before primary selection. | Real startup regression asserts the pre-initialization MongoDB ping fails with server selection unavailable. |
| F2 | Functional | The same client must admit its first dataset transaction after primary selection. | Regression uses the production connection/store/lifecycle path; exactly one record is inserted and read back without retrying the mutation. |
| F3 | Functional | Kubernetes completes the existing full workflow and replica replay gates. | Fresh deployment smoke and two-model-API replay pass; all five hosted CI jobs succeed. |
| N1 | Reliability | Regression resources are isolated, bounded and cleaned on failure as well as success. | UUID-named Docker network/containers, command deadlines, captured JSON/log evidence and cleanup review. |
| N2 | Compatibility | Preserve schemas, project scoping, ownership fences, snapshot/majority transactions, worker serialization, artifacts, timeouts and locked dependencies. | Diff review and unchanged fast/ordinary/recovery gates. |

## Design and constraints

Update only `MLPP_MONGODB_URI` in [the Kubernetes manifest](../../deploy/kubernetes/stack.json)
for production deployment behavior. Existing local-AI/laptop renderers inherit the
base ConfigMap. Keep the singleton replica set, headless Service, initialization,
startup/readiness probes, PVCs and all application implementation unchanged.

Add `scripts/check_mongodb_startup.py`, invoked after the Kubernetes CI image build.
It reads the URI from the checked-in ConfigMap, creates a uniquely named disposable
Docker network and fresh `mongo:8.0` container, and runs a bounded probe in the built
application image on that network. No published host ports or existing volumes are
used. Before initialization, its application client must reject ping. A separate
direct control client initializes the set and waits for writable primary. The
original application client then pings and performs the first real dataset
admission using `open_connections`, `TrackingStore` and its existing lifecycle
transaction. Save precondition, phase results and cleanup status as JSON under
`artifacts/kubernetes-validation/`; retain the existing artifact upload. Failed
assertions fail CI. No application mutation is retried to turn a failure into a pass.
Bound command execution and poll only declared startup conditions. Remove only
resources created by this probe, including on assertion/subprocess failure.

Document the URI and startup regression in the Kubernetes/verification guides.
For an existing test deployment, ConfigMap environment changes require controlled
application pod replacement after active jobs finish; this task does not restart
or alter saved user deployments. No metadata/data migration is required.

## Acceptance and verification

Before implementation: validate plan/evidence links and JSON, retain the exact
reproduction, run `git diff --check`, and commit/push for human review.

After approval: verify the regression fails with the original direct URI at the
pre-initialization readiness assertion and passes with the reviewed URI; check
resource cleanup for both outcomes. Run locked sync, Ruff lint/format, all fast
tests with coverage, and `uv pip check`. Validate the manifest and inherited laptop
configuration. Run the new startup gate and the unchanged full kind deployment
on a fresh isolated cluster with the current uninstrumented application image.
Verify first dataset creation, training, tuning, monitoring and replay through both
model API replicas. Run affected ordinary integration with both flags and the
separate serial recovery suite through hosted CI. Inspect JUnit for failures/skips
and retain exact run/revision references. No claim of real-model AI acceptance.

Fetch/compare upstream and `origin/main` before major changes and before each push;
integrate applicable incoming commits without rewriting published history.

## Risks and rollback

A different replica-set name or unreachable advertised member now fails selection
instead of accepting an unsuitable direct connection. The supported manifest names
and reaches `mlpp`/`mongo:27017`; verify those together. The probe adds a fresh MongoDB
pull/start to the deployment job. Revert the URI and regression/CI step together to
roll back, preserving PVCs/data; rollback can restore the startup failure.

## Human review and approval

Pending. The earlier approved runner pin did not approve this deployment URI
change. The current request authorizes diagnosis; this document records its concrete
proposed configuration and acceptance criteria for review under `AGENTS.md`.

## Implementation outcome

Pending approval. No checked-in application or deployment behavior has changed.
