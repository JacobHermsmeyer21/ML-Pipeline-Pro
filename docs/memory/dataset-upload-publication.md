# Uploaded CSV publication must survive uncertain metadata writes

October 19 local dashboard implementation publishes content-addressed CSVs before
inserting dataset metadata. A private staging file is linked atomically into
`uploads/<project>/<sha256>.csv`; an existing destination is checked against its
hash and size and never overwritten. Project checks also cover ordinary
registration and resolved symlink aliases, so that route cannot import another
project's uploaded file.

Only the request's temporary name is removed during cleanup. A committed insert
can lose its acknowledgement; deleting the published file in that case would
strand a saved dataset. The replay checks `(project, name, version)`, metadata and
file content and returns the saved identity. Published orphans are retained;
automatic cleanup requires a separate design.

Threaded file operations are shielded and awaited before cancellation removes
the staging file. Single/repeated cancellation checks verify this ownership rule.
Real simultaneous uploads prove 201/200 identical record replay on MongoDB, and
a serial worker trains through the actual shared volume mounted read-only.
Exact 10,000,000-byte and cap+1 requests exercise the gateway too. These are
controlled boundary checks, not concurrent-load capacity or independent review.

Evidence: [publication helpers](../../src/ml_pipeline_pro/dataset_files.py),
[upload route](../../src/ml_pipeline_pro/dataset_uploads.py),
[unit boundaries](../../tests/test_dataset_uploads.py),
[real-service checks](../../tests/integration/test_dataset_uploads.py), and
[dashboard run](../evidence/2026-10-19-dashboard/README.md).
Revisit before adding file deletion, retention, mutable uploads, network storage,
or additional worker concurrency.
