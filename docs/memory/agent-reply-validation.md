# Model-visible fact choices must match the host ledger

October 20, 2026; [approved plan](../plans/2026-10-20-agent-reply-validation-plan.md)
and [retained evidence](../evidence/2026-10-20-agent-reply-validation/README.md).

Conversation `7d497f4b` failed after a successful experiment read, but generic
`model_invalid_response` persistence discarded its exact rejection reason.
Two instrumented fresh requests reproduced `evidence_resolution /
unsupported_fact_field`. The lost original field remains unknown. A synthetic
best-epoch reference establishes a real mismatch: public experiment metrics can
contain fields the conversation fact policy does not accept.

A context list alone still failed in the first hosted correction attempt.
The implemented boundary shares scalar/path/identity resolution with available
fact references, adds per-request model-facing completion field/record-ID enum
hints, and excludes unsupported metrics from model context while preserving full
saved tool results. Host validation still checks exact pairs; enum hints do not
authorize new facts. Bound schemas derive from redacted context and are copied
per request; their hash travels with per-request usage, not shared mutable state.

The stronger correction completed the original request with 13 supplied facts and
qualified validation-only suggestions, with exact zero-inference replay. A later
attempt was refused before sending because its reservation would cross the $0.23
stop. All additional reservations total $0.212239 under the separate $0.25 cap.
Three-success hosted acceptance and human usefulness review remain outstanding.

Future failures save only fixed stage/reason metadata and correlated logs; no raw
reply, exception input or untrusted field name enters diagnostic details. Legacy
saved turns remain generic. Revisit new fact paths, completion schemas, context
minimization, provider wrappers and SDK upgrades. Keep the original rejected
references rejected unless a separately reviewed policy change permits them.
