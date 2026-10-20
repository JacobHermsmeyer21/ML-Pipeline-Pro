# Prepare raw classification CSVs inside the dashboard

- Status: approved for implementation, including editable encoding review
- Date: 2026-10-19
- Source baseline: `f152132f8495290e1c05c5636e934f51a11be8de`, `person-a/conversation-foundation`
- Request: minimize external preprocessing; encode categories and create training,
  validation and test splits without requiring a split column
- Human reviewer/implementation approval: Jacob, October 19, with encoding-review addition below
- Independent review: seek a separate reviewer for publication/replay and size/split
  arithmetic; availability unconfirmed; implementing-assistant review is self-review

## Proposed behavior and purpose

Upload an ordinary CSV, select the prediction target, review inferred column roles
and preparation settings, then save a training-ready dataset. Default to **70%
training / 15% validation / 15% test**, stratified by class, with seed **42**. The
normal workflow has no split-column input. Keep ratios, seed and an optional
existing-split mode under advanced settings.

The primary demo starts with Jacob's **original, unmodified `drug200.csv`**. Select
`Drug` as the target; the app handles `Sex`, `BP`, `Cholesterol`, string target
labels and split creation. No script, spreadsheet edit or prepared-copy upload
is an acceptable substitute. Keep the approved dashboard styling and agent panel.

## Clarification and critique

Jacob approved the proposed classification scope and defaults, adding: "the demo
should be able to handle that dataset exactly how it is now and process it for
training." This approves these requirements, before review of this written design.
No further product-intent question is outstanding for this proposed scope.

Source facts: the [loader](../../src/ml_pipeline_pro/datasets.py) requires numeric
features, contiguous integer labels and explicit splits. The
[trainer](../../src/ml_pipeline_pro/training.py) already fits normalization on
training rows and selects checkpoints by validation metrics. The
[previous drug200 run](../evidence/2026-10-19-drug200-demo/README.md) used an external
prepared copy; that workaround does not meet this request.

Read-only inspection of the current Downloads original on October 19 confirms
200 rows, headers `Age, Sex, BP, Cholesterol, Na_to_K, Drug`, no missing cells and
SHA-256 `10caebf3b055e149ef1e7494042031e510b47ba644f3c304bbb86c428fe89b66`.
Class counts are DrugY=91, drugA=23, drugB=16, drugC=16 and drugX=54. This is input
inspection, not evidence that the proposed importer works.

Automatic guesses can confuse category codes, identifiers and ordered categories.
Show editable numeric/categorical/excluded roles; never silently remove columns or
invent an ordering. Random stratification is suitable for independent rows, but
does not prevent leakage between repeated people or time-dependent observations.
Explain that limit and retain existing-split mode; group/time splitting is a
recommended follow-up. Do not claim automatic leakage detection.

A browser-only converter would require less backend work, but would leave API,
worker and later inference without authoritative preparation provenance. Use a
server preparation boundary producing the numeric CSV the current worker already
understands. Avoid replacing the trainer or adding a separate preparation service.
Use maintained splitting/encoding utilities rather than bespoke split arithmetic.

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | Original drug200 uploads and trains through actual dashboard controls with only target selection and review. | Original hash unchanged; raw upload hash matches; real worker succeeds and records validation metrics. |
| F2 | Functional | Automatic class-stratified 70/15/15 splits, seed 42; editable advanced ratios/seed and optional existing splits. | Original 200-row demo gives 140 train / 30 validation / 30 test; row membership is disjoint and exhaustive; same input/settings reproduce it. |
| F3 | Functional | Infer editable feature roles; one-hot encode categorical features and map string targets to readable class IDs. | Drug200 has two numeric and three categorical inputs; training-derived vocabularies and reversible label mapping persist. Unknown feature categories do not change feature width. |
| F4 | Functional | Preview missingness and class balance; offer training-fitted missing-feature handling. | Opt-in numeric median / categorical mode imputation works; missing targets and wholly missing training features fail with actionable errors. |
| F5 | Functional | Save immutable preparation provenance and reuse it for training, tuning, evaluation and raw-row transformation. | Recipe/source/output hashes verify; checkpoint retains maps/order; saved transform reproduces prepared model inputs and readable labels. |
| F6 | Functional | Review automatic encoding before saving and change feature treatment, category mappings or target class IDs. | Browser shows training-derived vocabularies and generated columns; user changes BP to an explicit numeric mapping and reorders drug class IDs, refreshes preview, then trains with those exact settings. Stale or incomplete mappings cannot be saved. |
| N1 | Reliability | Keep project access, exact replay/conflicts, artifact integrity, serial execution and existing prepared datasets working. | API, actual-volume replay/race and worker/recovery checks; unchanged legacy fixture trains and evaluates. |
| N2 | Resources | Bound reception, parsing, expansion and output; do not accept an upload that cannot become a supported dataset. | Exact-limit/limit+1 tests reach each guard; no partial registration, unbounded matrix allocation or raw-value error logging. |
| N3 | Usability | No external editing or split-column entry in the main path; preview and errors are usable at both approved desktop sizes. | Browser walkthrough, keyboard checks and screenshots at 1440x900 and 1280x800; human usefulness review. |

## Constraints and scope

First version: UTF-8 CSV classification, 2-64 classes, existing row/value limits
and at most 128 numeric features after encoding. Regression, free-text/date feature
engineering, learned ordinal/target encoding, automatic balancing, deduplication and
group/time splitting are follow-ups, not implemented scope. Imputation defaults to
**reject missing values** until the user explicitly selects the offered strategy.

Split before fitting category vocabularies, label maps, imputation or normalization.
Use validation metrics for checkpoint/tuning selection and test metrics only after
selection. Reuse the current trainer's normalization rather than normalize twice.
Stratification uses class labels to allocate rows, not to select a model. Fix row
membership per dataset version, independently of each experiment's training seed.

Preserve tuning ownership/deadlines and artifact references, existing registration
and upload defaults, opt-in uploads, secrets handling and local service boundaries.
This supports course C4/C5/C9 usability; it does not close other outstanding course
acceptance or independent-review gaps in the [requirements](../project/course-requirements.md).

## Design

### Import and transformation

Add a bounded CSV preparation module with a shared preview/prepare implementation.
Use Python CSV parsing and locked scikit-learn utilities for stratified splitting,
one-hot encoding and imputation. Add scikit-learn to the training extra and the
multipart parser to runtime dependencies; update `uv.lock` deliberately. API images
already install the training extra. Missing preparation dependencies return a
correlated 503, without affecting existing routes.

The user explicitly selects a target from the headers and confirms feature roles.
Infer numeric versus categorical roles from training rows; retain overrides for
numeric category codes. Support distinct nonempty source headers up to 128 UTF-8
bytes, including spaces, using stable generated internal aliases that satisfy
existing numeric dataset column-name constraints. Render source names as text.
Never include target or existing-split columns in model features.

Before registration, show each feature's inferred treatment, training-derived
category vocabulary, generated output columns and target-label-to-ID mapping.
Allow numeric, one-hot, explicitly supplied numeric category mapping, or exclusion;
custom numeric mappings must cover the training vocabulary with finite bounded
values and declare an unknown-category fallback. Explain that numeric mappings
impose distances. Target IDs may be reordered but must remain a bijection onto
`0..classes-1`. Do not learn a category ordering or target statistics automatically.
Changing any setting invalidates review. Require a refreshed preview and bind
registration to its hash so the saved recipe is the one the user reviewed.

For automatic splits, reserve 15% test first, then take 15/85 of the remainder for
validation, using stratified shuffling and seed 42 for both operations. Generalize
that fraction to the requested positive integer percentages summing to 100.
Persist the utility version and actual counts; rounding means small datasets may
not match percentages exactly. Reject impossible allocations and any resulting
split missing a class; offer more rows, different ratios or existing splits.
Do not silently use an unstratified fallback, duplicate rows or remove classes.

Fit ordered category vocabularies and contiguous target IDs on training rows only;
reject unseen validation/test target classes. One-hot categories have no imposed
order or learned target statistics. Use a fixed all-zero representation for unseen
feature categories, with a visible count/warning; never expand from holdout data.
Opt-in imputation learns medians/modes on training rows only. Preserve original
category spelling/case and label text. The source file remains unchanged.

The preview reports source roles, row/class counts, missingness, actual split counts
and encoded width, plus warnings for constant columns and likely identifiers/high
cardinality. Test metrics are never calculated during preview. Changing settings
invalidates the displayed preparation preview until it is recalculated.

### API, limits and persistence

Add `POST /api/v1/datasets/preview` and `POST /api/v1/datasets/prepare`, authenticated
and gated by the existing upload setting. Both accept multipart `file` (CSV) and
`settings` (JSON). Preview is stateless and cleans its staging file; prepare
revalidates the file/settings and returns the saved `DatasetRecord`. This avoids
durable draft sessions and a new job state machine. The browser keeps the original
file and exact settings for an explicit same-request retry after uncertainty.

Authenticate before multipart parsing. Bound raw CSV bytes to the smaller of
10,000,000 and `MLPP_DATASET_MAX_BYTES`; bound settings to 32 KiB, multipart
overhead to 32 KiB and the whole body to the raw cap plus 64 KiB. Accept only the
two expected parts. Keep the existing 30-second reception deadline; add a
30-second cooperative preparation deadline checked during parsing/transformation.
Use a 90-second browser bound for these routes. Do not change chat/worker budgets.
Mirror the new outer guards in the gateway with correlated errors.

Precheck expanded width and matrix size (at most 64 MiB of float32 values) before
allocating; bound canonical CSV to `MLPP_DATASET_MAX_BYTES` during serialization
and preparation manifest to 256 KiB. Check configured row/value bounds as well.
Reject excessive expansion with 422 explaining which column needs exclusion or a
different role; large-vocabulary grouping is deferred. Preserve correlated 408,
413, 415, 422, 409 and 503 error behavior, without raw rows, cell values or paths.

Publish original CSV, canonical numeric CSV and a versioned preparation JSON
manifest as immutable, content-addressed files under the same project uploads
directory, using [atomic create-if-absent publication](../memory/dataset-upload-publication.md).
The canonical CSV contains generated feature/target/split aliases; its hash remains
the dataset's existing `sha256`. The manifest records source/output hashes, selected
columns/types, exact settings, implementation/dependency versions, fitted maps and
imputation, encoded feature order and split membership digest. The canonical file
persists membership itself, so retries and tuning cannot reshuffle it.

Add optional typed preparation references to `DatasetRecord` for original and
manifest URI/hash/size plus recipe fingerprint; old records remain readable.
Update repository contracts, fixtures and response/tool documentation together.
Same project/name/version plus identical source/recipe/output returns the saved
record (200); changed content or settings conflicts (409), even if output bytes
happen to match. Resolve insert races by scoped reread. Files publish before the
single dataset insert; uncertain inserts retain published files. No new collection
or automatic orphan cleanup is needed.

Workers verify preparation references and embed the versioned fitted transform in
new checkpoints/manifests alongside existing normalization. A shared raw-row
transform reproduces numeric feature order and decodes target labels. Legacy
checkpoints remain numeric-only. Final evaluation preserves original training
artifacts under the [existing contract](../memory/evaluation-artifacts.md).

Update dashboard upload controls/config, guide, README endpoints/API reference,
dependency lock and any affected package/image fixtures. Expose actual encoded
width and preparation metadata without changing agent action permissions or
claiming new AI-generated preprocessing. Keep the existing prepared-upload path
available under advanced controls.

## Acceptance and verification

Implement in small checked slices: preparation rules; API/publication/provenance;
worker/checkpoint compatibility; browser workflow; original-file demo and evidence.
No implementation begins until this plan is reviewed.

Run all [fast gates](../../AGENTS.md#verification-commands) plus `uv build` for
dependency/package changes. Cover disjoint/exhaustive deterministic splits,
unseen categories/targets, rare classes, invalid ratios, missing/constant values,
source header aliases, output width and raw/encoded/envelope/manifest limits.
Use holdout-only extreme values/categories to prove training-fitted transforms;
changing only holdout features must not alter fitted parameters. Keep legacy
numeric training/final-evaluation and artifact-integrity assertions intact.

Run the complete ordinary suite with both `MLPP_RUN_INTEGRATION=1` and
`MLPP_RUN_WORKER_INTEGRATION=1`, including real-volume publication/replay/races,
project scoping, ambiguous insert and prepared-upload-to-worker cases. Run the
serial isolated suite separately with `MLPP_RUN_RECOVERY_INTEGRATION=1` after
worker/image changes, following the [verification guide](../guides/verification.md).
Missing services or selected skips remain gaps, never passes.

Browser acceptance selects the current original Downloads `drug200.csv`, confirms
its recorded source hash, chooses `Drug`, previews and prepares without entering a
split column, then completes real serial training, validation comparison, verified
artifact download and version registration. Prove 140/30/30 counts and every class
in every split, readable labels, exact replay and refresh. Recheck the source hash
afterwards. Retain screenshots, safe API outcomes, source/image/dependency IDs and
raw failures. Do not require an accuracy threshold from this one educational split.
Regression-test existing agent decisions and monitoring on the prepared dataset.
Seek separate boundary/arithmetic review; disclose unavailable review explicitly.

## Risks and rollback

Primary risks are holdout leakage, category expansion, inferred identifier roles,
multipart reception bounds and loss of preparation provenance. Negative tests
must reach those boundaries. Document random-split limitations for grouped/time
data. This plan does not promise general automatic data cleaning.

Deploy matching API/worker images together after current work drains. Canonical
numeric CSVs preserve the current loader boundary, but older record readers may
ignore preparation references and lose provenance. Roll back UI/routes only while
preserving metadata/files/mounts and a compatible worker for prepared records.
Never delete original uploads, canonical files, manifests or training artifacts.

## Human review and approval

October 19, Jacob approved classification scope, 70/15/15 defaults and advanced
ratios/seed/existing splits, explicitly requiring the original unprocessed drug200
for the demo. The complete design, dependency additions, preparation metadata,
API/limits, imputation policy and acceptance criteria above await review. This
record does not extend the earlier dashboard approval to new public contracts.

Jacob subsequently reviewed this plan and said: "ok plan looks good, only thing
is i want to be able to review the automatic encoding and change it if i please".
This approves implementation of the full plan with the F6 review/edit requirement.
The implementation will expose editable feature treatments, explicit category
numeric mappings and target class IDs, then require a refreshed preview before
saving. This addition is requested and approved by that same message; no further
approval is required for these controls. All original-data and verification
requirements remain in force.

## Implementation outcome

Outstanding; this change prepares the review document only. No categorical
importer, automatic splitter or new dataset preparation acceptance is claimed.
Planning validation: eight local links/anchors resolve, template sections and
whitespace checks pass, and the original CSV summary/hash was inspected read-only
with the existing virtual environment's Python (`csv`/`hashlib`). Application tests
are not run for this documentation-only change; implementation gates remain above.
Fresh fetch shows no incoming upstream or `origin/main` commits at this baseline.

Design references checked October 19: scikit-learn's
[training-only preprocessing guidance](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage),
[one-hot encoder](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.OneHotEncoder.html)
and [split-selection guidance](https://scikit-learn.org/stable/modules/cross_validation.html).
These are design sources, not evidence of this application's execution.
