# Permanent erasure needs metadata fencing and live-writer exclusion

Recorded October 19, 2026 from the approved
[permanent-deletion plan](../plans/2026-10-19-permanent-deletion-plan.md).

A read-only reference check cannot serialize new submissions, versions or
observations against cascade capture under MongoDB snapshot isolation. Admission
writes the project lifecycle gate in the same transaction as reference validation
and insertion. Dataset registration also binds its original lifecycle generation
while holding a native project publication lock, so uncertain inserts resolve
before uploaded-file ownership is assessed.

Terminal database status or an expired lease does not prove that an old process
has stopped writing artifacts. Each worker attempt holds its own native lock
before claim until all owned threaded work ends, including repeated cancellation.
Deletion acquires those locks before cleanup. Separate attempt locks preserve
recovery takeover; never steal them based on database lease age. Stable lock files
and `fallback_to_soft=false` avoid splitting ownership or expiring live locks.

Durable intent precedes file removal. Failure retains the cleanup manifest and
admission gate; same-key retries resume even after root metadata disappears.
Successful cleanup scrubs the manifest and retains minimal receipts. Old erased
submission keys return 410 rather than allocating new work. Preserve any uploaded
canonical/source/manifest file still referenced by a surviving dataset, including
a derived version; operator inputs outside managed uploads remain external files.

Evidence: [lifecycle](../../src/ml_pipeline_pro/lifecycle.py),
[native controls](../../src/ml_pipeline_pro/storage_control.py),
[cleanup](../../src/ml_pipeline_pro/deletions.py),
[real transaction/process tests](../../tests/integration/test_deletions.py), and
[retained verification](../evidence/2026-10-19-permanent-deletion/README.md).
The retained Windows and cross-container native-lock checks, 125-run cascade and
four process-death boundaries establish these tested cases, not arbitrary network
filesystem support, concurrent training capacity or independent review.

Browser acceptance also confirmed that pending operations keyed by project were
hidden after reload reset the workspace to `demo`. The tab now restores only its
nonsecret selected project before loading that project's saved pending requests;
API keys remain memory-only. Lost-response/reload and late-project-preview checks
exercise this boundary. Revisit before changing storage roots, publication,
worker cancellation/ownership, sharing references or browser persistence.
