# A read-only parent check cannot fence tuning child writes

Recorded October 6, 2026 from the existing ownership fix and its validation.

Under MongoDB snapshot isolation, reading a tuning parent's token before writing
a child does not force a conflict with a concurrent ownership takeover. The child
mutation must write the matching parent in the same transaction. The implementation
increments `ownership_revision`, checks token/status and the active lease, then
mutates the child. Transaction callbacks contain database operations because the
driver may retry them.

Evidence: [ownership implementation](../../src/ml_pipeline_pro/ownership.py),
[real-MongoDB takeover regressions](../../tests/integration/test_tuning_ownership.py),
and [recorded validation](../project/project-status.md#ownership-fix-validation), introduced
in commit `a2a089c`. The documented validation predates this memory entry.

Do not replace this with a separate execution-layer check or a read-only transaction.
Revisit if ownership storage or transaction semantics change; demonstrate stale
write rejection at the takeover boundary. The serial takeover checks do not prove
arbitrary partition or concurrent-load behavior.
