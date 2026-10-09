# Later errors cannot erase an uncertain submission

Recorded October 8, 2026 on baseline `2b9dfaf` during Person A's action slice.

A 5xx, malformed response, expired owner or lost chat process can occur after the
domain API has accepted training/tuning. Mark the attempt `unknown`; persist the
original immutable body/key and never treat missing audit completion as failed
submission. A subsequent definitive 4xx describes that attempt only, so the
action remains unknown until successful replay resolves earlier uncertainty.
Keep each attempt's safe outcome, including accepted IDs. Three dispatches are
the limit; no replacement action/key is created automatically.

The [real transaction tests](../../tests/integration/test_conversation_actions.py)
verify revision-independent retry of approved unknown actions, preserved keys,
later-4xx uncertainty, competing approval snapshots and stale attempt rejection.
The [real process test](../../tests/integration/test_conversation_dispatch.py)
kills a disposable chat API after upstream acceptance, waits for natural expiry
and restarts it: explicit same-action approval resolves to one experiment.
The transaction writes the conversation parent and action together; external
dispatch is outside retryable callbacks.

Forced expiry after a completion snapshot exposed another mechanism: reusing a
deadline predicate built before an awaited database operation admits a late
write even without a takeover. Action and turn completion now rebuild the
deadline predicate at the final mutation. The
[action failure](../evidence/2026-10-08-conversation-actions/expired-completion-before.txt)
and [turn failure](../evidence/2026-10-08-conversation-actions/expired-turn-before.txt)
retain the failing assertions; the same boundary tests pass after correction.

A slow optional record refresh also consumed the dispatch deadline before a
known accepted ID could be saved. The
[failing boundary](../evidence/2026-10-08-conversation-actions/refresh-timeout-before.txt)
shows no audit completion. Refresh now admits only with two dependency-timeout
allowances remaining, uses one allowance, and marks a timed-out/skipped refresh
unavailable while saving the original result. This reserves time for persistence;
an unavailable database can still prevent saving it. Storage failures report
uncertainty and known action identity.

These runs prove tested host/API/ownership boundaries, not model understanding,
independent review, network-partition safety or concurrent training capacity.
Revisit when changing attempt deadlines, API idempotency or cancellation semantics.
