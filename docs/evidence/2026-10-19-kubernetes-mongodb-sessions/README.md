# Kubernetes startup sessions diagnosis

October 19, 2026, America/New_York. Baseline `72eb06971e62d084807eacad44df1ebea354d459`;
the retained CI failures and runner fix are linked in the
[preceding evidence](../2026-10-19-ci-mongodb-kernel/README.md).

A new, isolated kind cluster `mlpp-storage-767d6801` reproduces the first dataset
POST returning 503 after rollout/readiness. The diagnostic image copies the tracked
baseline source and changes only its existing redacted storage warning to include
the exception type/message; no application behavior or smoke assertion changes.
The [raw diagnostic excerpt](kubernetes-error.txt) records
`ConfigurationError: Sessions are not supported by this MongoDB deployment`.
Both API replicas' logs were captured; the existing CI collector selects only one
replica and can miss the failing request. The full raw local logs, manifest, image
provenance and copied instrumentation are under ignored
`artifacts/kubernetes-storage-767d6801/`,
`artifacts/kubernetes-storage-active.json`, and
`.tools/kubernetes-storage-build-767d6801/`.

The [controlled startup JSON](startup-control.json) compares two clients created
against the same uninitialized `mongod --replSet mlpp`. The direct client can ping
before initialization. A replica-discovery client using `replicaSet=mlpp` rejects
that ping with server selection unavailable. After the direct control client
initializes the set and observes writable primary, its ordinary ping still
succeeds but its first lifecycle-fenced dataset transaction raises the same
`ConfigurationError`. The original discovery client then pings and admits its
first dataset transaction successfully. The probe's uniquely named MongoDB
container and Docker network are removed afterward; it publishes no host ports.

Installed PyMongo source confirms that connection handshake sets
`supports_sessions` only when the member is readable, and explicit session use
checks that connection property:
`.venv/Lib/site-packages/pymongo/asynchronous/pool.py` (handshake) and
`asynchronous/client_session.py` (`_apply_to`). This explains why a successful
later ping alone does not repair the connection opened as `RSGhost`. Fresh clients
created after initialization, as in the earlier warm probes, miss the mechanism.

Execution tools: Python 3.11.5 host, PyMongo 4.18.2, uv 0.12.23,
Docker Engine 29.8.2, Compose 5.5.1,
kind 0.33.0 and Docker's WSL kernel `6.18.54.1-microsoft-standard-WSL2`.
The startup-control script and full output are retained locally as
`artifacts/mongodb-startup-control.py` / `.json`. The JSON contains MongoDB's
unauthenticated all-zero cluster-time signatures, not an account credential.

The [repair plan](../../plans/2026-10-19-kubernetes-mongodb-sessions-plan.md) awaits
review; candidate behavior is demonstrated only by the controlled diagnostic so
far. No repaired deployment or CI result is claimed.
