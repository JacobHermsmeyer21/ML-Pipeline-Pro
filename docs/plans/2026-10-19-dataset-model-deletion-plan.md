# Delete datasets and classifier models from the workspace

- Status: awaiting review; implementation pending
- Date: 2026-10-19
- Source baseline: `9b862d8` on `person-a/conversation-foundation`
- Request: Jacob asks for a way to delete datasets and models.
- Human reviewer/approval: pending
- Independent review: seek a separate reviewer for deletion/submission ordering;
  reviewer availability is unknown, and no independent review has occurred.

## Proposed behavior and purpose

Add **Delete dataset** to dataset cards and a **Manage models** dialog beside the
training model selector, with a **Delete model** action for each named classifier.
Require a confirmation showing the name, dataset version where applicable, and
effect. Remove the confirmed item from normal lists and training choices, retain
its history and files, and prevent new training/tuning submissions using it.
Already accepted jobs finish normally. Saved results, artifact downloads,
registered versions and monitoring remain available.

This is logical deletion: it does not reclaim disk space. State that explicitly
in the confirmation and documentation. It adds lifecycle controls to the local
dashboard and course model-management work; it does not close unrelated course
acceptance gaps or delete Ollama's pre-trained conversation model.

## Clarification and critique

Source inspection establishes that datasets/models have no deletion route or
browser control. Experiments and tuning jobs retain their IDs; monitoring refers
to registered model versions. Uploaded and prepared datasets can share immutable
content-addressed files. Deleting those files can strand other records, including
an insert whose acknowledgement was lost. See the
[publication finding](../memory/dataset-upload-publication.md) and
[artifact preservation contract](../memory/evaluation-artifacts.md).

An intent question was presented about preserving history, blocking deletion of
used items, or permanently erasing related history/files. Pending a different
answer, this plan proposes preserving history/files. Human review must confirm
that interpretation, that “models” means workspace classifiers, and that retained
names remain reserved. Restoration, permanent erasure, disk reclamation, deleting
individual model versions, and deleting runs are outside this proposed slice.

Blocking deletion of any used item would be smaller but would leave the workspace
cluttered after experiments. Cascading permanent deletion requires a separate
retention and shared-file cleanup design, including uncertain publication and
active-worker recovery. Logical deletion meets workspace cleanup without that
additional destructive scope. The tradeoff is retained disk usage and identities.

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | Delete a selected dataset version or named classifier after explicit confirmation; cancel changes nothing. | Browser walkthrough for each type, cancel/confirm, refresh and empty states. |
| F2 | Functional | Deleted items disappear from ordinary lists and training choices; stale IDs cannot start new standalone experiments or tuning jobs. | API/list tests and real MongoDB deletion-versus-submission ordering tests. |
| F3 | Functional | Preserve existing jobs, idempotent submission replay, historical records, model versions, monitoring and hash-valid artifact downloads. | Delete after acceptance and during queued/running work, finish/recover it, replay its original key and inspect results. |
| F4 | Functional | Enforce project/key access and correlated errors; repeated deletion has the same result. | Own/foreign/missing ID, missing/invalid access, repeated request and lost-response retry checks. |
| N1 | Reliability | Concurrent deletion and new submission cannot accept work referencing an item already deleted at admission. | Controlled real-MongoDB interleavings at the transaction boundary, including separate model/tuning apps. |
| N2 | Compatibility | Existing active records need no backfill; preserve files, identity uniqueness and serial CPU execution. | Legacy record decode, shared-file/hash checks, unchanged uniqueness and full regression gates. |

## Constraints and scope

Preserve `/api/v1` project scoping, correlation/error envelopes, submission keys,
exact agent decisions, validation-only selection, training-fitted preprocessing,
tuning-parent ownership, reservations, original deadlines and training artifacts.
Deletion is a direct user action; add no agent deletion tool or automatic cascade.
No dependency or configuration changes are planned. Never exercise deletion on
the user's existing records during verification; use disposable scoped fixtures.

## Design

### API and persistence

Add project-scoped `DELETE /api/v1/datasets/{dataset_id}` and
`DELETE /api/v1/models/{model_id}` to the existing model-management router. Return
200 with the corresponding record, including a persisted deletion timestamp.
Repeat deletion returns that same tombstone without changing its timestamp.
Missing or foreign IDs use the existing type-specific 404. Database failures use
the existing correlated 503; an uncertain client retries the same resource ID.

Add optional `deleted_at` to `DatasetRecord` and `ModelRecord`, defaulting to null
for old records. Ordinary dataset/model lists exclude tombstones before sorting
and pagination. Add `include_deleted=false` to those list routes for history-aware
clients. Direct scoped GET continues to return deleted records and their timestamp
so saved references remain inspectable. Specialized lifecycle repositories keep
internal admission revision counters out of public schemas and decoded records.
Retain existing unique indexes, reserving dataset name/version and model name.
Registration/upload/preparation must never reactivate an existing tombstone;
identity conflicts return correlated 409 with guidance to choose a new identity.

New experiment/tuning admission checks both references and inserts the job in one
MongoDB transaction. Within that transaction, conditionally **write** both scoped,
non-deleted reference documents by incrementing an internal revision. A read-only
check is insufficient under snapshot isolation; use the same reasoning documented
for [parent fencing](../memory/tuning-parent-fence.md). Deletion atomically writes
the same reference document, giving a defined order against admission. A job
committed before deletion is accepted and may finish; deletion committed first
causes new admission to return 409 `dataset_deleted` or `model_deleted`.

Preserve matching idempotency replay before checking new-admission eligibility,
including dispatch recovery after deletion. Allocate record IDs/hashes outside
retryable callbacks; keep callbacks database-only and publish only after commit.
Handle duplicate submission races with the existing scoped reread/conflict rules.
Worker and tuning-child reads continue to resolve tombstones. Children of an
already admitted tuning parent continue under its existing ownership transaction;
do not apply fresh-job admission rules to those children. Registering a new model
version after deletion returns 409 `model_deleted`, with its insertion fenced
against model deletion; reading existing versions remains supported.

### Browser and coupled updates

Use the existing review dialog for deletion confirmation and accessible text
buttons with a destructive-action style. Disable repeated clicks while pending.
On success refresh records, clear the deleted selection and any stale training
review, and refresh agent context. Keep project-generation guards: late responses
and open confirmations must not mutate a different project. Unknown transport
outcomes offer an explicit check/retry for the same ID; do not report success
before a saved tombstone is confirmed.

Load history-aware records where needed to keep names on saved runs and offer
existing registered versions in Monitoring. Filter active options separately.
Label deleted historical references, and disable new version registration for
deleted models. Keep all untrusted names rendered as text. Document endpoints,
retained files/names and retry behavior in the root README, API reference and
dashboard guide. Update repository contracts, memory fakes, fixtures, and any
affected tool response/provenance assertions for the additive timestamp field.

## Acceptance and verification

Implement only after human plan approval, in checked slices: lifecycle storage
and routes; transactional admission/replay; browser controls; retained evidence.
Add meaningful API/storage tests for F1-F4 and N1-N2, without relaxing existing
assertions. Prove list filtering occurs before pagination and legacy records
remain active. Test shared canonical/source/manifest files retain their hashes
after deletion, and upload/preparation retries cannot resurrect tombstones.

Use controlled real-MongoDB interleavings for delete-before-admission,
admission-before-delete and transaction retry, for both reference types and both
standalone training and tuning. Include version-registration ordering. Check an
accepted tuning job can create children and finish after deletion, with original
deadlines/reservations and verified artifacts. Browser evidence covers both
actions, cancellation, double click, refresh, a lost response, project switching,
history labels and retained monitoring/version selection.

Run every [fast gate](../../AGENTS.md#verification-commands), `uv build` for the
packaged dashboard change, and the complete ordinary integration suite with both
`MLPP_RUN_INTEGRATION=1` and `MLPP_RUN_WORKER_INTEGRATION=1`. Run the isolated
recovery suite serially with `MLPP_RUN_RECOVERY_INTEGRATION=1`, separately, following
the [verification guide](../guides/verification.md). Missing services or selected
skips remain gaps. Retain commands, source/image IDs, outcomes and raw evidence.
Seek independent review of transaction ordering and replay; disclose unavailable
review rather than describe implementing-assistant self-review as independent.

## Risks and rollback

The main risks are admission races, breaking historical lookup, accidental
resurrection and misleading users about disk reclamation. Confirm the lifecycle
meaning before implementation. Deploy matching model/tuning APIs and workers
together after draining current work; older strict decoders may reject new stored
fields, and older submission routes bypass deletion admission. Roll back controls
and routes while retaining compatible record readers and admission checks; do not
restore older writers or remove tombstones as routine rollback. Retain all files,
metadata, artifacts and existing identities.

## Human review and approval

Pending Jacob's review of this concrete plan, especially history-preserving
deletion, already accepted jobs finishing, retained identities, and exclusion of
permanent erasure/Ollama model removal. The feature request authorizes preparation
of the plan; it is not recorded as approval of these new lifecycle contracts.

## Implementation outcome

- Source revision and changed scope: planning only, baseline above.
- Commands/environment: repository/source inspection and `git fetch origin`;
  Windows PowerShell. Branch matches its upstream; `origin/main` is an ancestor.
- Results: application implementation and acceptance checks pending approval.
- Raw evidence: no application execution or performance claims for this plan.
- Test changes: none.
- Review: human approval pending; no independent review performed.
- Deviations and durable findings: none.
- Completion commit and push: recorded in the task handoff after plan validation.
