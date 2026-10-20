# Reply validation boundary review

October 20, 2026. Reviewer: separate Codex/OpenAI agent
`/root/reply_boundary_review`; same vendor as implementation. A different-vendor
review was unavailable. This is a separate source review, not human usefulness
acceptance of model advice.

Submitted scope: the [approved plan](../../plans/2026-10-20-agent-reply-validation-plan.md),
working changes to per-run budget authorization, fixed-code diagnostics and
the reproduction runner, based on `df10153`. No reviewer source edits or paid
requests. The reviewer independently ran budget, provider and host tests:
**84 passed**.

No blocking findings. Frozen Decimal authorization, strict ledger-header matching,
upward micro-dollar rounding, durable reservations before counting/generation,
retained failed/uncertain reservations and preserved old defaults enforce the
new $0.25 authorization/$0.23 stop under the stated pricing assumptions.
The runner uses a separate fixed ledger, refuses existing phase reports, and
checks saved replay against unchanged reservations/provider-event counts.
Diagnostic metadata admits only fixed stage/reason pairs. Persistence ownership
and replay mechanisms were not changed.

Limits identified: official pricing and real MongoDB replay require execution;
usefulness and validation-only advice require human review. A completed baseline
report does not mean the agent's replies succeeded. Those checks and model
outcomes are recorded separately in the final evidence.

## Fact guidance and runner follow-up

Submitted scope: working correction on `950c00d`, shared scalar resolution and
available references, model-facing completion enum hints, context-only metric
filtering, per-request schema hash and explicit runner resume. The separate
reviewer independently ran grounding/provider/host tests: **78 passed**.

Two medium findings were fixed before resuming live testing:

1. A retained failed attempt plus two later successes could incorrectly set the
   aggregate acceptance result to true. `phase_passed` now requires exactly three
   retained per-attempt acceptance successes.
2. Reading a phase report before acquiring the budget lock could overwrite newer
   attempts after a staggered invocation. Existence/read/limit/resume admission
   now happen under the same exclusive ledger lock as spending admission.

The reviewer confirmed both resolutions and independently ran the three new
runner regressions, including controlled report advancement between invocation
and lock acquisition. No remaining findings. Source review confirmed unchanged
host rejection rules, exact normalized request counting, preserved audit tool
snapshots and no shared mutation of native tool definitions/provenance.
Individual record-ID/field enums guide generation; the host still verifies exact
pairs against current evidence.

A final source-only review confirmed schema enums derive from already-redacted
model context. The added outbound-request regression protects against secrets
embedded in record IDs reappearing in a schema. No tests or paid calls were run
by the reviewer during that last review. The same-vendor limitation remains.
