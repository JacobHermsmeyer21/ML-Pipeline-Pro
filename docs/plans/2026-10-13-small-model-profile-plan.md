# Evaluate one smaller local profile for the midterm

- Status: approved one-profile midterm direction; evaluation pending
- Date: 2026-10-13
- Source baseline: `f16e721` with checked delivery implementation in progress
- Human approval: Jacob's approved minimal local-model recommendation/implementation request
- Independent review: separate boundary reviewer; different-vendor unavailable

## Proposed behavior and purpose

Evaluate one explicit Qwen2.5 3B Q4_K_M candidate on the pinned runtime/template,
keeping original acceptance cases and limits. Select it for the demo only if its
identity/token counter and full ten/seven semantics pass. Preserve the existing
7B/14B profiles and their failure/success history, without automatic selection.

## Clarification and critique

Current 7B inference produces about 13 output tokens/second; the normalized tuning
draft needs about 312 tokens and 24 seconds, exceeding the original 20-second call
limit. Serial evaluation with the Kubernetes node stopped still fails that case.
A separate 60-second diagnostic removes the decoder character cap but still takes
24.3 seconds: grammar-size overhead is not established as the cause. No host cap,
assertion, scenario or deadline will be weakened. Compact instructions alone do
not resolve the failure. Backend/full actual-ID/history walkthrough passes, but
current all-profile timing acceptance remains open.

The smaller candidate is a hypothesis, not established reliability. Official
[Ollama metadata](https://ollama.com/library/qwen2.5:3b-instruct-q4_K_M) identifies
1.9 GB weights and a Qwen research license; it is not the existing Apache 7B
artifact. Retain exact installed license/identity and require project-appropriate
use review rather than claiming commercial permission. Weights stay external.

## Requirements

| ID | Type | Requirement | Evidence |
| --- | --- | --- | --- |
| F1 | Functional | One explicit smaller profile guides original dialogue and all four generated Python profiles. | Original ten/seven gates unchanged, one complete retained run each. |
| N1 | Reliability | Exact verified tokenizer/template/runtime/artifact identity; same input/output/time/call limits. | Metadata/vocabulary identity and actual SDK/runtime count equality. |

## Constraints and scope

No paid API, language-model training, general runtime support, new action permission,
output repair, hidden retries or default/native contract change. Add only one
whitelisted identity; unknown profiles still fail. Licensing and hardware evidence
are profile-specific. Existing 7B setup remains available; failure of this candidate
must remain outstanding rather than be hidden by partial passes.

## Design

Explicitly install the official artifact in the ignored model store, inspect its
metadata/license/tokenizer compatibility, and create a new local tag using the
same checked-in template. Add its exact identity to the counter only after verifying
compatibility; setup accepts only the installed pinned base digest. Keep 8192
context, 1024 snippet output, original per-call/turn/suite limits and host byte/AST
validation. Document explicit selection only after actual acceptance. No downloads
inside API/test startup. Independent review covers the whitelist/rendering changes.

## Acceptance and verification

Retain failed candidate runs, source/runtime hashes, license and raw counts. Run
focused counter/native compatibility checks, all fast gates and original ten/seven
live gates; exercise real HTTP/full walkthrough on a selected passing profile.
No different-profile results may be combined into one acceptance result.

## Risks and rollback

A smaller model may lose semantic reliability. Retain 7B configuration and report
failed acceptance if it does. Remove only the additive profile selection/code if
rejected; never delete existing weights or saved actions/drafts. No model artifact
is baked into the application or container.

## Human review and approval

One-candidate evaluation within Jacob's approved small local-model/classroom
scope; this does not assert separate human review of this document or its license.
Material changes to acceptance/defaults require renewed review.

## Implementation outcome

Pending. Current 7B code timing remains a recorded acceptance gap.
