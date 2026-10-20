# Permanent dataset/model deletion verification

October 19, 2026, America/New_York. Design and explicit Jacob approval are in the
[plan](../../plans/2026-10-19-permanent-deletion-plan.md). Application changes were
prepared separately from simultaneous column-editing work, against `270ef7d`.
See [environment provenance](provenance.json); no language-model gate or
performance/capacity claim is made by these deletion checks.

| Verification | Result | Retained evidence |
| --- | --- | --- |
| Deletion-only fast suite | 722 passed; no selected skips | `fast-deletion-only.xml` |
| Deletion-only ordinary integration, both live flags | 98 passed; no selected skips | `ordinary-deletion-only.xml` |
| Serial isolated worker/dependency recovery | 10 passed; no selected skips | [recovery JUnit](recovery.xml) |
| Dedicated deletion transactions/process boundaries | 21 passed, including a 125-run cascade and four actual process kills | [storage JUnit](deletion-store.xml), [test source](../../../tests/integration/test_deletions.py) |
| Combined workspace regression before staging | 739 fast / 104 ordinary passed | [fast JUnit](fast-final.xml), [ordinary JUnit](ordinary-final.xml); includes separately owned column work |
| Browser on deletion-only image | Passed at 1440x900 and 1280x800; zero page exceptions | `browser-deletion-only/result.json` and screenshots |
| Native cross-container exclusion, holder death, late erased job delivery | Passed on actual shared Docker volumes | `native-volume-deletion-only.json` |
| Package/dependencies | Locked sync, lint, format, installed compatibility and build pass; wheel/sdist inspected | `package-inspection.json`; private/cache paths excluded |
| Existing local dashboard | Verified deletion modules/assets match; five domain/worker services use one image | [live-image hashes](live-image.json); combined column/deletion runtime preserved |

The 722-case fast run and standalone build used an exported Git tree rather than
the concurrently changing working directory. Final staging also removes the other
task's column-only request middleware, whose routes are absent from this commit;
the original middleware remains unchanged for deletion and existing routes. The
final fast gate is repeated on that staged source (`fast-deletion-commit.xml`).
Other subsequent changes are documentation and verification-script formatting.
The main shared-workspace fast suite also passed before staging. Direct unit fake stores do not establish transactional
correctness: real MongoDB checks cover the lifecycle gate and cleanup ordering.
Recovery ran serially in its separate `mlpp-recovery-*` project. Neither ordinary
nor recovery tests ran against the user's saved demo records.

The [browser harness](../../../scripts/verify_deletion_dashboard.py) creates a
fresh disposable project, runs real serial training and verifies artifact hashes.
It checks cancel, double click, dataset/model cascades, shared-source preservation,
actual active-worker blocking, lost-response/reload/same-key recovery, name reuse,
surviving-input training and late responses after project switching. Its long
blocking exercise intentionally uses an eight-second training budget; that job
ends failed on budget and is not reported as successful classifier training.

The [storage harness](../../../scripts/verify_deletion_storage.py) holds a native
lock in the API container, proves a worker cannot acquire it, kills that exact
holder, then proves acquisition succeeds. A real Celery delivery for an already
erased fixture experiment returns `not_claimed` and does not recreate its artifact
directory. Empty stable coordination files and minimal operation/key receipts
remain by design; these are not saved training data or checkpoints.

Earlier failures are preserved. [Initial ordinary JUnit](ordinary.xml) records
97 passes and one monitoring fixture failure: the fixture lacked the saved version
now required for transactional observation admission. The fix supplies that
reference and keeps its race/replay/pagination/index assertions. The initial
browser results in `browser-first/` show a harness assertion before the deliberately
lost response finished; the corrected harness waits for the recovery action to
be enabled. `browser-second/` then exposes the real reload-to-`demo` defect, fixed
by restoring the nonsecret active project before loading session state.
[Third browser run](browser-third/result.json) and standalone browser acceptance
pass those original boundaries. No assertion was lowered or selected case skipped.

Other verification details: the Windows process-death harness initially targeted
the virtual-environment launcher instead of the actual lock owner. It now records
and kills the helper's own PID, proving native release. One old preparation test
expected no filesystem entries after rejection; it now requires exactly the
empty stable coordination file and no private/published data. The first build
could not access PyPI inside the sandbox; the offline cached build succeeded.
The workspace-cache warning was checked against the actual archives, not ignored.

Independent review was sought through the available capabilities; no separate
code-review provider was available. Implementing Codex self-review covered
cascade/project scopes, transaction retry callbacks, receipts, path containment,
lock lifetimes, cancellation and preview/retry ordering. This is self-review,
not independent review; that gap remains disclosed for human review.
