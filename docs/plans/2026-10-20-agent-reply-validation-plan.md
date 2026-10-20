# Diagnose and correct rejected agent replies

- Status: implemented; three-success hosted acceptance and human usefulness review outstanding
- Date: 2026-10-20 (America/New_York)
- Source baseline: `a75da54` / `main`; fetched upstream and `origin/main` match
- Request: plan a fix for conversation `7d497f4b` failing after an experiment read
- Human reviewer/approval: Jacob approved the plan at `8c4f985` on October 20,
  2026 with "i appove, implement it"; the separately approved additional test cap
  is **$0.25**
- Independent review: seek a separate reviewer for test-budget arithmetic and
  persistence/replay compatibility; record availability and findings

## Proposed behavior and purpose

The pipeline agent should answer experiment-inspection and F1-tuning questions
using current experiment facts and clearly identified suggestions. When a model
reply cannot be accepted, the saved turn and dashboard should explain the failed
validation category without exposing raw model output or exception text.

First make failures attributable, then align the model's reply instructions with
the facts the host actually accepts and correct any reproduced parsing defect.
Preserve validation-only tuning advice and exact-action confirmation. This
supports C3/C5/C9 in the [course checklist](../project/course-requirements.md);
it does not establish new local-model or deployment acceptance.

## Clarification and critique

Read-only investigation of saved conversation
`7d497f4b-76eb-419e-9ce7-ecad87535392`, turn
`8ad5464b-22bb-4def-b3d1-d31a5b14f444`, found:

- The request inspected experiment `508815fb-1652-475e-aba9-c68281270704`
  and asked for more run facts and ways to improve F1.
- The saved provider was OpenAI `gpt-5.4-mini`; `get_experiment` succeeded.
  The experiment succeeded and supplied validation F1 `0.8443759876139247`.
- Model API logs for correlation ID `7ed0bea8c2efda15863aa6ae4d8e950f`
  show two successful token-count/generation pairs and completed inference
  boundaries, followed by failure persistence at 21:05:14 UTC on October 20.
  Total turn time was about 6.5 seconds; saved error was
  `model_invalid_response`, internal HTTP status 422.
- The [host error handler](../../src/ml_pipeline_pro/conversation_service.py)
  replaces schema and evidence rejection details with a fixed generic message.
  The rejected reply was not retained. The original failing field is **unknown**.

Source inspection also finds that the
[ledger](../../src/ml_pipeline_pro/conversation_grounding.py) accepts a fixed
set of scalar fact paths, whereas a retrieved experiment can contain other
fields, such as `metrics.best_epoch`. The
[model instructions](../../src/ml_pipeline_pro/conversation_model.py) provide
examples rather than the exact available references. This is a demonstrated
contract mismatch, **not proof** that best-epoch facts caused this incident.

Simply retrying the request might succeed but would neither establish the
mechanism nor improve future diagnosis. Dropping invalid facts silently would
hide defects; accepting arbitrary paths would weaken grounding. Capturing full
model responses would add avoidable data retention. Choose fixed safe diagnostic
codes and explicit accepted references instead. No automatic repair call is
proposed: additional inference would introduce spending and lifecycle changes.

The scope and budget decisions below are proposed for human review. No remaining
intent question prevents review; the exact original rejection remains an
investigation limit, not a question the user can answer.

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | New rejected replies save a bounded validation stage/reason and correlation ID; old failures remain readable. | Provider, host, API/history and legacy-record regressions. |
| F2 | Functional | Give the model exact currently admissible fact references, derived from the same rules used to resolve facts. | Valid-reference tests plus missing, ambiguous, foreign, nonscalar and holdout exclusions. |
| F3 | Functional | An instrumented reproduction identifies a rejection category; correct a confirmed defect within this scope. | Before/after deterministic regression and saved live attempt, if reproduced. Historical exact cause stays unknown if unrecoverable. |
| F4 | Functional | The original inspection/tuning request returns supported facts and useful validation-based suggestions without submitting work. | Three fresh hosted attempts, saved HTTP history and human review; budget exhaustion leaves this criterion open. |
| F5 | Functional | Dashboard failures show a fixed readable reason and correlation ID; legacy/unknown reasons use the generic fallback. | Browser checks of new, legacy and unrecognized metadata, including hostile strings. |
| N1 | Security | No raw replies, user-supplied field names, model values, credentials or SDK exception strings enter diagnostic metadata/logs. | Nested-secret and hostile-provider/field fixtures reaching each rejection boundary. |
| N2 | Reliability | Preserve grounding, public status codes, exact replay, project scoping, ownership and action confirmation; add no inference retry. | Existing negative checks, zero-call replay assertions and real MongoDB persistence tests. |
| N3 | Resources | Preserve model, token/byte/call/time limits; additional live testing stays within its separately approved $0.25 authorization. | Exact-request admission tests and durable conservative reservations stopping at $0.23. |

## Constraints and scope

Keep `/api/v1/chat`, history routes and turn states unchanged. The only planned
public addition is optional fixed diagnostic metadata inside the existing `error`
dictionary. Preserve `error.code`, `error.http_status` and `error.message`, and
the current transport behavior: a persisted failed chat turn can return HTTP 200
while its saved error has status 422. Document that distinction in
[the OpenAI guide](../guides/openai-agent.md).

Do not change MongoDB ownership predicates, transaction boundaries, submission
keys, expiry, artifacts, training, or worker concurrency. No new route or runtime
configuration, model switch, dependency update, automatic mutation, fact-policy
expansion, or automatic execution of Python. Preserve explicit Ollama operation.
The original failed turn remains immutable; fresh tests use new request identities.

## Design

1. **Save safe rejection categories.** Add a small shared internal diagnostic type
   with fixed stage/reason enums. Instrument the provider envelope, parsed reply,
   host step/usage and evidence-resolution boundaries. Examples of stages are
   `provider_response`, `reply_schema`, `host_step`, `evidence_resolution`;
   reasons include `invalid_json`, `invalid_reply_schema`, `unknown_citation`,
   `unsupported_fact_field`, `missing_fact_field`, `ambiguous_record`,
   `nonscalar_fact`, `invalid_usage` and a fixed unknown fallback. Enumerate the
   final mapping before coding. Never serialize exception messages, Pydantic
   inputs or unchecked validation locations. Preserve categories when SDK wrappers
   obscure causes. Emit a correlated fixed-code log at the host boundary and save
   `error.details.validation_stage` / `error.details.validation_reason`.
   Unrecognized metadata maps to the generic fallback. Older records need no
   backfill; older clients can ignore the additional keys.
2. **Align available facts with resolution.** Share the existing path/scalar/
   project/identity rules between ledger resolution and a deterministic list of
   available `{record_id, field}` references. Include that bounded host-generated
   list in model context after successful reads; it is guidance, never authority.
   Continue to reject references absent from current successful snapshots,
   ambiguous record identities and unsupported paths. Keep holdout metrics out of
   model context and selection. Expose no new measured fact fields. Preserve
   valid related-record citations without treating an unfetched parent as a fact
   source. Ensure the added context is covered by exact SDK token counting and
   existing byte limits, including the empty-list case.
3. **Reproduce and fix narrowly.** Run instrumented fresh attempts of the original
   prompt using the existing record, or a recorded equivalent if unavailable.
   Retain stage/reason, safe usage/timing and host-accepted facts, not the raw
   rejected reply. Translate a reproduced rejection into a minimal synthetic
   offline failing case. Correct prompt/reference alignment or a proven reply
   decoding defect while preserving existing schemas and negative checks.
   A needed policy expansion, different model/protocol or automatic retry requires
   an amended plan and renewed review. If the failure does not recur, report that
   limit and do not claim the historical root cause has been established.
4. **Explain failures in the UI.** Update
   [agent.js](../../src/ml_pipeline_pro/dashboard/agent.js) with fixed reason-to-copy
   mappings, rendered as text alongside the saved correlation ID. Do not render
   arbitrary `details` content or suggest retrying automatically. An old turn such
   as `7d497f4b` continues to show the generic explanation because its detail was
   never saved.
5. **Enforce the new testing cap.** The
   [current budget guard](../../src/ml_pipeline_pro/openai_test_budget.py) hardcodes
   the earlier $2 authorization and $1.90 stop. Parameterize its immutable per-run
   authorization/stop values with the same old defaults and strict ledger matching;
   do not edit or reset the old ledger or mutate module constants. A separate
   diagnosis runner/ledger uses $0.25 authorization and $0.23 reservation stop,
   retaining $0.02 margin and all failed/uncertain reservations. Charge counting
   conservatively at full input rate as previously approved; reserve before every
   request, include diagnostics and reruns, use no SDK retries and refuse stale
   pricing. Recheck official pricing before live execution. The cap covers this
   runner, not unrelated dashboard activity or an account-wide reconciled bill.

## Acceptance and verification

Implement in small slices: diagnostics and regressions; budget guard/runner;
instrumented baseline before changing model guidance; shared fact guidance and
any reproduced correction with regressions; dashboard, documentation and final
acceptance. Run targeted tests after each meaningful step. The baseline uses
the original instructions with only safe diagnostics added.

Exercise `tests/test_conversation_openai.py`, `test_conversation_grounding.py`,
`test_conversation_service.py`, `test_conversation_api.py`,
`test_conversation_schemas.py`, `test_openai_test_budget.py` and
`test_dashboard.py`. Test valid replies, malformed completion arguments, unsupported
and missing fact paths, unknown citations, non-scalar values, zero-valued facts,
cross-project/colliding IDs and missing upstream fields. Every diagnostic fixture
must reach the intended boundary. Keep existing rejection assertions; annotate
any changed test with the requirement it now checks.

Run all [fast checks](../../AGENTS.md#verification-commands) before application
commits: `uv sync --locked --extra training`, Ruff check and format check,
`uv run --locked --extra training pytest -m "not integration" --cov`, and
`uv pip check`. Use the workspace's installed `uv` executable/cache as needed.
Run ordinary integration per the
[verification guide](../guides/verification.md#ordinary-integration), with both
`MLPP_RUN_INTEGRATION=1` and `MLPP_RUN_WORKER_INTEGRATION=1`, including new real-store
failure persistence/history/replay assertions. Run separate serial recovery gates
if lifecycle, ownership or recovery code changes; the planned work leaves those
mechanisms unchanged. Record missing services/skips as gaps.

For hosted acceptance, budget for at most two diagnostic baseline attempts and
three post-fix fresh turns of the original request. Stop before any reservation
would cross $0.23; never enlarge the cap to reach a pass. Each post-fix turn must
complete, cite the current experiment, render its validation-F1/configuration facts
from saved evidence, offer clearly qualified tuning suggestions and create no
action/submission. Replay each saved request and confirm zero additional provider
calls. Save source/model identity, request/correlation IDs, stage/reason, usage,
timings, failures and reservation totals. Three passes establish this narrow
acceptance workload, not general model reliability. Human review checks usefulness
and validation-only advice. If funds or nondeterminism prevent completion, leave
hosted correction acceptance explicitly outstanding.

Use offline browser fixtures to inspect safe readable failures, fallback behavior
and text rendering; inspect the rebuilt local dashboard with saved history without
an extra model call. Seek separate review of budget rounding/admission, sanitized
error propagation and replay compatibility; disclose unavailable review. Update
evidence and durable memory. Fetch/compare incoming changes, commit and push each
major completed slice under [the workflow](../../AGENTS.md#repository-workflow).

## Risks and rollback

The historical reply cannot be reconstructed from generic saved errors; a fresh
success cannot prove its cause. More detailed categories must not leak raw fields
or secrets. Fact guidance consumes context and may not eliminate model mistakes.
The test cap may prevent all desired runs. Keep each limitation visible.

Rollback with ordinary revert commits, retaining published history. Revert UI and
model guidance independently if needed; restore the previous provider/host behavior
without editing saved turns. Additional optional diagnostic keys are compatible
with old readers; no migration or destructive backfill is required. Preserve both
budget ledgers and all uncertain reservations during rollback.

## Human review and approval

Jacob approved up to **$0.25 additional OpenAI testing** on October 20, 2026 in
response to the explicit budget question. That approves the cap, not this written
implementation design. Jacob subsequently approved this written plan at `8c4f985`
with "i appove, implement it" on October 20, 2026. Approval covers the diagnostic
metadata, shared fact guidance, narrow reproduced corrections, dashboard copy,
budget guard and capped verification described above. No paid test was performed
while preparing the plan; implementation now proceeds within this scope.

## Implementation outcome

- Approval: `df10153`; diagnostics/budget/baseline slice: `950c00d`, pushed to
  `origin/main`. Correction slice follows that commit; final publication is
  recorded in Git history and the delivery response.
- [Retained evidence](../evidence/2026-10-20-agent-reply-validation/README.md)
  includes source hashes, failed baseline and correction attempts, successful
  output, exact zero-inference replay, reservation ledger and browser checks.
  Two original-instruction reproductions identify unsupported fact references;
  the precise lost original field remains unknown.
- Implementation refinement within the approved guidance scope: a reference
  list alone failed in a hosted attempt, so the completion schema also advertises
  available field/record-ID enum choices and unsupported metrics are omitted
  from model context. Public schemas, host acceptance policy and full saved tool
  snapshots remain intact. Dynamic schemas use redacted context and request-local
  hashes; no shared tool/provenance mutation or automatic inference retry.
- Final gates: Windows/Python 3.11.5, locked training dependencies; 805 fast
  passes, 105 ordinary integration passes without selected skips; Ruff lint/format,
  dependency checks and package builds pass. Both ordinary integration flags were
  set. Recovery mechanisms were unchanged, so no separate recovery rerun.
- Tests add category propagation, negative evidence boundaries, shared reference
  consistency, actual SDK count/send schemas, redacted enum generation, real
  persistence/replay and dashboard fallback/rendering evidence. The memory-store
  substitute now returns the real store's scoped 404; the existing assertion
  remains. An unchanged timing test failed once, then passed in isolation and
  the serial full suite; no assertion, timeout or skip was weakened.
- [Separate review](../evidence/2026-10-20-agent-reply-validation/review.md):
  Codex/OpenAI, same vendor; different-vendor review unavailable. Two runner
  resume findings were resolved with controlled interleaving/aggregate-result
  regressions before the final hosted attempt. Final security source review
  confirms enum generation uses redacted context.
- Hosted result: the stronger correction completes the original request with 13
  actual facts and qualified suggestions; a later request is refused before send.
  Total additional reservations: **$0.212239**, below the $0.23 stop/$0.25 cap.
  Three-success acceptance F4 and human usefulness review remain outstanding;
  no extra spending or relaxed success threshold was used. Final secret-redaction
  hardening has offline coverage, not a further paid rerun.
- Local dashboard/model API rebuilt with existing data preserved. Old turn
  `7d497f4b` remains failed/generic. No substantive design deviation or new
  approval request; paid authorization and failure policy remain unchanged.
- Durable finding: [fact guidance and validation](../memory/agent-reply-validation.md).
