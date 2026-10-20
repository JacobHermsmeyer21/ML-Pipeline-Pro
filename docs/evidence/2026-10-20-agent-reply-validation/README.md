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

[Separate boundary review](review.md) found no blocking issue. Shared fact guidance,
dashboard behavior, complete ordinary integration and post-fix hosted acceptance
remain pending at this stage. Human usefulness review remains separate.
