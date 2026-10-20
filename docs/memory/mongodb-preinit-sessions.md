# A direct connection opened before replica initialization can reject later sessions

October 19, 2026; baseline `72eb069`. The
[fresh Kubernetes reproduction and controlled comparison](../evidence/2026-10-19-kubernetes-mongodb-sessions/README.md)
confirm the dataset 503 is PyMongo's `ConfigurationError: Sessions are not
supported by this MongoDB deployment`.

With `directConnection=true`, an application connection can handshake with the
uninitialized `RSGhost` member. PyMongo 4.18.2 records that connection's
`supports_sessions=false` because the member is not yet readable. The same pool
can keep answering ordinary ping after primary election, yet reject the first
explicit session/transaction. Successful dependency ping does not prove that
connection can execute lifecycle-fenced writes. Warm/fresh-database probes made
after replica initialization miss this startup precondition.

In a same-server comparison, a client created before initialization with
`replicaSet=mlpp` rejects early ping and succeeds on its first dataset transaction
after primary selection. Kubernetes advertises reachable `mongo:27017`, so proper
replica discovery is available there. Host clients may require direct mode because
they cannot resolve that internal name; do not replace host URI examples blindly.

The [configuration repair plan](../plans/2026-10-19-kubernetes-mongodb-sessions-plan.md)
awaits approval. Preserve snapshot/majority transactions, fencing and the original
smoke assertions; sleeping or retrying dataset registration would not establish
correct startup selection. Revisit the finding after a driver/connection-mode
change using a real client opened before replica initialization, not only a ping
against an already initialized service.
