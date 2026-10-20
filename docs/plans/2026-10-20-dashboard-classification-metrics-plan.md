# Dashboard classification metrics

- Status: awaiting review
- Date: 2026-10-20
- Source baseline: `d0fad5a`, `main`; fetched origin, upstream and origin/main match.
- Request: show F1, precision, recall and accuracy in the dashboard.
- Human reviewer/approval: pending Jacob's review of this plan.
- Independent review: availability unknown; no concurrency or ownership changes planned.

## Proposed behavior and purpose

Show validation F1, precision, recall and accuracy side by side in the recent
experiment table and run details. Retain the existing best validation F1 summary
and F1 comparison/ranking. New MLP and logistic regression runs save precision and
recall alongside their existing metrics. Run details also show the four held-out
test metrics in a separate labeled group when test evaluation has completed.

## Clarification and critique

Source inspection confirms accuracy is already saved and shown in run details;
precision and recall are absent from the shared training scorer. F1 currently
averages per-class scores equally across the dataset's class IDs. Use that same
macro convention for precision and recall, with zero for undefined per-class
denominators. Accuracy remains the fraction of correct predictions. Label the
averaging convention in the UI/guide and display scores on the existing 0–1 scale.

Displaying only existing accuracy would be simpler but would not meet the request
for precision and recall. A metric selector adds interactions for just four values;
side-by-side columns make comparison immediate. Separate maxima for each summary
metric could describe different runs, so retain the existing F1 summary instead.
Use horizontal table scrolling and wrapping detail cards on narrow screens.

Approval of this plan confirms validation metrics as the primary table values,
macro averaging, separate test details, and no retroactive recomputation. There
are no additional unresolved source questions; these are proposed scope choices
for human review.

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | List and detail show all four validation metrics with clear labels. | Browser exercise with distinct values and a real worker run. |
| F2 | Functional | New runs and evaluated tuning winners save macro precision/recall for evaluated splits. | Independent expected-score assertions, training and final-evaluation tests. |
| F3 | Compatibility | Historical or incomplete runs show missing values as an em dash, preserving genuine zero values. | Browser exercise with legacy, zero, pending and missing values. |
| N1 | Reliability | Test labels never influence checkpoint/winner selection; artifacts remain hash-valid. | Existing selection-isolation and evaluation artifact regressions. |

## Constraints and scope

Supports both current classifier architectures. Preserve API response envelopes,
project scoping, idempotency, config hashes, checkpoint formats, selection metrics,
tuning objectives, serial execution, ownership and recovery. Metrics dictionaries
gain additive validation_precision/validation_recall and test_precision/test_recall
entries; no schema migration or new routes/configuration. Do not fabricate old
metrics, retrain old runs, or modify their saved records/artifacts. Existing test
evaluation gates remain unchanged. This improves the course C4/C9 classifier UI;
it does not claim new monitoring or AI acceptance.

## Design

Extend the shared scorer in [training.py](../../src/ml_pipeline_pro/training.py)
to compute accuracy and macro F1/precision/recall from one prediction pass. Update
epoch scoring, selected-checkpoint validation scoring, optional direct test scoring
and final tuning checkpoint evaluation consistently. Keep checkpoint selection
based only on its existing validation objective and first-best tie behavior.

Update [index.html](../../src/ml_pipeline_pro/dashboard/index.html),
[workspace.js](../../src/ml_pipeline_pro/dashboard/workspace.js) and responsive
styles as needed. Table order: F1, precision, recall, accuracy. Details distinguish
validation from test and keep selected epoch separate. Existing numeric formatting
must preserve zero and render missing/nonfinite values as unavailable.
Update the [dashboard guide](../guides/dashboard.md) and metric documentation in
the API reference to explain additive fields, macro averaging and legacy behavior.

## Acceptance and verification

Run targeted score/training/logistic/final-tuning tests while implementing. Use
known imbalanced binary and multiclass predictions, including never-predicted
classes, to distinguish macro averages from micro/weighted averages and verify
undefined denominators. Assert saved manifest metrics match returned metrics.
Retain existing assertions; additions establish the new requirements.

Before the application commit run `uv sync --locked --extra training`,
`uv run --locked --extra training ruff check .`,
`uv run --locked --extra training ruff format --check .`,
`uv run --locked --extra training pytest -m "not integration" --cov`, and
`uv pip check`. Run affected ordinary worker/training/tuning integration cases
with both `MLPP_RUN_INTEGRATION=1` and `MLPP_RUN_WORKER_INTEGRATION=1` using the
[verification guide](../guides/verification.md). Ownership/recovery mechanisms
are unchanged; run affected final-evaluation/artifact regressions and record any
service gaps explicitly. Exercise the browser with deterministic metric records
and an isolated real serial training run, checking narrow and desktop layouts,
legacy missing metrics and real zero values. Save evidence with revision and
commands. Validate documentation links and `git diff --check`.

## Risks and rollback

Older runs cannot supply precision/recall without new evaluation; show unavailable
and tell users a new run is needed. Macro values can differ substantially from
weighted scores on imbalanced data; label their meaning. Extra columns require
responsive inspection. Roll back code together without deleting records/files;
older code tolerates additional metric dictionary entries. No runtime service or
demo rebuild is included without separate authorization.

## Human review and approval

Pending. No implementation is authorized by this plan until Jacob approves its
written scope under the [development method](../project/development-methodology.md).

## Implementation outcome

Pending implementation and verification. Plan-only checks: local relative link
targets and `git diff --check`; no application or live-service acceptance claimed.
