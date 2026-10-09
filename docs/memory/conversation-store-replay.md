# Conversation completion needs a parent write and BSON-precision timestamps

Recorded October 8, 2026 during Person A's durable store slice, baseline `813a01d`.

The store reserves/reconciles/completes turns and saves pending proposals using
a conversation write in the same MongoDB transaction. Controlled real-MongoDB
interleavings establish an old snapshot, replace the expired owner, then resume
completion: stale answers and proposals reject without changing the replacement
owner or adding an action. Simultaneous first requests also establish both absent
snapshots before reservation; the unique request index leaves one identity and
no orphan conversation. Retry callbacks retain preallocated proposal IDs/keys.
This follows the [existing parent-fence finding](tuning-parent-fence.md).

A new replay regression with a `123456`-microsecond clock failed because BSON
returned the saved deadline at `123000` microseconds. Conversation clocks,
deadlines and proposal expiry now use UTC milliseconds before persistence and
response construction. The regression compares original/replayed deadlines and
full proposal responses exactly, rather than weakening equality assertions.
This aligns with the actual stored deadline; it does not extend a turn's budget.

Evidence: [store](../../src/ml_pipeline_pro/conversation_store.py),
[real transaction/precision cases](../../tests/integration/test_conversation_store.py),
and [plan outcome](../plans/2026-10-06-conversation-workflows-plan.md#person-a-durable-turn-store-october-8-2026).
The outcome links retained raw results, including the before-fix failure.

These cases prove store sessions/controlled interleavings, not independent review,
chat HTTP authentication, action decisions/dispatch, unknown-outcome recovery,
or chat process loss. No model or upstream HTTP call runs in a transaction.
Revisit when implementing those pending operations or changing persistence/time
precision; retain immutable IDs, the original deadline and parent-write predicates.
