# Dataset short IDs

- Status: implemented; verification and coordinated demo rollout recorded below
- Date/baseline: October 20, 2026, `e7e6bb2` on `main`
- Human authorization: Jacob requested the same short-ID behavior for datasets,
  explicitly instructed "dont make me aprove a plan, just implemnt it", then
  emphasized agent understanding of d1/d2. This request overrides the separate
  plan-approval step for this extension; no additional approval is requested.

## Proposed behavior and purpose

Add permanent project-scoped `d1`, `d2`, `d3` dataset references using the existing
transactional registry. Dashboard, agent read/training/tuning proposals and API
dataset inputs accept them. Canonical dataset UUIDs and stored relationships,
recipes, artifact references and historical evidence remain intact. Numbers are
never reused after deletion. Existing installations backfill with writers paused.

## Clarification and critique

Reuse the established alias design rather than replacing UUIDs or numbering in
the browser. Separate counters by project and kind. Each immutable dataset version
gets its own reference. The user has already specified the behavior and authorized
implementation; no unresolved intent questions remain. This is C3/C9 usability
work and does not change the course's existing acceptance limits.

## Requirements and design

- Extend `ShortIds.KINDS`, dataset metadata and transactional lifecycle admission.
  Resolve dataset reads and all public inputs to canonical identities, including
  training/tuning admission, column saves and deletion preview/execution.
- Fingerprint original training/tuning bodies and deletion paths before resolving;
  persist canonical references and dispatch the exact approved action arguments.
  Column request digests retain canonical parent identity and replay even after
  parent deletion through the permanent registry.
- Normalize agent read targets before strict tool identity checks; accept dN in
  proposals without changing their saved arguments/hash. Explicit requested-fact
  constraints must still refer to verified canonical records.
- Show dN in dataset cards, selectors, run context, starter prompts and facts,
  keeping full IDs available. Preserve eN/cN behavior and all ownership fences.
- Unknown/foreign/deleted references retain existing scoped errors. Rollback all
  services together while retaining mappings/counters and canonical data.

## Acceptance and verification

Run targeted API/tool/column tests and all AGENTS.md fast checks. Run affected real
MongoDB/worker/deletion gates with both ordinary flags and isolated serial recovery
because admission and deletion boundaries are affected. Verify uploads/preparation
and child versions each receive dN, concurrent/retried publication, nonreuse,
canonical training/tuning references, exact proposal/replay hashes and column
replay after parent deletion. Extend migration expectations with the dataset
namespace without weakening existing eN/cN assertions.

Use isolated browser/worker/local-model acceptance to inspect d1 and propose
training with d1; verify canonical fact references, saved d1 action arguments and
exact confirmation dispatch. Seek separate local-model review of boundary diffs
and record its scope/limits. Run a coordinated local-demo migration only after
checks, preserving canonical payloads, existing eN/cN assignments and every input/
artifact file. Retain evidence, update memory, commit and push each major change
with incoming-history checks. Human usefulness review remains separate.

## Implementation outcome

Implemented under Jacob's direct authorization. Scope follows this record;
separate plan approval was intentionally omitted per his instruction.

- Added dN dataset metadata/allocation and scoped resolution for reads, agent
  inspection, experiment/tuning submission, columns and deletion. Existing
  canonical relationships and original request/action hashes are preserved.
- 842 fast and 116 ordinary integration tests pass without selected skips.
  Serial recovery results are retained in the
  [evidence record](../evidence/2026-10-20-dataset-short-ids/README.md).
- Real pinned local Qwen inspects d1 and d2 with canonical facts, proposes d1
  training, and exact confirmation dispatch completes one real worker run with
  verified artifacts. Chrome verifies labels, selection, prompt and refresh.
- Locked dependencies, lint/format, package build/archive and local documentation
  checks pass. Existing assertions were preserved; migration expectations include
  the new dataset namespace. Added tests verify the new public boundaries.
- A separate Qwen 14B review is retained with source/test-backed resolutions;
  its unsupported findings are disclosed, not presented as verified defects.
  Human usefulness review remains separate.
- The [short-ID memory](../memory/short-record-ids.md) records dataset fingerprint,
  deletion receipt and column replay boundaries. Implementation commit/push and
  preserved-data local demo upgrade are reported in the completion handoff.
