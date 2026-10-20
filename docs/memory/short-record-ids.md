# Short references must preserve canonical evidence and request fingerprints

Recorded October 20, 2026 under the approved
[short-ID plan](../plans/2026-10-20-short-record-ids-plan.md).

Experiment `eN` and conversation `cN` aliases are permanent project-scoped
mappings. Allocate them in the transaction publishing the record; tuning children
still write the parent ownership fence in that same transaction. Counter updates
roll back with rejected publication. Retain mappings/counters across deletion so
an old reference cannot select a new record. Canonical UUIDs remain the identity
for artifacts, ownership, fact references and action hashes.

Normalize typed aliases for lookup without modifying the original request before
fingerprinting. The transaction and replay checks confirm that an exact `c1`
request replays, while replacing it with the UUID under the same request key is a
different body. Migration adds parent metadata and projects aliases on history
reads; it does not rewrite saved turn payloads or hashes.

Tool dispatch checks returned IDs against canonical resolved IDs. Requested-fact
guidance must also match a supplied experiment's `short_id` to its canonical `id`
and verify the canonical evidence reference; otherwise an `e1` inspection loses
the explicit requested-fact constraint. Facts continue to cite canonical IDs.

Evidence: [real transaction/migration tests](../../tests/integration/test_short_ids.py),
[API/tool negative tests](../../tests/test_short_ids.py),
[browser/local-model harness](../../scripts/verify_short_ids.py) and
[retained results](../evidence/2026-10-20-short-ids/README.md).
Twelve concurrent allocations establish that tested workload, not an arbitrary
load/scaling claim. Existing-data migration requires paused writers, and older
applications require canonical IDs. Revisit when adding record namespaces,
cross-project references, new canonical-ID producers or online migration.
