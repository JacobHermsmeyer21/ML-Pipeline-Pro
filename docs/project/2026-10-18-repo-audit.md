# Repository audit and October 20 demo priorities

Historical October 18 audit: branch/main relationships, missing frontend/storage
work and laptop gate failures below describe that revision. October 19 delivered
the dashboard, preparation/column versions and permanent deletion; standalone
laptop gates and two unbounded diagnostics subsequently pass, while bounded
deployed laptop acceptance stays open. Use [current status](project-status.md)
for the reconciled state; the original findings/evidence remain unchanged below.

Audited October 18, 2026, against `cb67bb8b3937dbf4dbe7fe6ae2c9247ee37849d0`
on `person-a/conversation-foundation`. Jacob confirmed the presentation will use
the **CPU laptop**. This audit runs on the Ryzen 7 7800X3D / RX 9070 workstation;
checks here cannot establish laptop AI acceptance.

The minimal all-nine course implementation exists. Most of Person B's original
service/monitoring/deployment assignment is already delivered on this branch
under the approved October 13 scope. The urgent gap is reliable AI on the
presentation laptop, followed by delivery/rehearsal and the remaining review.
Starting the original B backlog from scratch would duplicate working features.

## Published state and audit scope

Fetching origin found no incoming commits: the working branch matches its
upstream and contains 35 commits beyond `origin/main` (`f0ec2ad`). Main is an
ancestor, with no main-only commits. Origin advertises only main and this branch;
no additional published Person B branch is visible. This does not establish what
another person may have done privately. The working tree was initially clean.

Inspection covered requirements, plans, memory, application boundaries,
tests/evaluations, examples, dependencies/builds, Docker/Compose, Kubernetes,
CI, guides and retained evidence. Inventory checks cover 44 application modules
and all 30 distinct API operations across the three factories; the API reference
matches. All 51 source hashes in the passing RX 9070 walkthrough still match this
checkout. All 14 pre-existing ZIP evidence archives pass CRC checks. Source/hash
checks establish identity and readability, not universal correctness or review.

## Course coverage and Person B takeover

The [course checklist](course-requirements.md) remains authoritative. The
[approved minimal scope](midterm-scope.md) supersedes the broader immediate
ambitions of the historical two-person allocation.

| Requirement | Implemented and evidenced | Remaining demo concern |
| --- | --- | --- |
| C1: environment | Locked uv/Python, PyTorch, PyMongo, LangChain/Ollama; pinned model/tokenizer setup | Verify final laptop checkout, runtime and installed artifact |
| C2: separate services | Independent model/conversation, tuning and monitoring APIs, gateway, Compose/Kubernetes | B1 and B2 service separation delivered; preserve shared MongoDB transactions |
| C3: conversational AI | Grounded reads, history, guided 7B, missing-input handling, exact confirmed actions | Workstation passes 10/10; latest laptop gate passes 2/10 |
| C4: MongoDB | Scoped parameters, experiments, versions, trials, metrics, indexes and small-demo query evidence | Larger benchmarks deferred; preserve source CSVs and artifacts |
| C5: intelligent tuning | Serial Optuna TPE, validation selection, winner-only final test evaluation, recovery and AI proposals | Backend works; laptop AI proposal path has not passed |
| C6: monitoring | Immutable observations, actual inference producer, bounded summaries, Prometheus/Grafana, threshold and cited advice | Minimal B2 delivered; laptop generated diagnosis depends on working inference |
| C7: generated Python | Four model-generated profiles, AST/API validation, saved drafts/provenance, no execution | Workstation passes 7/7; latest laptop gate passes 0/7 |
| C8: testing/deployment | Fast/service/recovery suites, Docker, real kind rollout, direct replay through two API pods, CI/CD | B3 delivered; current CI passes; final laptop deployment preflight remains |
| C9: onboarding | Complete actual-ID/history/draft/monitoring tutorial and clean-checkout/Kubernetes evidence | Minimal B4 tutorial exists; full laptop rehearsal remains outstanding |

Source confirms training-only preprocessing, validation-based selection,
hash/size-verified artifacts, same-transaction parent-write ownership fencing,
reserved tuning identities/deadlines, project access and submission replay.
Training stays serial. Monitoring is a capped observed window with explicit
unknown labels and seeded delays, not general drift detection. The demo surface
is Swagger/API examples plus Grafana; a custom frontend is explicitly deferred.

## Findings in priority order

1. **Demo blocker: no passing complete AI run on the chosen CPU laptop.** Latest
   full gates pass 2/10 dialogue and 0/7 snippets. The post-reboot walkthrough
   measures 113.524 seconds of prompt evaluation and 19.545 seconds generation,
   followed by an API 504 after 140.929 seconds despite 20-second model and
   60-second turn limits. It reaches no tool read. Slow inference is established;
   the timeout-overrun mechanism remains undiagnosed. The later RX 9070 success
   does not fix laptop behavior. See [laptop failure](../evidence/2026-10-14-post-reboot-validation/README.md)
   and [workstation success](../evidence/2026-10-14-rx9070-walkthrough/README.md).
2. **Delivery risk: main lacks the implementation.** A laptop checkout of main
   receives the old allocation/backend. Pin the published working-branch revision
   for rehearsal/submission, or integrate through the agreed review process.
   This audit does not merge main.
3. **Review gap: the requested-inspection-fact correction lacks separate boundary
   review.** Earlier service/snippet boundaries have recorded separate same-vendor
   review. Later workstation success neither replaces review nor reproduces the
   unavailable original failed record. New generated outputs require human review.
   No independent review was performed by this audit.
4. **Documentation drift obscures readiness.** The architecture still called
   implemented monitoring routes proposals; the index called delivered tutorials
   outstanding. This audit corrects active summaries and makes the CPU limitation
   visible from the README/roadmap. Historical dated records remain intact.
5. **Source-package hygiene check fails.** The build succeeds and the wheel has
   all 44 application modules, but the source archive includes
   `.tools/midterm-clean/.env.example`. Its bytes match the public root example;
   no private `.env`, weights or cache contents were found. Git itself reports
   the file ignored by `.tools/`; why source selection includes it is unresolved.
   Explicit source-build exclusions should be evaluated before distributing a
   source package; this audit does not change build configuration.

The 3B candidate was already rejected: only 5/10 dialogue and 1/7 snippets passed,
and its supported-profile changes were removed. Selecting it, raising timeouts,
replaying answers or dropping assertions would not establish a working laptop
AI demo. See the [candidate outcome](../plans/2026-10-13-small-model-profile-plan.md#implementation-outcome).

## Priorities before October 20

Classifier training can run live while Jacob presents. The retained October 14
laptop `walkthrough/backend.json` timestamps show the existing five-epoch demo
training taking **0.887 seconds from worker start to completion**, or **1.641
seconds from submission to completion**. Three-trial tuning, including final
evaluation, takes **1.574 seconds from submission to completion**. These are one
small-fixture run with services already running, not cold-start or arbitrary-data
guarantees. The separate Qwen language model is already pretrained; its slow
inference is not classifier training and is not fixed by background training.

**October 18:** preserve the working backend/services. Investigate CPU inference
at the failing boundary: collect prompt/generation timings, resource use and
event-loop/cancellation observations without changing the gates. Establish
whether the current runtime can meet them before pursuing another model. Any
execution/default/model-support design change needs a concrete plan and human
review. Using the workstation for inference or presentation is an option to
review, with a tested connection and agreed arrangement; it would change the
approved one-machine scope and is not existing laptop acceptance.

Jacob proposed an eight-minute Qwen diagnostic. The
[bounded diagnostic plan](../plans/2026-10-18-laptop-qwen-diagnostic-plan.md)
was approved by Jacob on October 18 and implemented as `0f6ed20`. The actual
laptop [single-request diagnostic](../evidence/2026-10-18-laptop-qwen-diagnostic/README.md)
returns the correct first inspection step in 99.359 seconds after separate
24.281-second warmup. Prompt processing accounts for 88.330474 seconds. This
passes eventual first-step response within eight minutes, while exceeding the
unchanged 20-second call limit. Full laptop gates/tutorial and the API timeout
mechanism remain outstanding; no inference configuration was changed.

**October 19:** rehearse the exact final arrangement with the original ten/seven
gates and complete actual-ID walkthrough. Verify training, Bayesian tuning, exact
approval, saved draft/replay, measured observations, dashboard/alert and generated
diagnosis. Retain a complete run with source/model/runtime/timing provenance;
inspect generated outputs and complete the boundary review. Freeze that revision
and prepare concise presentation steps plus a labelled recording/evidence fallback.
Availability of an external recording is unknown; a recording is not live acceptance.

**October 20:** start/warm the tested runtime before class, check readiness and
worker progress, and open API docs/Grafana and retained evidence. Avoid installs,
downloads and untested configurations during class. Backend-only fallback does
not demonstrate the full C3/C5/C6/C7 AI requirements.

Keep broader B work deferred: advanced drift/notifications, production metrics,
immutable object storage, retention/migrations/restore, person-level identity/TLS,
authenticated dependencies, concurrent training and large research benchmarks.
These remain capabilities to deliver beyond the approved minimal course scope.

## Fresh verification and limits

[Audit evidence](../evidence/2026-10-18-repo-audit/README.md) records commands,
results, source hashes and raw output. Application behavior and assertions are
unchanged. Locked sync, Ruff lint/format, dependency compatibility and **598 fast
tests** pass, with 73 integration/recovery cases deselected and 80% rounded host
coverage. Worker execution and real MongoDB ownership are outside fast coverage.

The rebuilt isolated ten-service stack passes routing and actual
training/three-trial-tuning/version/monitoring/submission-replay smoke. Smoke
telemetry is synthetic, not a newly measured monitoring workload. Ordinary and
recovery checks pass **63** and **ten** cases respectively, without selected
skips; recovery runs serially. The initial integration
attempt omitted `/api/v1` from the test origin; its 13 failures/50 passes are
retained as an audit invocation error. The corrected run keeps all assertions.

The exact baseline branch's [remote CI](https://github.com/JacobHermsmeyer21/ML-Pipeline-Pro/actions/runs/38681567923)
has all five jobs successful: Python 3.11/3.13 checks, compatibility Compose with
isolated recovery, domain Compose and actual Kubernetes deployment. These jobs
do not run real-model quality gates. This audit makes no new laptop/live-model
acceptance, performance, or exhaustive security/concurrency claim.
