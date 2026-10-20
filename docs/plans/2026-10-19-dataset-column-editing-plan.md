# Drop dataset columns in the dashboard

- Status: implemented and locally verified; independent review unavailable
- Date: 2026-10-19
- Source baseline: `e819960` on `person-a/conversation-foundation`
- Request: basic dataset manipulation, beginning with dropping columns
- Human clarification: Jacob selects **both new uploads and saved datasets**;
  new-version behavior is proposed below for review.
- Human reviewer/approval: Jacob, October 19; approves the written plan with
  "looks good" while this plan is open in the IDE.
- Independent review: seek separate publication/deletion-boundary review;
  reviewer availability unknown, and no independent review has occurred.

## Proposed behavior and purpose

Let users choose which input columns to keep before uploading a CSV and add
**Edit columns** to saved dataset cards. Show the retained and dropped inputs,
then **Save as new version**. Require an explicit unused version; retain the
dataset name. Existing datasets, runs and artifacts continue to use their original
contents. Saved edits preserve every row's order, target and split membership.

For prepared categorical datasets, show original names such as `BP`. Dropping
`BP` drops its complete group of encoded features. For already numeric datasets,
show their registered feature names. The target and split are protected, and at
least one input must remain. Restoring a saved omission starts from the original
version. This first slice implements column removal; row/value editing, renaming,
filtering and new transformations remain follow-ups.

## Clarification and critique

Source inspection establishes that [upload preparation](../../src/ml_pipeline_pro/dashboard/preparation.js)
already offers **Exclude column**, but only after a successful encoding preview.
An entirely missing or excessively expanding feature can prevent reaching that
control. The [server](../../src/ml_pipeline_pro/dataset_preparation.py) already
supports explicit exclusion. Saved cards in
[workspace.js](../../src/ml_pipeline_pro/dashboard/workspace.js) have no column
editor. Jacob explicitly requests both entry points on October 19.

Uploading a hand-edited copy would suffice technically, but requires external
editing and another upload. Merely changing a training form would leave the
dataset's saved feature definition ambiguous. Mutating a registered version
would break its hash and existing experiment provenance. Create a separate
dataset version and materialize its retained numeric columns instead.

Treat these remaining choices as explicit proposals for human review: immutable
new versions; whole-source-column removal for categorical inputs; no target or
split removal; no change to rows or encodings. No additional intent question
remains outside those reviewable choices.

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | Select columns before encoding preview; retain the existing encoding controls and prepared-upload mode. | Browser drops an entirely missing feature and a high-cardinality identifier before preview, then saves and trains; API verifies their exclusion. |
| F2 | Functional | Edit saved numeric or raw-prepared datasets without selecting a local file; preview omissions and save under a new explicit version. | Both browser journeys, cancel, list refresh and actual worker training from the new version. |
| F3 | Functional | Preserve retained values, row order, target IDs, split membership and fitted transformations exactly. | Compare complete parent/child rows and raw-row transformations; categorical removal drops every corresponding encoded feature. |
| F4 | Functional | Reject unknown/protected inputs, duplicate omissions, no-op edits and removing every feature; changed preview/settings cannot be saved. | Negative API and browser cases reach each intended validation; parent files/metadata remain unchanged. |
| N1 | Reliability | Keep scoped access, immutable hashes, matching replay and uncertain-save recovery; integrate with publication/deletion coordination. | Real MongoDB and shared-volume replay/race/failure cases; deleting either version preserves every surviving file reference. |
| N2 | Resources/usability | Reuse existing CSV, row, width, manifest and operation-time limits; accessible controls at both supported sizes. | Applicable exact-boundary checks, keyboard/browser evidence at 1440x900 and 1280x800, and human usefulness review. |

## Constraints and scope

Keep `/api/v1` contracts compatible, project scoping, correlation IDs, upload
opt-in, serial CPU execution, train-fitted preprocessing, validation selection,
test evaluation boundaries and tuning ownership/deadlines. No language-model
call or generated-code execution is needed for column selection. This improves
course C4/C9 usability without closing other outstanding
[course acceptance](../project/course-requirements.md) gaps.

The workspace contains uncommitted permanent-deletion work at the source baseline.
This planning change does not edit or commit that work. Before implementation,
reinspect its final contracts and coordinate edits to shared files. Column editing
must use the [approved deletion design](2026-10-19-permanent-deletion-plan.md)'s
publication lock and lifecycle gate, not add an uncoordinated writer.

## Design

### Upload selection

After the existing bounded local header read, show labeled keep/drop controls
before **Preview encoding**. Translate omitted raw inputs into the existing
`columns[name].treatment = "exclude"` settings. In advanced prepared-upload mode,
update the existing `feature_columns` selection. Protect the chosen target/split;
retain independent explicit exclusions when their roles change. File changes
reset selection. Selection changes invalidate review and disable saving until a
fresh preview. Excluded cells still obey existing structural/byte limits.

### Saved-version interface

Add project-scoped model-service endpoints, under the existing upload opt-in:

- `GET /api/v1/datasets/{id}/columns`: verified editable input descriptors,
  protected target/split names, encoded groups and a source snapshot digest.
- `POST /api/v1/datasets/{id}/columns/preview`: JSON `version`, `drop_columns`
  and `source_sha256`; return typed before/after descriptors, feature/split counts
  and `preview_sha256`, with no dataset registration.
- `POST /api/v1/datasets/{id}/columns`: the same JSON plus `reviewed_sha256`;
  publish/register the exact reviewed version and return the existing dataset
  response, 201 for creation or 200 for identical saved replay.

Use existing `Name`/bounded column types, forbid extra fields, and limit omission
lists to 128 unique names. Only currently active inputs are editable. Normalize
omission order while preserving the parent's retained feature order. The server
checks both preview hashes and file integrity; it never trusts browser headers.
An invalid selection returns correlated 422, missing/foreign records 404,
stale source/review or a conflicting name/version 409, and storage/dependency
failure 503. Existing authentication and disabled-capability behavior apply.

Use small column-edit schemas/API/helpers beside preparation modules. Verify the
parent's canonical hash and preparation source/manifest hashes before deriving
anything. For saved numeric data, copy only retained registered features plus
target/split into a new canonical CSV. For raw-prepared data, use the verified
manifest to resolve original inputs into complete encoded groups, then project
the saved canonical CSV. Do not split again, refit, rename retained features or
infer new categories. Verify the derived CSV through the ordinary loader.

Prepared children retain their original raw-source file reference and get a new
self-contained manifest with frozen retained transforms, unchanged label map and
split digest, and explicit selection provenance: parent ID/content/recipe hashes
and omitted source names. Use a distinct `format_version = 2` and
`implementation = "classification-csv-selection-v1"`; retain v1 read support.
Compute its recipe hash from the frozen transformation and selection contract;
bind the preview to source, canonical, manifest, selection and destination
identity. Extend preparation verification/transformation for v2 and reject
unsupported or inconsistent formats. No runtime parent lookup or parent file
other than the directly retained raw-source reference is required by a child.
Retain provenance as hashes/IDs, not additional storage references or embedded
raw data. Numeric children need no raw-preparation recipe.

### Publication, lifecycle and browser recovery

Reuse immutable content-addressed publication, identity replay and cancellation
ownership. Recheck the source under the project publication lock; fence child
registration with the same lifecycle generation as other dataset writes.
Resolve an existing exact destination replay before requiring the parent to
still exist; this recovers a committed save whose parent was subsequently
deleted. Changed request/destination reuse conflicts. Retain sufficient operation
provenance to verify this replay for numeric children as well as prepared children;
use an optional typed dataset selection field with immutable parent hashes and
normalized omissions. Old records require no migration. Update repository/fake
contracts and deletion inventory if needed; no new parent cascade is introduced.

Do not remove published files after uncertain database acknowledgement. Only
private staging files are request-owned cleanup. A child directly references
every file needed for training; deleting its parent must not erase shared raw
source files. Coordinate the new writer with deletion from preview through commit.

Use the existing dashboard styling and review dialog. Show parent/version,
omissions, remaining feature count and unchanged split counts; require a version
entry, then explicit save. Disable duplicate clicks. An uncertain save retains
the original request and offers same-request check/retry. Cancel publishes
nothing. Project changes and late responses cannot select or save another
project's records. Refresh lists and select the new version only on confirmed
success. Document new routes and behavior in root README, API reference and the
dashboard guide; no new dependency or configuration default is proposed.

## Acceptance and verification

Add meaningful projection/API tests for F1-F4, v1/v2 compatibility, repeated
selection, non-default label maps, fixed custom splits and changed/missing parent
files. Compare complete retained matrices and row membership; equal aggregate
counts alone cannot prove F3. Train both child types and verify checkpoint
feature order, raw transforms and artifact hashes. Retain original parent hashes
and successful replay assertions. No existing gate/assertion is weakened.

Exercise N1 with real MongoDB/volumes: identical simultaneous saves; lost insert
acknowledgement; cancellation during owned file work; parent deletion on either
side of publication; child replay after parent deletion; deletion of parent and
child independently while another version survives. Use disposable test projects.
Seek separate review of publication, lifecycle and hash/size boundaries; disclose
unavailable review rather than labeling self-review independent.

Run the [fast commands](../../AGENTS.md#verification-commands), `uv build`, ordinary
integration with both `MLPP_RUN_INTEGRATION=1` and
`MLPP_RUN_WORKER_INTEGRATION=1`, then isolated serial recovery with
`MLPP_RUN_RECOVERY_INTEGRATION=1` per the
[verification guide](../guides/verification.md#run-the-suite). Record unavailable
services/skipped selected cases as gaps. Save source/dependency/image identifiers,
raw commands/results and browser evidence. There is no performance claim.

## Risks and rollback

Column selection can remove useful predictors; provide explicit review and keep
the original version. A dropped input remains in retained original/raw-source
files for provenance; this is feature editing, not permanent data erasure.
Mixed older workers reject v2 recipes: deploy matching domain services/workers
together after work drains, including consumers of the optional selection field.
For rollback, disable creation controls but retain v2 reading and
lifecycle guards while selected datasets/runs exist; avoid rolling workers back
to a version that cannot read them. Unregister/delete disposable test children
through the reviewed deletion workflow. Never rewrite original files.

## Human review and approval

October 19: Jacob requests column removal and confirms **both new uploads and
saved datasets**. After the plan was committed and pushed as `270ef7d`, Jacob
replies "looks good" with this plan open in the IDE. This approves implementation
of the written scope, including new-version behavior, protected target/split,
whole categorical groups, v2 provenance, API, publication/deletion coordination
and acceptance checks, under [AGENTS.md](../../AGENTS.md) and the
[development method](../project/development-methodology.md).

## Implementation outcome

- Scope: approved upload/saved-column editing, immutable projection, v2 recipe
  verification, typed provenance/index/replay and existing lifecycle coordination.
  New JSON routes reuse the existing 64 KiB request cap. No feature dependency added.
  Shared deletion/publication foundation was separately committed and pushed as
  `04c55b5` before the column-editing commit; its source matches the tested tree.
- Environment: Windows PowerShell, CPython 3.11.5, uv 0.12.23; source/dependency/image
  hashes and exact execution context are retained in the
  [evidence record](../evidence/2026-10-19-dataset-columns/README.md).
- Checks: locked sync, Ruff lint/format, installed dependency compatibility and
  package build pass. Full fast suite: 740 passed; ordinary: 104 passed with both
  flags; isolated recovery: ten passed with unchanged assertions and separate
  ports/image/control namespace. No selected skips. Build/cache warning and the
  initial browser-harness reconnect failure remain separately documented.
- Acceptance: F1-F4 and N1/N2 assertions pass. Chrome covers both sizes, whole
  categorical groups, keyboard access, cancel, stale preview, duplicate click,
  uncertain-save reload/reconnect, project switching and five actual serial worker
  runs, including training after parent/child deletion on the shared volume.
  Complete retained-cell/frozen-transform comparisons include repeated v2 edits,
  custom mappings/label IDs/splits, missing/corrupt files and boundary rejection.
- Test changes: new projection/API, real MongoDB/deletion cases and an opt-in
  browser script prove the requirements; existing assertions/gates are not weakened.
- Deployment: existing local Compose services/workers updated together after idle
  checks; readiness and final keyboard behavior pass on port 8000. User data/volumes
  retained. No new AI inference or external model/API is required by the feature.
- Review: Jacob's design approval is recorded above. Independent review unavailable;
  implementing-assistant inspection is self-review. Completed-control usefulness
  review remains pending. No material design deviation or course-gap closure claimed.
- Durable finding: [projection and parentless replay](../memory/dataset-column-projection.md).
- Completion commit/push: report exact commit and remote outcome in the handoff.
