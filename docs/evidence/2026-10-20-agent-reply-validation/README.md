# Agent reply validation correction

Approved [plan](../../plans/2026-10-20-agent-reply-validation-plan.md), October 20,
2026. Baseline application is `a75da54`; implementation begins after approval
commit `df10153`. This record is updated as each approved slice completes.

## Diagnostic baseline

[Saved baseline report](baseline.json) records two fresh requests using the
original experiment and unchanged model instructions, with diagnostics added.
Both fail at `evidence_resolution / unsupported_fact_field`, retain the successful
experiment read, and replay exactly without another model call. This establishes
the new reproductions' rejection category, not the lost original reply's precise
field. Synthetic regression `metrics.best_epoch` proves the whitelist mismatch;
no raw rejected model output or private prompt snapshot is archived.

The report's `passed: true` means baseline execution/replay checks completed;
both attempts' `status` is `failed`. It retains source hashes, returned model
identity, safe token/timing metadata and request/correlation IDs. All eight
count/generation reservations total **$0.103084** against a separate $0.25
authorization and $0.23 stop. The original provider-test ledger is untouched.

Diagnostic slice checks on Windows / Python 3.11.5, locked training environment:
Ruff lint/format, locked sync and dependency checks pass; **794 fast tests pass**,
115 integration cases deselected, coverage 80%. A new targeted real-MongoDB
diagnostic persistence/replay/scoping case passes. Local raw outputs are
`artifacts/agent-reply-validation/diagnostic-fast-fixed.{log,xml}` and
`diagnostic-mongo.xml`. An initial fast run exposed a missing scoped-not-found
behavior in the in-memory test substitute; its contract was corrected while
retaining the HTTP 404 assertion. No application scoping predicate changed.

[Separate boundary review](review.md) records the initial clean review and later
runner findings/resolutions. The results below supersede the diagnostic slice's
pending status without turning the failed baseline into acceptance.

## Correction and remaining acceptance

A model-context reference list alone still failed: attempt 1 in
[the acceptance report](acceptance.json) repeats `unsupported_fact_field`.
The stronger correction also narrows model-facing completion field/record-ID
choices from current references and excludes unsupported metrics from model
context. Public schemas and accepted fact paths are unchanged. The host remains
the authority for exact record/field pairs, with full tool snapshots preserved.

Attempt 2 completed the original request in conversation
`3a92c251-1403-42aa-b332-b143c3c4eec0`: 13 structured facts matched the experiment,
including validation F1 and all six configuration values. It offered qualified
validation-based tuning guidance, created no action/snippet and replayed exactly
without inference. [Reviewable output](human-review.md) is awaiting Jacob's
usefulness review. The report retains both the earlier failed attempt and the
explicit resume's source hashes. A final redaction hardening change was tested
offline after this hosted success; no further paid call was made for it.

Attempt 3 was refused by budget admission before sending. The independent
[reservation ledger](live-budget.json) totals **$0.212239**, below its $0.23 stop
and separately approved $0.25 authorization. These are conservative reservations,
not a reconciled provider bill. The previous $2 provider-test ledger was not reset
or changed. Three successful fresh attempts were **not** obtained; `passed: false`
in the aggregate report is intentional. Broader hosted reliability, usefulness,
the lost original field and earlier local/Kubernetes acceptance gaps remain open.

## Final verification

Final Windows / Python 3.11.5 locked training environment: **805 fast tests pass**,
115 integration cases deselected; coverage 80%. Locked sync, Ruff lint and format,
dependency compatibility and package source/wheel builds pass. **105 ordinary
integration tests pass**, no selected skips, using both required integration flags
and the existing Compose stack. New real-MongoDB tests retain diagnostic errors,
successful tool evidence, scoped history and exact replay after a store restart.
No transaction/ownership/recovery mechanism changed; the separate destructive
recovery suite was not rerun for this correction.

An earlier full run failed the unchanged 100 ms overall-tuning-deadline test while
other work was running. Its isolated recheck and the final serial full suite pass;
no assertion, deadline or skip was changed. Failed and successful logs remain
under `artifacts/agent-reply-validation/`.

[Source browser checks](browser-source.json) and
[deployed browser checks](browser-deployed.json), Chrome 155, verify readable
failure categories, generic legacy fallback, invalid-pair fallback and hostile
content rendered as text. All API writes were blocked; no model call was made.
The existing local model API/dashboard container was rebuilt/replaced, preserving
project volumes and other running services. The original failed turn was not
rewritten. [Final read-only delivery checks](delivery.json) verify the running
provider file hash against final source, the new dashboard module, OpenAI config,
the untouched original failure and the readable 13-fact success. Raw successful
gate logs/XML and the browser/delivery procedures are retained in
[checks.zip](checks.zip); local originals are `final-fast-serial.{log,xml}`,
`final-integration.{log,xml}` and `verify_browser.py` under the artifact directory.

The [review record](review.md) discloses the same-vendor limitation and the two
resolved resume defects: false aggregate acceptance and stale report overwrite.
The tests exercise each failure precondition without relaxing existing checks.
