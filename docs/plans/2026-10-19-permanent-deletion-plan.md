# Permanently delete datasets and classifier models

- Status: awaiting revised review; implementation pending
- Date: 2026-10-19
- Source baseline: `486c861` on `person-a/conversation-foundation`
- Request: dataset/model deletion. Jacob explicitly selects: "Permanently erase
  it and its related history and files."
- Human decisions: permanent erasure, blocking active jobs and preserving agent
  conversations/drafts confirmed; full design approval remains pending.
- Supersedes: the [history-preserving proposal](2026-10-19-dataset-model-deletion-plan.md).
- Independent review: seek separate transaction, cleanup and worker-boundary
  review; availability unknown, and no independent review has occurred.

## Proposed behavior and purpose

Add **Delete dataset** to dataset cards and **Manage models** beside the training
model selector, with **Delete model** for each classifier. Show the name/version
and exact counts of affected runs, tuning jobs, registered versions and files.
Require **Permanently delete** confirmation. Cancel changes nothing. Remove the
selected record, its dependent training history and owned files. Names become
reusable after completed cleanup, with new IDs.

| Target | Erase | Preserve |
| --- | --- | --- |
| Dataset version | Its experiments, tuning jobs/trials, versions derived from those experiments, associated monitoring observations, checkpoint directories and exclusively used managed dataset files. | Model definitions, other datasets and their runs/files. |
| Classifier model | Definition, all its experiments, tuning jobs/trials, registered versions, observations and checkpoint directories. | Source datasets and other models/runs/files. |

Dataset files include uploaded originals, prepared CSVs and preparation manifests
under `uploads/<project>/`. Keep a shared file if any surviving dataset references
it. Ordinary registered files outside this app-owned subtree are operator inputs:
unregister them and report them as unmanaged, without deleting repository fixtures
or the user's original files. This feature targets workspace classifiers; the
installed Ollama agent remains separate.

## Clarification and critique

The source lacks deletion routes/controls. Runs reference datasets/models, versions
reference runs, and observations reference versions. Uploads/preparations share
immutable content-addressed files, including after uncertain inserts. These links
require a scoped cascade and coordinated cleanup; see the
[publication finding](../memory/dataset-upload-publication.md),
[artifact contract](../memory/evaluation-artifacts.md) and
[ownership finding](../memory/tuning-parent-fence.md).

Jacob confirms both intent choices on October 19: **block deletion until related
jobs finish** and **keep conversations and drafts; erase training history and
files**. Deletion does not cancel jobs or erase saved agent messages/Python drafts.
Chats can retain copied facts/code after underlying training records disappear.
These resolve the presented intent questions; full design approval remains pending.

Logical deletion was simpler and reversible, but Jacob selected permanent erasure.
Refusing active jobs avoids adding standalone cancellation to this slice. Shared
and unmanaged inputs cannot safely be erased with one record. Erasure here covers
application records/files, without forensic disk wiping or removal of downloads,
backups, saved evidence, exports or previously scraped Prometheus history. Explain
these boundaries in the preview/guide rather than promising global data erasure.

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | Preview and confirm the exact cascade; changed dependencies require a fresh review. | Both browser journeys, cancellation, exact counts and stale-preview checks. |
| F2 | Functional | Erase the scoped cascade and exclusively owned files; retain unrelated/shared/unmanaged data. | Real MongoDB/volume assertions and hash-valid surviving artifacts. |
| F3 | Functional | Refuse queued/running/cancelling affected jobs without implicitly cancelling them. | Every nonterminal status, expired leases and actual worker boundaries; rejection changes no domain data. |
| F4 | Functional | Recover a lost response and resume interrupted cleanup using the original operation; success means complete cleanup. | Kill/fail each durable boundary, retry and verify one completed result. |
| N1 | Reliability | Admission, publication, stale writers and old submission retries cannot race erasure into dangling records or resurrected artifacts. | Controlled real-service transaction/process interleavings and shared-volume lock checks. |
| N2 | Compatibility | Preserve scoped access, correlation IDs, surviving schemas/idempotency, ownership/deadlines and serial CPU execution. | Complete regression gates and explicit survivor assertions. |

## Constraints and scope

This extends course model management and the local dashboard; it closes no other
outstanding course requirement. Confirmed erasure supersedes retention only for
its targets. Surviving work preserves validation-only selection, train-fitted
preprocessing, artifact hashes and tuning-parent transactions. Exclude agent
deletion tools, global orphan cleanup, project deletion, restoration, standalone
cancellation and installed-language-model removal. Use disposable test projects;
never exercise deletion on existing user records during verification.

## Design

### API and durable cleanup

Add `GET /api/v1/datasets/{id}/deletion-preview` and the equivalent model route.
Return typed dependency/file counts, active-job blockers and a fingerprint of the
exact affected IDs/revisions; count beyond browser pagination. Expose no raw rows,
secrets or absolute paths. Add `DELETE /api/v1/datasets/{id}` and
`DELETE /api/v1/models/{id}`, requiring `Idempotency-Key` and that fingerprint.
Return a typed 200 completion receipt after successful cleanup. Add scoped
`GET /api/v1/deletions/{operation_id}` for saved progress/results.

Use correlated errors: 403 access, type-specific 404 missing/foreign target, 409
`deletion_preview_stale`, `deletion_blocked` or `deletion_in_progress`, and 503
storage/cleanup failure. An uncertain result includes a known operation ID when
available and an explicit same-operation retry. Never imply partial cleanup is
success. Erased resource GETs return 404; affected reads during incomplete cleanup
return `deletion_in_progress`. Unrelated reads stay available.

Persist a journal before destructive work, with
`preparing -> cleaning -> complete` states and paged item/file entries rather
than an unbounded document. Atomically acquire a project lifecycle gate, check
active jobs and validate the preview before capture. Rejection is non-destructive.
The gate prevents new dependent mutations while cleanup is incomplete. Same key
and arguments resume the original manifest; changed arguments conflict. Missing
owned files are already-cleaned success; I/O failures retain resumable intent.
Remove files, remove scoped domain metadata, then finalize the receipt and reopen
admission. Detailed journal entries are scrubbed on completion; retain only
minimal operation/submission receipts, counts and timestamps, without metrics,
configuration, raw data or code.

### Admission, publication and workers

New training/tuning submissions, version registration and observation insertion
write the project lifecycle document in the same MongoDB transaction as reference
validation and insertion. A separate read-only check cannot fence deletion under
snapshot isolation. Preserve ordinary matching replay for survivors. Erased
submissions retain key digests/request hashes: matching replay returns 410
`submission_deleted`; changed-body reuse remains 409. Never recreate an erased job
from its former key.

Coordinate registration/upload/preparation publication with erasure using a
process-held project storage lock on the shared artifact volume. Capture the
lifecycle generation before registration begins and require it at publication/
commit, rejecting requests spanning deletion. An explicit new request after
completion can reuse a freed name with a new ID. Resolve uncertain metadata
commits before classifying candidate files as unreferenced. Private staging files
and unrelated published orphans are outside the cascade.

Workers take per-attempt process-held locks before claim and retain them until
threaded work actually stops; store locks outside experiment output directories.
Deletion must acquire the affected attempt locks before cleanup. Distinct
recovery attempts have separate locks, preserving normal lease takeover; a live
stale writer blocks erasure, not recovery. Do not steal OS locks on lease expiry.
Late queue deliveries cannot claim erased records or write files. Keep tuning
parent fencing, reserved IDs and original deadlines.

Declare the already locked `filelock` package as a direct runtime dependency;
update `pyproject.toml`/`uv.lock` without unrelated upgrades. Require native locks
and disallow soft-lock fallback. Verify them across processes on Windows and
actual Compose volumes. Keep lock paths stable; acquire nonblocking/in a fixed
order and report contention. Await owned file work before releasing on
cancellation. Hold no lock across long agent model conversations.

Under the publication lock, resolve all surviving canonical/source/manifest
references before unlinking candidates. Remove only enumerated managed uploads
or exact experiment artifact directories, including old attempts. Verify resolved
paths remain within the intended scope and reject symlink/reparse-point escapes
or ownership/root changes. Never recursively remove a project root/shared volume.
Retain files referenced by surviving datasets, including aliases, and unmanaged
inputs. Metadata removal follows the durable manifest, with scoped batched
progress so interruption does not lose cleanup references.

### UI, deployment and coupled documentation

Use the existing review dialog, destructive styling, exact preview counts and
disabled duplicate clicks. After completion clear deleted selections, run details,
monitoring frames and pending training reviews, then refresh context/lists.
Unknown outcomes check saved operation status and offer same-key resume. Preserve
project-generation guards for late responses/open confirmations. Retained chat
snapshots label unavailable source records rather than present them as current.

Document endpoints, shared/unmanaged/external retention and retry behavior in the
root README, API reference and dashboard guide. Add journal/gate contracts,
indexes, fakes and fixtures. Share coordination paths/volumes among participating
APIs/workers, preserving read-only uploaded data in the worker. Deploy matching
services together after existing work drains; existing dataset/model response
schemas require no deletion timestamps or archived-list defaults.

## Acceptance and verification

Implement after revised approval in checked slices: journal/preview/gate;
admission/publication/worker coordination; cascade/resume; UI; evidence. Test all
active statuses, foreign IDs, same bytes under multiple dataset identities,
preparation references, unmanaged fixtures, missing files, I/O failures and path
escapes. Prove cascade enumeration beyond one 100-record page. Assert unrelated
records/files and source inputs retain their hashes.

Force both sides of deletion versus submission, upload/uncertain insert,
version/observation creation and duplicate deletion using real MongoDB/volumes.
Retain original survivor replay/artifact assertions; justify new 410 assertions
only for explicitly erased work. Kill cleanup at each durable boundary, restart
and retry the original request. Exercise stale writers and delayed queue delivery
without relaxing recovery gates. Browser evidence covers both deletion flows,
blockers, cancel, refresh, lost response/resume, name reuse and project switching.

Run all [fast gates](../../AGENTS.md#verification-commands), `uv build`, the full
ordinary suite with both `MLPP_RUN_INTEGRATION=1` and
`MLPP_RUN_WORKER_INTEGRATION=1`, and the separate serial recovery suite with
`MLPP_RUN_RECOVERY_INTEGRATION=1`, following the
[verification guide](../guides/verification.md). Missing services/skips remain
gaps. Retain revision/image/dependency IDs, commands and raw outcomes. Seek
independent review of cascade, transactions and lock/state ordering; disclose
unavailable review and do not label implementing-assistant self-review independent.

## Risks and rollback

Code rollback cannot undo erasure. Before destructive work, rejection leaves
domain data intact; after cleanup begins recover forward from the journal. Never
remove incomplete intent or release its gate on timeout. Restore from an
operator-controlled backup only if separately requested. Disable new deletion
controls for rollback while retaining compatible gate/receipt/worker/recovery
guards until operations finish; older writers must not bypass pending cleanup.
Unsupported locking, storage failure or unresolved publication blocks cleanup.

## Human review and approval

October 19: Jacob confirms permanent erasure, superseding the prior retained-
history proposal. In the two explicit clarification replies, Jacob selects
"Block deletion until those jobs finish (Recommended)" and "Keep conversations
and drafts; erase training history and files (Recommended)". Approved scope of
those replies: active-job behavior and chat/draft retention. They do not expressly
approve the full revised design. Cascade, retention boundaries, name reuse,
minimal receipts, locking dependency, recovery and acceptance design await that
approval under [AGENTS.md](../../AGENTS.md). No application implementation has started.

## Implementation outcome

- Source/scope: planning only at the baseline above; permanent-erasure revision
  and confirmed active-job/chat-retention choices recorded after `c90a550`.
- Environment/commands: source and installed-lock inspection, `git fetch origin`,
  Windows PowerShell. Branch matches upstream; `origin/main` remains an ancestor.
- Application results/test changes: none; implementation pending revised approval.
- Documentation checks: 13 local links/anchors across both plans validated;
  whitespace/template checks and `git diff --check` pass. No executable examples.
- Review: human design approval pending; no independent review performed.
- Raw application evidence/durable findings: none for this documentation change.
- Completion commit and push: recorded in the task handoff after validation.
