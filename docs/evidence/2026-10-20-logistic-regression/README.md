# Logistic regression implementation evidence

Jacob approved the [plan](../../plans/2026-10-20-logistic-regression-plan.md) in chat
on October 20, 2026. Approval record `10e9f37` is published on `origin/main`.
Implementation is published in `5c5f429`, followed by normalization and explicit
dashboard errors in `dbfaae6`. The [provenance record](provenance.json) verifies
that all 76 installed files in the final API/worker and recovery packages match
the published final application source. Earlier browser/command records retain
their original base revision and working-tree flag rather than relabeling runs.

## Scope and test justification

The implementation adds immutable logistic model definitions, a strict tagged
config, explicit worker dispatch, linear binary/multiclass training, weight-only
L2, checkpoint reconstruction, dashboard controls and unsupported AI/tuning guards.
Existing MLP configuration serialization and defaults remain unchanged. Ownership,
leases, cancellation, concurrency, resource bounds and dependencies are unchanged.
No course requirement is closed by this baseline algorithm.

New tests cover the plan's F1–F5/N1 boundaries: legacy payload/hash serialization,
same-key replay before reference checks, mismatched admission without dispatch,
host rejection before proposal persistence, stale/direct tool rejection, worker
algorithm checks, binary/multiclass metrics independently calculated with
scikit-learn, selected in-memory versus reloaded predictions, training-only scaling,
test-label isolation, exact L2 gradients including unpenalized bias, malformed
checkpoint tags/dimensions, artifact downloads and registration. The ordinary
queued-worker test is parameterized for both algorithms with its existing success,
isolation, replay and artifact assertions preserved. New recovery cases kill the
logistic worker and hold a logistic minibatch past its runtime budget.

Three existing action/transport test fixtures now answer the required model GET
before their original mutation boundary. Their POST count/key, malformed response,
storage-loss and optional-refresh assertions are preserved. No assertions were
weakened, gates lowered or skips added.

Initial targeted runs found a duplicate model preflight read and two fixtures
that did not support model reads; both were corrected. The first synthetic binary
fixture added a holdout offset to a constant feature, which training-only scaling
amplified by its `1e-6` floor. Varying that feature within every split produces the
intended separable fixture; the accuracy threshold remains unchanged. The first
browser script forgot to reopen collapsed settings after its deliberate reload;
the corrected walkthrough passes without an application change.

Final review also reproduced a canonicalization mismatch in the initial logistic
default: an integer `0` default serialized differently after Pydantic revalidation
as a float. The final `0.0` default and a regression test make omitted and explicit
defaults serialize identically. MLP fields/hashes are unchanged. The
[saved reproduction](default-normalization.json) reconstructs the old field from
`5c5f429` and compares final behavior. The final dashboard maps the safe unsupported
algorithm code to a fixed manual-training explanation for turns and stale actions.

## Automated verification

| Gate | Result | Retained raw evidence |
| --- | --- | --- |
| Locked sync, Ruff lint/format, dependency compatibility, package build | All five commands exit 0 | [Exact commands/output](checks.json) |
| Fast suite with coverage | 823 pass, zero failures/errors/skips; 118 integration cases deselected | [JUnit](fast.xml), [log/coverage](fast.log) |
| Ordinary real-service integration | 106 pass, zero failures/errors/skips; both required flags enabled | [JUnit](ordinary.xml) |
| First serial recovery run before default normalization/UI explanation | 12 pass, zero failures/errors/skips | [JUnit](recovery-before-normalization.xml) |
| Final committed-source serial recovery | 12 pass, zero failures/errors/skips; 929 unrelated cases deselected | [JUnit](recovery.xml), [log](recovery.log), raw logistic snapshots listed in [provenance](provenance.json) |
| Final browser/worker walkthrough | Three runs pass, including lost response/reload/same-key replay, comparison and registration | [Execution report](browser.json), [comparison screenshot](comparison.png), [multiclass run](multiclass-run.png) |

Fast coverage rounds to 80%; it measures the host test process, not container
workers. Ordinary integration ran on the final backend after normalization; the
later text-only dashboard explanation is covered by the final browser/package
checks. It does not alter API/worker behavior. No selected skips are counted as
passes. The first recovery run includes a 9m39s image build downloading unchanged
locked dependencies; the final run uses cached dependencies and preserves all
timeouts/assertions. Package contents include the architecture selector, float L2
default and explicit error explanation.

The final recovery suite completes in 281.64 seconds on `dbfaae6`, with the same
76 installed files as the final ordinary/browser image. It verifies both logistic
cases and all ten existing MLP/tuning/ownership recovery cases. The recovered
logistic experiment retains its ID/config with two attempts and verified artifacts;
the expired experiment fails with no artifact references. The detailed logistic
before/after/failure snapshots are retained unchanged alongside this report.

The browser uses Chrome through optional Playwright 1.64.0 and a disposable
`logistic_browser_9d171e740585` project on API port 18000. Its script is
[`verify_logistic_dashboard.py`](../../../scripts/verify_logistic_dashboard.py).
The replay exercise lets the server accept a real request, drops its response,
changes the selected model, reloads, and asserts the original body/key is retried.
Both binary runs use the same dataset version. All three fixed synthetic runs
report validation/test accuracy and macro-F1 of 1.0; this is fixture acceptance,
not a generalization or superiority result. Actual configs, selected epochs,
dependency versions, artifact hashes/sizes and timing are in the execution report.

[Independent checkpoint checks](checkpoint-checks.json) retain exact predictions,
targets, independently calculated metrics and preprocessing values. The
[binary CSV](classes-2.csv) and [three-class CSV](classes-3.csv) exactly match the
registered dataset hashes. Downloaded checkpoints pass recorded hash/size checks;
their mean/std equal training-only values and reloaded metrics agree within `1e-6`.
The unit suite additionally compares reloaded predictions exactly with the selected
in-memory state and verifies that test-label changes cannot select weights.

Local detailed service logs and additional snapshots remain under
`artifacts/logistic-validation/`, `artifacts/logistic-*.log` and
`artifacts/recovery-validation/`. The ordinary/browser stack uses a separate Compose
project `mlpp-logistic-validation-20261020` with independent volumes/ports; existing
demo records and deployment were not changed. The validation containers were
stopped after acceptance, retaining their records/volumes; the recovery fixture
removed its disposable stack/volumes after retaining snapshots. Reproduce using the
[dashboard command](../../guides/dashboard.md#compare-algorithms) and
[ordinary/recovery gates](../../guides/verification.md).

## Review and remaining limits

Implementing assistant self-review covers legacy serialization, architecture
dispatch, checkpoint loading, artifact publication, unsupported-action guards and
the final diff. This is not independent review. No concurrency, state machine or
rate/size arithmetic was changed; independent review is unavailable in this
session. Human usefulness review of the completed selector/comparison flow remains
open. No live AI understanding or generated-logistic-snippet acceptance is claimed.
Only fixed separable synthetic data and existing regression fixtures are tested;
no algorithm superiority or convergence/generalization claim follows.
