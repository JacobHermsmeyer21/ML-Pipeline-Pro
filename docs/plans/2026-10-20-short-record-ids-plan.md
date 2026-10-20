# Short experiment and conversation IDs

- Status: implemented; isolated acceptance verified; local demo upgrade pending
- Date: 2026-10-20
- Source baseline: `d0fad5a` on `main`
- Request: make experiment and conversation IDs easier to type.
- Human decisions: Jacob selected dashboard, agent chat and API support, then
  requested experiment IDs beginning with `e` and conversation IDs with `c`.
- Human reviewer/implementation approval: Jacob, October 20, 2026, "approved" in chat.
- Independent review: local Qwen 2.5 14B, Ollama 0.40.2; submitted scope,
  findings, limits and resolutions retained in the evidence record.

## Proposed behavior and purpose

Show experiments as `e1`, `e2`, `e3` and conversations as `c1`, `c2`, `c3`.
Users can type those references in agent messages and existing API ID inputs.
Keep canonical UUIDs and their stored references intact. Each project has its own
experiment and conversation sequence, beginning at one. References persist across
reloads, browser sessions and service restarts. Never renumber surviving records
or reuse a deleted record's short reference. Gaps are acceptable.

## Clarification and critique

The user explicitly selected all three interfaces and letter prefixes. This plan
interprets that choice as permanent project-scoped aliases, with separate counters
for experiments and conversations. Dataset, model, version, tuning-job, action and
request IDs are outside scope. No further user intent questions remain for this
proposed scope; approval below confirms these defaults.

Source uses UUIDs for canonical records in
[repositories](../../src/ml_pipeline_pro/repositories.py) and transactional
[conversation storage](../../src/ml_pipeline_pro/conversation_store.py). The
dashboard currently abbreviates UUIDs. Merely shortening those labels does not
make typed references work. Browser-only numbering would change between machines
and risk selecting the wrong record. Replacing stored UUIDs would unnecessarily
change artifact, ownership and historical references. Durable aliases preserve
those identities at the cost of a small allocation/migration subsystem.

This improves course C3/C9 usability; it does not close outstanding model,
deployment or independent-review acceptance gaps.

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | Show stable `eN` and `cN` references for existing and new records, including tuning-created experiments. | Migration, creation, refresh and restart checks. |
| F2 | Functional | Accept short references wherever existing API inputs accept experiment or conversation IDs; retain canonical-ID support. | History, continuation, action read/decision, experiment read/artifact/compare and version-registration API tests. |
| F3 | Functional | Agent messages such as "inspect e1" and "compare e1 and e2" identify the exact scoped records and retain verified facts. | Deterministic host/tool tests and an opt-in real-model inspection/comparison walkthrough. |
| F4 | Functional | Keep sequences separate by project and kind; deletion never redirects an old alias to a new record. | Cross-project, namespace and deletion/recreation tests. |
| N1 | Reliability | Concurrent creation, transaction retry and request replay never allocate competing aliases for one identity or publish duplicate aliases. | Real-MongoDB interleavings and existing reservation/submission replay gates. |
| N2 | Compatibility | Preserve canonical storage references, original request fingerprints, action hashes, ownership fences, deadlines and artifacts. | Existing fast/ordinary/recovery gates plus alias-specific replay checks. |

## Constraints and scope

Preserve `/api/v1` canonical ID fields and accepted legacy requests. Add short-ID
metadata without rewriting historical saved turn/action payloads or evidence.
Do not substitute aliases inside stored generated Python or historical facts.
Maintain project access, lifecycle deletion gates, transaction ownership and serial
CPU training. No dependency, model-provider, training or timeout changes.

## Design

Use a shared MongoDB alias registry and counters keyed by project and record kind.
Mappings bind a short reference to one canonical ID. Unique indexes enforce both
directions. Allocate with atomic increments and transaction-safe insert/retry;
couple new-record publication with its mapping in the existing admission or
reservation transaction. Include tuning child publication without weakening its
parent fence. A replay uses its existing mapping rather than consuming a new
public identity. Allocation failure must fail publication, never fall back to a
temporary browser number.

Backfill existing records in resumable bounded batches while record creators are
paused for the coordinated upgrade. Order each project's existing records by
`created_at`, then canonical ID. Retain committed mappings/checkpoints on retry;
verify complete coverage and uniqueness before resuming writers. Do not claim
old records' numbers reflect an exact creation order when timestamps tie.
Allocation must avoid collisions with existing literal canonical IDs, including
non-UUID legacy IDs. Existing exact canonical matches retain their meaning.

Resolve only valid positive forms `e[1-9][0-9]*` and `c[1-9][0-9]*` in their
corresponding ID fields. Resolve under the authenticated project, then apply the
existing read/deletion/ownership checks to the canonical record. Unknown aliases
use the existing scoped missing-record behavior; deleted aliases never resolve
to replacement records. Keep minimal mappings/counter history after erasure,
without retaining copied dataset/model facts. Bound numeric parsing to MongoDB
counter capacity and fail explicitly on exhaustion.

Expose additive short-ID metadata on experiment reads/lists and conversation
responses/history, including historical records through read-time projection.
Keep canonical `id`, `conversation_id`, fact references and saved payloads intact.
Document exact added fields in schemas and the API reference during implementation.
Keep replayed responses consistent under the same deployed version; preserve old
stored request hashes and compute new hashes from the originally submitted body.
Changing alias spelling to UUID under the same request key may remain a body
conflict, matching existing exact-body idempotency.

Normalize aliases before tool dispatch identity comparisons and evidence capture.
[Tools](../../src/ml_pipeline_pro/tools.py) currently require returned canonical
IDs to match requested IDs exactly; preserve that assertion against resolved IDs.
Do not simply accept mismatching tool outputs. Resolve two aliases for the same
experiment before duplicate comparison validation. Keep approved action arguments
and hashes immutable; resolve their ID inputs at execution boundaries. Preserve
the original chat text and identify verified canonical records in the host ledger.
Support alias references in generated API examples without changing saved drafts.

Update dashboard conversation labels, run rows/details/comparisons and relevant
fact/outcome displays to show short references prominently, with canonical IDs
available in details. Keep actual pending-request bodies and recovery identities
intact. Update [dashboard guidance](../guides/dashboard.md), README endpoint
documentation and [API reference](../reference/api.md), plus schemas, repository
protocols, fakes and fixtures affected by allocation/resolution.

## Acceptance and verification

Run targeted alias/API/tool/dashboard tests after meaningful steps, then all fast
checks from AGENTS.md: locked training sync, Ruff lint/format, non-integration
pytest with coverage and `uv pip check`. Build with `uv build` if package contents
change. Test changes must establish alias behavior while retaining old-ID,
fingerprint and ownership assertions.

Run affected real-service cases following
[ordinary integration](../guides/verification.md#ordinary-integration) with both
`MLPP_RUN_INTEGRATION=1` and `MLPP_RUN_WORKER_INTEGRATION=1`. Exercise simultaneous
allocations, transaction callback retries, migration interruption/resumption,
tuning child admission, cross-project isolation and deletion/recreation. Run
affected ownership and isolated recovery cases serially with
`MLPP_RUN_RECOVERY_INTEGRATION=1` separately. Missing services or selected-case
skips remain gaps.

Use an isolated project for browser acceptance: create two experiments and two
conversations, verify labels, reload and reconnect, read by aliases and UUIDs,
continue the same conversation by `cN`, compare experiments by `eN`, and verify
artifact retrieval and same-key replay. Retain raw commands/results and browser
evidence. A real-model gate uses the configured opt-in provider and its existing
authorization/budget; absent authorization or runtime is reported as a gap.
No performance improvement is claimed. Seek independent review of allocation,
migration, resolution, replay and deletion boundaries and record findings.

## Risks and rollback

Main risks are cross-project ambiguity, collisions, incomplete migration,
duplicate allocation, tool identity rejection and changed replay fingerprints.
The above negative and real-service checks address these boundaries. Coordinate
all APIs, worker and scheduler so old writers cannot create unnumbered records
after migration. Keep data and artifacts; upgrade does not require erasure.

Rollback coordinated application code to canonical-ID behavior while retaining
alias mappings and counters for a future roll-forward. Canonical IDs continue to
work; aliases are unavailable in older code. Do not clear registry history or
reuse numbers, and do not run mixed writers against an incomplete migration.

## Human review and approval

Jacob confirmed the three-interface scope and prefix preference in this chat on
October 20. Those decisions precede this written plan and are not recorded as
approval of its allocation/migration design. Jacob subsequently replied "approved"
after the plan handoff, authorizing the complete written scope on October 20.

## Implementation outcome

Implementation based on `2bd91ff`, with collaborator metrics changes through
`a44452e` preserved. See [retained evidence](../evidence/2026-10-20-short-ids/README.md)
for exact commands/results, source manifest and raw runs.

- Added transactional registry/counters, short-ID metadata and scoped resolution
  for experiment and conversation inputs; immutable canonical IDs/fingerprints.
- Added bounded resumable migration, canonical tool/evidence normalization,
  alias-aware requested-fact constraints, dashboard labels and upgrade guidance.
- Verification: 837 fast, 111 ordinary, six focused real-store and 12 serial
  recovery passes; no selected skips. Browser/two real training runs and pinned
  local Qwen e1 inspection/e1/e2 comparison pass. Package and dependency checks pass.
- Independent local-model review is retained with resolutions; human usefulness
  review remains separate. No new hosted-provider spend or broad load claim.
- New tests cover alias grammar, bad tool resolution, project isolation, duplicate
  canonical inputs, transaction retry/rollback, overflow, migration/replay,
  erasure nonreuse and tuning fencing. Existing assertions/skips are unchanged.
- Implementation follows the approved scope. Existing literal-ID collisions use
  the planned canonical priority. Counter mappings double as permanent tombstones.
- Durable finding: [short-ID identity/evidence boundaries](../memory/short-record-ids.md).
- Implementation commit/push and local demo migration are reported in handoff;
  coordinated rollout evidence follows separately.
