# Preserve explicitly requested inspection facts

- Status: approved guided-fact scope; diagnosed fix pending
- Date: 2026-10-13
- Baseline: `db7002e`
- Request: Jacob's failed real demo at the inspection assertion
- Human approval: existing approved guided schema/fact direction and current bug report
- Independent review: separate boundary review; different-vendor unavailable

## Proposed behavior and purpose

Require explicitly requested fact references in a guided inspection reply when the
current successful lookup supplies the requested scalar. Keep values rendered by
the existing evidence ledger, and keep the original demo assertions and budgets.

## Clarification and critique

`artifacts/my-demo/results.json` records a completed reply with prose about F1=1.0
but `facts=[]`, after successful `get_experiment` of the requested record. The
walkthrough correctly rejects it. The copied guided reply schema permits omitted
or empty facts even when the current prompt requests a verified fact. This is a
semantic omission, not a timeout or a failed backend. Earlier passing runs do not
prove this request cannot fail.

Changing the assertion to accept prose, silently filling model references/values,
retrying a failed saved turn or merely rerunning the demo would not fix that
boundary. Add a narrow current-request constraint, analogous to existing explicit
missing-input/current-budget constraints; it is not general intent extraction.

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | Explicit Inspect + verified status/validation-metric request yields the corresponding reference after its successful current lookup. | Actual SDK format and real failed-record HTTP inspection; unchanged full walkthrough. |
| N1 | Reliability | Unknown, failed, foreign, relationship-only, absent-field or historical data cannot create required facts; ignored grammar rejects rather than repairs. | Positive/negative guard tests, decoded-output rejection and original ten/seven gates. |

## Constraints and scope

No public schemas/defaults, native behavior, project scoping, mutations, ownership,
artifact or persistence changes. Preserve original per-call/turn/suite and byte/
token limits, confirmation, host fact values and all existing assertions. Keep
the user's failed run unchanged. No new model selection, hidden retry or code execution.

## Design

Recognize only the current explicit Inspect ID plus positive `return a verified
metrics.validation_f1/metrics.validation_accuracy/status fact` or `return [its]
actual status as a verified fact` clauses. Explicit missing-input/draft requests
take precedence. Match the appropriate successful current lookup, actual snapshot
ID/record evidence, and a supplied scalar field; absent fields remain unconstrained.
Require the requested reference list in the copied guided reply schema. Other
read/proposal branches retain their existing behavior. After decoding, reject a
reply that ignores this constraint; never insert/rewrite its references or values.
Historical assistant context and embedded record instructions do not drive it.

Update exact-SDK format assertions to include the new constraint, without changing
semantic cases/budgets. Improve the walkthrough's assertion message to point at
the saved result, retaining the assertion itself. Document the supported syntax
and durable finding; no generic language-understanding promise.

## Acceptance and verification

Focused scripted tests prove required-reference inclusion, absent/default fields,
failed/foreign lookups, relationship IDs, negation/history and ignored grammar.
Run all fast gates and nine affected real conversation-store/API cases. Rebuild
the actual image, verify inspection against the saved failed record with a fresh
request ID (saved old turns remain immutable), then complete a new full walkthrough.
Run original ten/seven local-model gates unchanged, retaining failures and source/
request identity. Check documentation, package build and push; inspect remote CI.

## Risks and rollback

The guard supports explicit phrases only. It must not infer an unavailable metric
or coerce freeform model prose into facts. Grammar/token admission must include
the actual new schema; existing limits still apply. Rollback removes the additive
guard but does not rewrite saved turns, actions, drafts or training records.

## Human review and approval

Correction inside Jacob's already approved guided schema/fact semantics and request
to fix the demo; no separate human review of this document is claimed. Material
changes to public contracts, budgets or action permissions require renewed review.

## Implementation outcome

Pending. The original saved omission is retained as the failing baseline.
