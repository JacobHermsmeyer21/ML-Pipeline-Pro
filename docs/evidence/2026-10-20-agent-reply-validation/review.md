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
