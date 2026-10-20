# Short record ID acceptance

October 20, 2026, approved short-ID implementation on `main`, based on plan commit
`2bd91ff` and including collaborator metrics commit `a44452e`. Tests ran on the
implementation working tree; `manifest.json` records source hashes. The local
demo upgrade is recorded separately after implementation commit/push.

Experiments now expose permanent project-scoped `eN` references and conversations
`cN`. Canonical IDs, artifacts, request hashes and action fingerprints remain
unchanged. New references publish transactionally; paused-writer migration adds
existing-record metadata without rewriting saved turn payloads.

| Evidence | Result |
| --- | --- |
| Locked training sync; Ruff lint/format; dependency compatibility | Pass; 121 compatible installed packages. |
| Full fast gate with coverage | 837 passed, 123 deselected; 79% reported total coverage. |
| Full ordinary gate, both integration flags | 111 passed, 845 deselected, no selected skips. Isolated ports 18002/37018/16380. |
| Final focused real-MongoDB boundary gate | Six passed: concurrent allocation/scoping/nonreuse/final counter slot, injected transaction conflict, resumable migration/literal collisions, conversation replay/actions, legacy payload preservation and tuning parent ownership. Includes the additional legacy-payload case introduced after the full ordinary run. |
| Serial isolated recovery gate | 12 passed, 944 deselected; its own `mlpp-recovery-1345e32e9afb` stack. Worker/dependency interruptions affect only that disposable stack. |
| Chrome and real-worker acceptance | Pass: two successful training runs, same-key replay, e1/e2 reads/comparison, artifact size/hash verification, registration by alias, run/detail/fact labels and UUID-only remembered conversation label migration/reload. |
| Local-model acceptance | Pinned guided Qwen 7B on Ollama 0.40.2 completes e1 inspection and e1/e2 comparison, with canonical validation-F1 facts, c1/c2 history and exact replay. Finite 120-second turn / 60-second model test profile. No hosted calls. |
| Supplementary HTTP conversation gate | c1/c2 history and c1 continuation/replay pass. Validation API intentionally lacks an AI model: that continuation saves `model_unavailable`, separately from successful direct local-model generation. |
| Package build and archive inspection | Wheel/sdist build; short_ids.py included and tool/cache/secret exclusions inspected. Generic in-source uv-cache warning checked against actual archive contents. |
| Independent review | Separate local Qwen 14B review of allocation, integration, migration and UI boundary; [scope, limits and resolutions](review.md). Human usefulness review remains separate. |

`raw.zip` retains logs/XML, successful and failed browser reports, the independent
review's exact scope/response/provenance, package-build log, HTTP evidence and
serial recovery snapshots/logs. `short-ids.png` is the successful browser view.
The first browser attempt passed worker/local-model assertions then failed on an
ambiguous test selector matching both Close and Back. The harness now selects Back
explicitly; the full rerun passes. No product assertion was weakened.

The first targeted fast run exposed that the existing tuning fake inherits the
experiment fake. Alias assignment is now limited to records declaring `short_id`;
the existing tuning assertions pass unchanged. Added tests establish positive
ASCII alias bounds, project/record identity, duplicate canonical comparisons,
nonreuse and explicit requested-fact evidence matching. Existing tests were not
relaxed or skipped.

Application source remained unchanged after the final fast run began. The
additional migration case changes test coverage only. Recovery and the isolated
application image preceded the requested-fact guidance correction; alias storage,
ownership and recovery code are identical. The final browser/local-model run uses
the corrected host guidance and the validation image's same storage/API code.
No broader model reliability, load/scaling or course-completion claim is made.
