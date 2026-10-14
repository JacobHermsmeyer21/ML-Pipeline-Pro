# Preserve explicit current budgets in guided proposals

- Status: approved minimal guided direction; implementation pending
- Date: 2026-10-13
- Source baseline: `dd57e17` with monitoring delivery in progress
- Human approval: Jacob's October 13 approval of all recommendations and request to implement; [record](2026-10-13-midterm-delivery-plan.md#human-review-and-approval)
- Independent review: separate boundary reviewer; different-vendor unavailable

## Proposed behavior and purpose

Constrain supported explicit English budget expressions in the current request,
so history-based tuning cannot substitute the total runtime for the per-trial
runtime. Keep model-generated proposals and exact confirmation; reject mismatches,
without changing or repairing returned arguments.

## Clarification and critique

The real three-domain walkthrough saved a proposal with per-trial runtime 40
despite the current request saying 10 and total 40. The host requested confirmation
and dispatched nothing. Its saved output establishes the mechanism; the script
also confused turn `awaiting_confirmation` with action `pending_confirmation` and
will correct that check without weakening budget assertions. Earlier synthetic
ten-case passes do not establish this real-ID/history case.

Do not add general intent extraction or silently replace values. Recognize only
unambiguous current phrases such as `per-trial runtime is 10 seconds`, `runtime
10 seconds`, `maximum 2 trials`, and `40 seconds total` (or `total 40 seconds`).
Conflicting expressions receive no inferred value; existing semantic checks and
human confirmation remain. Explicit absence takes precedence. No new defaults.

## Requirements

| ID | Type | Requirement | Evidence |
| --- | --- | --- | --- |
| F1 | Functional | Current supported budget expressions constrain proposed configuration and limits. | Distinct per-trial/total regression with actual recorded IDs/history. |
| N1 | Reliability | Provider-ignored constraints fail safely; no retries, repairs or inferred missing values. | Scripted ignored-grammar case, current-only/conflicting/missing-expression tests. |

## Constraints and scope

No public API/schema/default/permission changes. Native mode and original
ten/seven semantic cases, budgets and failure accounting remain intact. No domain
dispatch before exact approval. No modification of saved proposals/fingerprints.
Only recognized unambiguous integers become constraints; all other values remain
model proposals requiring review. Keep original byte/token/call/deadline limits.

## Design

Extract a small current-only map for `config.max_runtime_seconds`,
`limits.max_trials` and `limits.max_runtime_seconds`. Add `const` to copied guided
schema definitions and require supplied nested values where relevant. Apply the
same constraints after decoding a create-experiment/tuning/draft call, rejecting
absent/wrong explicit values. Reads/final replies remain available; no rewrite.
Do not mutate the public tool schemas or base provenance across calls. Record
actual transmitted format identity and rerun original semantic/runtime gates.

## Acceptance and verification

Run focused SDK/guard cases and the full fast gates. Retain the failed real
walkthrough; one new complete run must demonstrate actual inspection/history,
correct proposed budgets, saved replay, explicit demo decision, tuning outcome,
generated draft and monitoring. Run original ten/seven live gates unchanged.
Seek separate review of narrow parser/arithmetic, schema isolation and rejection.

## Risks and rollback

Unsupported phrasing remains model behavior, not deterministic extraction.
Conflicts must not pick an arbitrary number. Reverting this guard retains saved
actions and native mode; it reopens the demonstrated real-history failure.

## Human review and approval

This implements current-input preservation within Jacob's approved minimal guided
workflow, not a broader natural-language parser or separately claimed review of
this document. Material changes to approved intent require renewed review.

## Implementation outcome

Implemented current-only schema constants and post-decode rejection. The separate
reviewer found signed/fractional numeric fragments and whitespace-dependent total
runtime classification; full whitespace-delimited numeric tokens and total-runtime
classification fix these with regressions. Conflicts/unsupported expressions remain
unconstrained, never converted to an inferred number. Public/native defaults intact.

The complete actual-ID/history walkthrough now verifies per-trial 10/total 40,
saved replay, explicit test approval, completed tuning, generated draft/replay and
monitoring. The script uses per-run request IDs because IDs are project-global;
it preserves `awaiting_confirmation` turn versus `pending_confirmation` action.
No budget assertion was weakened; failed attempts remain in the evidence. Cold
runtime failures led to an explicit setup warmup, not hidden retries or larger gates.

Focused SDK/parser/HTTP checks and full fast gate pass. Original ten conversation
and seven snippet gates retain all attempts, semantic assertions and budgets;
hardware/contention timing limits remain visible. Different-vendor review unavailable.
