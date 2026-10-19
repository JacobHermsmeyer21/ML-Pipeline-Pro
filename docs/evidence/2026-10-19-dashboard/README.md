# October 19 local dashboard

Jacob approved the dashboard plan, removed timed checkpoints and requested an
early visual prototype during implementation. After seeing the running design,
he replied, "Yes—keep this visual direction." He then said "looks good, use that
prototype dashboard." The working product retains that design.

Open `http://127.0.0.1:8000/dashboard/` on this Ryzen 7 7800X3D / Radeon RX 9070
desktop. The workspace provides numeric CSV upload/column mapping, model creation,
bounded serial training, validation results/comparison, verified artifact downloads,
version registration, saved local-agent conversations and exact proposal decisions,
reviewable generated Python, and real embedded Grafana panels. See the
[startup and browser walkthrough](../../guides/dashboard.md).

## Verification

| Check | Recorded local result |
| --- | --- |
| Locked sync, lint, formatting, dependencies | Pass; 219 files already formatted, 109 compatible packages |
| Package build/content inspection | Wheel/sdist pass; seven UI assets match source; tool/cache/artifact paths excluded |
| Fast tests | 684 passed, 85 integration deselected, no selected skips; 81% rounded coverage; 51.46 seconds |
| Ordinary real-service integration | 75 passed, 694 deselected, no selected skips; both required flags; 41.84 seconds |
| Isolated serial recovery | 10 passed, 759 deselected, no selected skips; 281.58 seconds |
| Real browser workflow | Upload/model/training/artifact/version, validation comparison and saved tuning trials pass |
| Live local agent | Verified fact inspection, same-turn replay, reject/no job, exact approve/one completed run and saved Python draft pass |
| Grafana/monitoring | Three actual canvases, saved-value agreement, automatic empty-to-observed refresh, selected version/range links and local-model explanation pass |
| Interaction/layout | Project-switch race, unavailable-service recovery, memory-only keys, accessible controls, keyboard dialog and both desktop sizes pass |
| Final services | Ten running, all configured healthchecks healthy; original 20/60/90-second desktop budgets retained |

The real Chrome journey uploaded a fresh fixture, verified its 80/20/20 row counts
and SHA-256, created a model, trained through the shared uploaded-file volume,
checked the actual downloaded checkpoint hash/size, and registered a version.
Corrupting the first accepted training acknowledgement preserved its original
request body/key; explicit replay recovered one run. Double clicking sent one
submission. Reload restored saved records. Existing tuning trials and same-dataset
validation comparison also work through actual controls.

The local agent inspected saved results, recovered a deliberately lost first reply
using the original request identity and identical saved turn, rejected a proposal
without a job, and explicitly approved one bounded training run. Double clicking
sent one decision. A validated model-generated Python draft survived reload and
was never executed. The final integrated agent browser journey took 10.458822
seconds; its slowest complete chat HTTP reply took 2.4879 seconds. All five request
timings, including one saved replay, are retained. These single-run intervals
exclude build/startup/warmup and do not establish capacity or latency bounds.
The first journey took 11.344219 seconds but lost per-request fetch records during
a harness reload; that earlier diagnostic remains saved.

Three real Grafana iframe canvases render latency, labeled accuracy and
error/declared-delay series for the named version. Prometheus values match saved
observations, the 100 ms reference line renders, and time-range changes update
all panel/full-dashboard links. A fresh empty version picks up later measurements
and updates its summary without manual refresh. The producer replays a finalized
validation fixture using CPU inference and injects five declared 150 ms delays
among 20 samples. These are demonstration observations, not training-loss curves,
independent generalization evidence or production-performance measurements.

Browser checks also confirm that delayed old-project responses cannot populate
a new project; foreign-project graphs are withheld; service errors are visible
and manual refresh recovers; keys remain in page memory and are not restored on
reload; controls have accessible names; and Enter/Tab/Escape works in the connection
dialog. Screenshots fit 1440x900 and 1280x800 without horizontal overflow. The final
selector-alignment check measures the two controls in actual Chrome at both sizes.

## Confirmed defects and retained failures

The first real concurrent-upload test failed exact response equality: initial
microseconds ended in `995710`, while MongoDB replay returned `995000`. Upload
records now normalize UTC timestamps to milliseconds before persistence and first
response. The complete equality assertion remains intact. New tests cover body
limits, authentication before ingestion, malformed CSV, foreign paths, exact
replay, conflicts/races, ambiguous insertion, timeout/disconnect and repeated
cancellation. The real gateway accepts exactly 10,000,000 bytes and rejects cap+1;
the serial worker reads uploads through its actual read-only shared mount.

The accessibility check found an unnamed model selector because a button was
nested in its label. Separate label/button markup fixes its name; explicit dialog
focus and real keyboard checks pass. Final screenshot inspection caught a spacing
regression from that markup change. Correcting the stylesheet keeps the selectors
aligned. Harness-only navigation timing, reused script variables, lazy offscreen
frames, foreground key delivery and a check against the previous image are retained
separately from application defects. No assertion was weakened, skip added to hide
a failure, AI reply repaired, deadline extended, generated Python executed or
second automatic job created.

Initially empty solo panels stayed empty after Prometheus had samples. The pinned
Grafana refresh picker takes the dashboard's allowed intervals, as shown in its
[official source](https://github.com/grafana/grafana/blob/v12.1.1/public/app/features/dashboard-scene/serialization/transformSaveModelToScene.ts#L357).
A visible-page trace had one query window with `refresh=15s`; explicitly adding
`15s` to `timepicker.refresh_intervals` produced another advancing window after
15 seconds. The summary also needed a separate bounded, non-overlapping refresh.
Selection/project/request fences reject stale reads while preserving chart frames.
The regression starts with an empty version, collects real samples and observes
both graph and summary updates without user refresh.

Package inspection reproduced an ignored nested tool-checkout example in the
source archive. Directory-only excludes did not remove it; explicit descendant
globs do. The corrected sdist excludes tool/cache/artifact paths, and all seven UI
assets in the wheel match source bytes. No dependency was added.

## Provenance, review and limits

Published commits `b303c90` and `1152aa8` were inspected and integrated before the
full service reruns. Later `288277e` changes laptop documentation/evidence only;
the memory-index overlap preserves both findings. Service/test Python hashes stay
unchanged across final gates; subsequent static/Grafana refinements have fresh
browser/package verification. The installed API matches all 56 canonical
Python/static files. Source hashes identify each uncommitted phase precisely.
No current remote CI completion is claimed.

Ollama 0.40.2 serves the pinned 7B profile on the RX 9070. Model digest:
`abadc4bf8517d77dcc8db312ca98cd7cb43488243048c41f1b5746e031427779`.
The new laptop diagnostic flag is false here. Model/turn/client budgets remain
20/60/90 seconds. Heavy checks were quiescent during live model inference.

Jacob approved the prototype direction; he has not independently executed the full
first-time-user checklist in this run. Independent review of upload publication,
size arithmetic and browser replay/state was unavailable. Implementing-assistant
review is self-review, supported by controlled boundary and real-service/browser
checks. It is not independent review. A complete accessibility audit, laptop
rollout, other dataset formats and broader course acceptance remain outside this
evidence.

Monitoring uses the bounded latest-100/five-minute exporter for project `demo`;
new versions can have no observations and old windows become stale. Published
upload blobs are retained after uncertain metadata writes; automated orphan
cleanup is deferred. Conversation discovery uses this browser session's remembered
IDs. Narrow layouts stack the agent; approved desktop layouts retain its right
panel. Stop/rollback preserves database, upload and artifact volumes. The temporary
prototype-only server on port 8010 is stopped; the working workspace uses port 8000.

[Results and provenance](results.json) identify safe outcomes, sources, image,
model, raw reports and the archive hash. The [raw archive](raw.zip) preserves 252
payload files plus its manifest; [member hashes](manifest.json) verify their bytes.
Browser profiles/cache, duplicate downloaded checkpoints and third-party source
files are excluded. Training artifacts/uploads remain in their preserved volumes.

## Screenshots

[Workspace at 1440x900](workspace-1440.png),
[workspace at 1280x800](workspace-1280.png),
[actual Grafana panels at 1440x900](monitoring-1440.png), and
[panels at 1280x800](monitoring-1280.png).


Delivery: implementation commit `9f5009212900b06d6d29d88e58e3a6296fb7eca8` was pushed
successfully to `origin/person-a/conversation-foundation` on October 19 after
checking upstream and `origin/main`. The working dashboard remains running on
port 8000. A follow-up documentation commit records this observed push result.
