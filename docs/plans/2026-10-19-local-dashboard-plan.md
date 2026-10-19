# Local dashboard for tonight's demo

- Status: implemented and locally verified; independent boundary review unavailable
- Date: October 19, 2026; deadline **11:00 pm America/New_York (ET)**
- Source baseline: `98b4908` on `person-a/conversation-foundation`
- Request: add datasets, talk to an agent and train models through a dashboard
- Human decisions: Jacob requests relevant Grafana graphs and a dashboard that is
  "nice to look at"; confirms an 11:00 pm ET handoff
- Human reviewer/implementation approval: Jacob, October 19; approved with timed checkpoints removed
- Independent review: seek review of upload limits/publication and browser replay
  handling; reviewer availability unknown; no independent review performed

## Proposed behavior and purpose

Open `http://127.0.0.1:8000/dashboard/` on this Windows desktop and complete the
dataset-to-trained-model workflow in the browser. Provide real CSV upload, model
selection/creation, training controls, saved results, agent chat and explicit
proposal approval. Embed useful live Grafana graphs within a cohesive interface.
Use the existing local 7B agent and separate model, tuning and monitoring services.

Tonight's deliverable is one working local workspace with Datasets, Runs and
Monitoring views, plus a persistent agent panel. A documented startup command is
allowed; the core browser journey must not require PowerShell requests or scripts.
This adds a product interface to the [demonstrated desktop backend](../evidence/2026-10-19-desktop-demo/README.md).
It does not establish CPU-laptop readiness or complete previously open course gaps.

## Clarification and critique

Jacob explicitly requires attractive presentation, Grafana graphs and the 11 pm
deadline. Proposed dataset scope remains the existing UTF-8 numeric CSV classifier:
selected feature columns, integer class labels and explicit nonempty `train`,
`validation`, `test` splits. Automatic splitting, categorical/text/image pipelines
and LLM fine-tuning are outside tonight's approved scope; no broader format
support is assumed.

The source already implements training, tuning, chat/history, exact action
decisions, verified artifacts and monitoring. It lacks browser upload and a UI.
The [earlier minimal scope](../project/midterm-scope.md#deferred-work) deferred a
custom frontend; approval of this plan adds this narrow desktop deliverable.

A new framework, frontend build system or hosted app would consume time on setup
and connectivity. Use packaged HTML/CSS/JavaScript and the current FastAPI service.
Swagger and a standalone Grafana link do not meet this request. Reuse actual
Grafana panels; avoid implementing a second monitoring/charting system.

Existing Grafana metrics describe **inference observations**, including latency,
accuracy with known labels, errors and declared delays. They do not contain
epoch-by-epoch training loss. Training cards/comparisons use saved validation
metrics from the API; do not fabricate training curves or progress percentages.
Newly trained versions with no inference observations show an honest empty state.

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | Upload a supported CSV, enter/select its columns and save a dataset version; show hash, classes and split counts. | Upload a fresh copy of the supplied fixture through the browser; record 80/20/20 counts and matching file hash. Train successfully from the uploaded file. |
| F2 | Functional | Select/create an MLP model, review training settings, submit once and inspect queued/running/terminal status and metrics. | Real serial worker completes browser-submitted training; refresh preserves the record; artifact download verifies against its recorded hash/size. |
| F3 | Functional | Chat about selected real records, display saved history, and explicitly approve/reject the exact agent proposal. | Real local-model inspection plus one bounded training/tuning proposal; reject submits nothing, approve submits once, repeat decision/replay creates no duplicate. |
| F4 | Functional | Present real embedded Grafana latency, labeled accuracy, and error/declared-delay graphs for a named model version. | Actual browser renders changing panels, version filter and time range; retained Prometheus queries match. Empty/stale/partial observations are explicit. |
| F5 | Functional | Expose validation results, saved Python drafts, artifact downloads and model-version registration. | Review required drafts are readable/copyable and never executed; only eligible completed experiments register versions. |
| N1 | Usability | Polished, readable dashboard at 1440x900 and 1280x800; usable keyboard navigation and clear loading/empty/error states. | Browser screenshots and Jacob's visual review; no page overflow, clipped controls or unreadable graphs. A first-time user completes F1-F3 without API payload editing. |
| N2 | Reliability | Preserve project access, correlation IDs, submission keys, action hashes and uncertainty semantics. | Boundary tests and browser refresh/double-click/disconnect exercises; uncertain submission never appears as a definitive failure or new automatic job. |
| N3 | Delivery | Work as quickly as correctness permits, targeting verified local handoff by 11 pm ET. Advance as soon as each step and its relevant checks are complete. | Passing checks, browser walkthrough, startup instructions, retained evidence, commit and successful push; unfinished criteria remain reported outstanding. |

## Constraints and scope

One presenter on this Ryzen 7/RX 9070 desktop; serial CPU training and one pending
chat request per conversation. Preserve all existing API schemas/defaults,
validation-only selection, training-fitted preprocessing, ownership transactions,
original deadlines, artifact integrity and opt-in live gates. Add upload contracts
without changing existing non-upload dataset registration behavior. No automatic
inference/action retries or generated-code execution.

Use project `demo` for tonight's monitoring, matching the existing Prometheus
scrape and anonymous local Grafana Viewer. API project/key controls continue to
work; other projects must not display the `demo` Grafana panels as their own data.
Keep keys in memory and out of URLs, storage, prompts and screenshots. Loopback
deployment remains the target. Public hosting, accounts/roles, dashboard Kubernetes
upload storage, concurrent training and automatic monitoring producers are deferred.
No dependency changes are planned.

## Design

### Workspace and visual direction

Use a graphite background, layered slate cards, teal primary actions and restrained
amber/red status colors, consistent spacing, legible system typography and simple
SVG icons. Make Upload dataset and Train model obvious. A slim navigation rail
opens Datasets, Runs or Monitoring; the selected dataset/model and service state
stay visible. Keep the agent in a right panel that becomes a drawer at narrower
widths. Show readable names first, with copyable IDs in record details.

Datasets provides file selection, an editable column mapping, format guidance and
server-verified registration results. Runs provides a training form using current
backend defaults, model creation/selection, status/elapsed time, validation metric
cards, comparable-run results and artifact/version actions. Agent messages separate
verified facts, generated interpretation, draft code and pending actions. Provide
visible prompt starters containing selected IDs and explicit budgets; send exactly
the text the user reviews, with no hidden dataset-context assumptions.

### Minimal frontend and deployment

Package static assets under `src/ml_pipeline_pro/dashboard/`, with a small
`dashboard_api.py` mounted in the model/compatibility factories only. Serve
`/dashboard/` and `/dashboard/config.json`; the latter exposes upload availability,
effective file/row limits and the fixed local Grafana origin, never credentials.
The UI calls same-origin `/api/v1` routes with project/key headers. Render untrusted
CSV names, agent output and code as text; use bounded local assets and no CDNs.
Add meaningful CSP/static-serving tests and verify assets in the built wheel/image.

Add `compose.dashboard.yaml` after the existing domain/monitoring/AI overlays.
Reuse the existing desktop project/volumes. Add an uploads volume at
`/app/examples/data/uploads`, writable by the model API's existing non-root user
and read-only in the worker. Prepare ownership in the image. Keep the bundled
`classification.csv`, existing dataset root and artifact mounts intact.
Add `MLPP_DATASET_UPLOAD_ENABLED=false`; enable it only in this overlay. Document
the new setting/routes in `.env.example`, README and a short dashboard guide.

### CSV upload contract and durable files

Add `POST /api/v1/datasets/upload`: raw `text/csv` body; query metadata `name`,
`version`, repeated `feature_columns`, `target_column=target`, `split_column=split`.
Authenticate before reading the body. Validate metadata with existing definitions;
enforce the limit against received bytes independently of `Content-Length`. The upload
cap is the smaller of `MLPP_DATASET_MAX_BYTES` and 10,000,000 bytes; row/class/value
checks reuse [the current loader](../../src/ml_pipeline_pro/datasets.py).
Bound body reception to 30 seconds; return correlated 408 and remove its staging
file if reception expires before publication.
The gateway's new exact upload location has the same 10,000,000-byte outer guard,
request buffering disabled and a correlated JSON 413; other routes retain their
limits. Disabled uploads return correlated 404; wrong media type 415, oversized
body 413, invalid CSV/metadata 422, identity/content conflict 409 and storage
unavailability 503. No raw rows or filesystem paths in errors/logs.

Stage each request privately under its project, validate the complete CSV and
hash it, then publish an immutable `uploads/<project>/<sha256>.csv` before inserting
the existing `DatasetRecord`. Use an atomic create-if-absent hard link on the same
filesystem; an existing destination must match hash/size and is never overwritten.
Prove this on the actual Docker volume; do not silently replace it with overwrite
semantics. Existing `(project, name, version)` uniqueness arbitrates registration:
return 201 on creation, 200 for matching content/column metadata replay, 409 for a
different version payload. Resolve duplicate insert races by scoped reread.

The ordinary registration route must also reject references into another project's
reserved `uploads/` subtree, including path aliases; existing non-upload paths
retain their contract. Remove only the request's staging file on rejection or
disconnect. Preserve a published file after uncertain MongoDB writes: deleting it
could invalidate an accepted record. Unreferenced published files may remain until
a later reviewed cleanup feature. No new collections, record schemas or migrations.

### Chat, submissions and refresh

Reuse [existing chat/history/decision routes](../../src/ml_pipeline_pro/conversation_api.py).
Send a fresh request ID for each intentional turn with the exact expected revision.
Keep bounded project-specific conversation IDs and unresolved request bodies in
browser session storage, excluding keys. Reload retrieves public history; a lost
first response can be checked with the original request ID/body. No conversation
discovery API is added tonight.

Show a proposal's complete arguments/budgets and use its server-supplied
`arguments_hash` for Approve/Reject. Refresh action state before enabling a decision;
respect expired, superseded, running and unknown states. An unknown result offers
an explicit same-action check/retry, never a newly generated action. Direct training
retains its original body/idempotency key until resolved. Disable duplicate clicks;
the server's existing replay/CAS rules remain authoritative across tabs.

Poll active run/history status no more than once every two seconds without overlapping reads;
pause while hidden and stop at terminal state or navigation. Keep the current
90-second desktop client bound for chat. Timeout is an uncertain transport outcome;
check saved state rather than cancelling training or automatically resending.
Display API error codes/correlation IDs with a useful recovery action.
Project changes clear prior records/frames and cancel or ignore late responses;
test that an old project's response cannot populate the new workspace.

### Grafana integration

Provision a separate `mlpp-workspace` dashboard from the existing metric sources,
preserving `mlpp-midterm`. Use model-version filtering and an adjustable time range,
15-second refresh, correct units and a matching dark theme. Embed three panels:
mean/max latency with the 100 ms threshold; labeled accuracy on a separate scale;
errors and explicitly declared seeded-delay counts. Keep window bounds/partial
warnings visible. Give each iframe a title, useful height and an Open in Grafana
link. Do not present an iframe load event as proof of successful graph rendering.

The opt-in overlay sets `GF_SECURITY_ALLOW_EMBEDDING=true` for installed Grafana
12.1.1 and retains its existing local Viewer configuration. Iframes point to the
fixed loopback port 3000; no proxy/auth integration is added. Grafana documents
[panel embedding](https://grafana.com/docs/grafana/latest/visualizations/dashboards/share-dashboards-panels/#share-an-embed)
and [the embedding setting](https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/#allow_embedding);
verify actual pinned-image headers and browser rendering before claiming success.
Use the existing measured producer with a finalized version for the graph rehearsal.
Label its fixture replay and five injected delays; training alone does not generate
these inference observations. No-data states are required, not filled with mock data.

## Acceptance and verification

Jacob approved proceeding without timed checkpoints. The 11 pm ET handoff remains
the target, not a reason to delay earlier completion. Start each available next
step immediately after its dependencies and relevant checks pass. Run independent
checks concurrently where practical; retain the required correctness gates.

1. Package the UI shell, visual layout and working Grafana embeds; inspect a first
   browser preview as soon as it is available.
2. Implement upload, validation, scoped storage and replay/conflict checks; prove
   that the API and worker can use the same uploaded file.
3. Add model selection/creation, training, results and artifact/version actions.
4. Connect agent history, visible context, exact decisions and uncertainty handling.
5. Finish graph filtering, empty/error states and keyboard/layout polish.
6. Complete full checks, the browser journey, live-model/backend rehearsal and
   boundary review. Fix confirmed defects and rerun affected checks immediately.
7. Retain evidence, finish startup documentation, commit and push the verified work.

Protect upload, real training, agent confirmation, embedded graphs and visual
quality. Cut optional animations, advanced filters, extra comparison charts and
convenience controls first. Do not replace core functionality with mocks, drop
assertions, extend AI deadlines or report an incomplete dashboard as finished.

Add upload/API/storage tests reaching real preconditions: exact cap and cap+1,
absent/false length, malformed CSV, conflicting columns, traversal/foreign project,
matching retry, conflicting/concurrent registration, disconnect and ambiguous insert.
Test disabled upload/static/config packaging and unchanged registration behavior.
Use browser interaction checks for request identity/revision, approve/reject,
refresh and unavailable services; HTML text assertions cannot establish these.

Run all [fast gates](../../AGENTS.md#verification-commands), `uv build`, and
the ordinary suite with **both** `MLPP_RUN_INTEGRATION=1` and
`MLPP_RUN_WORKER_INTEGRATION=1`, plus real upload-to-worker cases. Run the serial
isolated suite separately with `MLPP_RUN_RECOVERY_INTEGRATION=1` after image/mount
changes, following [verification setup](../guides/verification.md). No selected
skips count as passes. Keep heavy checks quiescent during live inference.

Browser acceptance on a fresh dataset/version must complete upload, model creation,
training, validation results, verified artifact download, agent inspection,
rejection with no submission, and one explicitly approved bounded proposal.
Refresh restores saved records; a duplicate submission/decision creates no extra
job. Show a saved draft and its review requirement. Then show the measured Grafana
panels for an explicitly named monitored version and an empty new version.
Save screenshots at both viewport sizes, safe API outcomes, query/timing evidence,
source/image/model identifiers and raw failures. If browser automation is
unavailable, Jacob must execute the interaction/visual checklist; HTTP tests alone
do not close it. Obtain human visual/usefulness review, and seek separate boundary
review; disclose unavailable independent review rather than calling self-review
independent. Commit/push each completed major slice after its relevant gates.

## Risks and rollback

Upload publication/metadata uncertainty and Grafana rendering are the largest
new risks; tackle them before chat styling. The deadline leaves little space for
broader dataset adapters. Browser history is limited to this browser's remembered
IDs. Anonymous Grafana remains a local demo configuration, not project-level
multi-user authorization. New versions need real inference samples for graphs.

Stop new submissions and let existing work finish before reverting application
code/overlay. Preserve the uploads volume and its URI/mount in API/worker processes
while imported records exist; removing that mount would strand datasets. Reverting
the UI or embedding option must not delete records, files, artifacts, decisions or
model weights. Existing API/script workflows remain available.

## Human review and approval

Jacob approved on October 19, 2026: "looks good, except for the timed checkpoints,
I dont want you taking longer just to hit a certian checkpoint. work as fast as you
can without making mistakes". This approves the proposed dashboard, upload/API/
storage, supported CSV boundary, agent decisions, Grafana integration and
verification scope, with the timed start/checkpoints/freeze removed. Work proceeds
immediately as dependencies and correctness checks permit, targeting handoff by
11 pm ET or earlier. This revision records that requested exception without
changing functional acceptance. [AGENTS.md](../../AGENTS.md#development-method)
requires renewed review for material design deviations.

Jacob then explicitly requested: "go for it, also give me a quick visual prototype
for the design of it while you work on it". Proceed with implementation and show
the initial browser layout while completing the working controls; label any
prototype-only content clearly until connected to real records.

Jacob reviewed the running design and replied, "Yes—keep this visual direction."
He then said "looks good, use that prototype dashboard" and "keep going." Keep the
prototype's slate/teal styling and right agent panel in the working product. This
is design-direction approval; it does not establish an independently executed
full usability checklist.

## Implementation outcome

Implemented the approved local workspace, retaining the prototype design. The
[guide](../guides/dashboard.md) covers startup, CSV mapping, training, exact agent
decisions, artifacts/versions and embedded monitoring. The
[retained evidence](../evidence/2026-10-19-dashboard/README.md) records safe outcomes,
source/image/model identity, screenshots, raw failures, tests and browser scripts.

Final local gates: locked sync, Ruff lint/format (219 files), dependency check
(109 compatible packages), package build/content inspection, 684 fast cases with
81% rounded coverage, all 75 ordinary cases with both required flags and all ten
serial isolated recovery cases pass without selected skips. Published incoming
application commit `1152aa8` was integrated before the full reruns. Later incoming
`288277e` adds laptop evidence/documentation only and was integrated preserving
both memory-index updates. Python service/test sources are unchanged across the
final service and browser checks; later static/graph refinements have fresh
browser/package verification. No current remote CI result is claimed here.

Real Chrome controls completed fresh CSV upload (80/20/20 rows and matching hash),
model creation, bounded worker training, validation comparison, checkpoint
hash/size verification, version registration, local-model fact inspection,
rejection with no job, one exact approval with one completed run, saved Python
draft/reload and monitoring explanation. Duplicate clicks, malformed accepted
training acknowledgement, lost first chat reply, delayed old-project response,
unavailable service, key storage/reload and keyboard controls were exercised.
The original training key/body and chat request/revision survive uncertainty.

All three actual Grafana canvases show version-filtered measured inference data,
and their values match Prometheus/saved observations. A fresh empty version picks
up later real samples without manual refresh. Explicitly allowing the 15-second
Grafana interval fixes its previously inactive refresh; a separate fenced summary
poll keeps availability/diagnosis controls current without recreating chart frames.
Full-dashboard links preserve the selected version and time range. Screenshots
at 1440x900 and 1280x800 fit without horizontal overflow. The measured fixture
producer declares five injected delays among 20 CPU inferences; these plots do
not establish production performance or training-loss history.

Confirmed defects were fixed at their failing boundaries: upload UTC timestamps
now match BSON milliseconds on exact replay; valid model selector labels and
initial dialog focus pass the accessibility tree/keyboard check; explicit sdist
descendant exclusions remove an ignored nested tool-checkout example. Tests keep
full equality/limit/ownership assertions. No dependency, default AI deadline,
serial worker policy or generated-code execution was added.

Jacob approved the visual direction and requested using this prototype. An
independently executed complete first-time-user checklist and independent boundary
review were unavailable; implementing-assistant review is self-review. Numeric
CSV/explicit split scope, browser-session history discovery, bounded demo-project
monitoring and retained orphan uploads remain as planned. Narrow layouts stack
the agent instead of adding a drawer; approved desktop layouts keep the right
panel. Other formats, laptop rollout and broader course gaps remain outside this
change. Service/data volumes stay available; rollback preserves upload mounts.

Completion commit and origin push are recorded after delivery below.
