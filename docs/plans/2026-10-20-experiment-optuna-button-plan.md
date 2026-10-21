# Run Optuna trials from an experiment

- Status: superseded by the user's narrower prompt-only request
- Date: 2026-10-20
- Source baseline: `fd36e79` on `main`; fetched origin, no incoming commits
- Request: a button on the experiment for doing trials with “opfana”
- Human reviewer/approval: pending; interpret the requested engine as Optuna
- Independent review: availability unknown; submission recovery changes need review

## October 20 scope correction

Jacob clarified: "i just want it to give the agent a prompt with all the info
filled in". The direct-submission design below is not approved or implemented.
Instead, add a local **Plan Optuna trials** prompt starter alongside the existing
experiment inspection prompt. It fills and focuses the editable agent message
box with the source experiment's IDs/config and explicit existing tuning-contract
settings (five trials, 300 seconds, serial, validation F1 and default search ranges).
The user sends the message and reviews any agent proposal through the existing
workflow. Show it for MLP only, consistent with current tuning support.

This follows the compressed loop for a local UI edit under the user's clarified
scope: no new submission flow, API, persistence, ownership or execution behavior.
Verify the browser click against saved experiment values rather than current
training selection, confirm no request is sent on click, and run the fast gates.
The remainder of this document preserves the abandoned proposal for context.

### Prompt-only implementation outcome

- Added the MLP experiment-detail prompt button in `dashboard/workspace.js` and
  documented it in the dashboard guide. Source base: `034b67b`.
- Verification: locked training-extra sync checked 121 packages; Ruff lint and
  format pass; existing training environment's `python -m pytest -m "not
  integration" --cov` passes 855 tests, 134 deselected, 79% overall coverage.
  Sync subsequently confirmed the installed environment already matched the lock.
  `uv pip check` passes for 121 packages; `git diff --check` passes.
- Chrome headless / Playwright 1.64.0 loaded the actual local dashboard modules
  with fixture records: clicking uses source IDs and the complete saved config
  despite another selected model/dataset, fills all search settings, focuses an
  editable message, sends no mutation request and reports no browser errors.
  Logistic details omit the unsupported tuning starter. Local harness:
  `artifacts/verify_optuna_prompt.py`; no live AI invocation or training run.
- No existing tests changed and no new permanent tests added for this local edit.
  Implementing assistant reviewed the diff; no concurrency/state-machine change
  or independent review is claimed. Existing agent approval flow is reused.
- Commit/push result is reported in the task handoff. The abandoned full-search
  acceptance criteria below do not describe this clarified prompt-only change.

### Local dashboard deployment follow-up

October 20: Jacob reported the button missing. An HTTP read confirmed the running
`/dashboard/workspace.js` returned 200 but lacked `Plan Optuna trials`; the source
change had been pushed as `edaac96` without rebuilding the local app.

Fetched origin (no incoming changes), built `model-api` and recreated only that
service with `--no-build --no-deps --wait --wait-timeout 120`, using the running
container's exact Compose project/files: `mlpp-rx9070-walkthrough-20261014`, base,
services, monitoring, dashboard and OpenAI overlays. Existing volume configuration
was retained; no dataset/model mutation or AI request was made. Build and healthy
startup passed. Other services were not recreated.

The gateway now returns the updated asset and readiness 200. A headless Chrome /
Playwright 1.64.0 check opened the actual dashboard and experiment `e25`, clicked
the visible button, and verified the filled model/dataset/config against that
saved experiment, zero POST requests and zero browser errors. Local harness and
screenshot: `artifacts/verify_deployed_optuna_button.py` and
`artifacts/optuna-button-deployed.png`. A first browser attempt did not find an MLP
record; the subsequent run completed the click checks. No application source changed
in this deployment follow-up; the preceding fast gate remains the source validation.

## Proposed behavior and purpose

Add **Run Optuna trials** to MLP experiment details in the existing dashboard.
Open a settings dialog, then show a complete review before submitting a bounded
search. Use the experiment's saved model, dataset and base training configuration,
regardless of the current training-form selection. Starting a search creates new
trial experiments; it does not resume or modify the source experiment.

## Clarification and critique

Optuna TPE search, submission keys, serial workers, trial inspection and cancellation
already exist. The missing piece is direct manual admission from experiment details.
Reuse those mechanisms rather than introduce another tuning service or an AI call.
This addresses course requirement C5 without changing its backend acceptance claims.

Proposed scope for human review: MLP only, all saved experiment statuses eligible,
validation F1 objective, editable trial count, runtime budget and search ranges.
Logistic details explain that tuning is unavailable, matching the existing API.
Adding logistic tuning would require a separate backend design; it is excluded here.
No remaining source question requires a new API or persistence contract.

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | MLP details offer the button; logistic details clearly explain the limitation. | Browser exercises both algorithms. |
| F2 | Functional | Settings use the source model/dataset/config; review shows exact settings, validation objective and serial execution before submission. Back submits nothing. | Browser captures reviewed arguments and checks submitted body after switching training selection. |
| F3 | Functional | Accepted searches appear in tuning jobs; inspect saved trials, states and best validation result, with a link to the winner when available. | Real worker search completes and displayed results match saved API records. |
| N1 | Reliability | Double-clicks, uncertain responses and reload reuse one frozen body/key per project, with explicit same-request recovery. | Browser lost-response/reload replay creates exactly one tuning job; project switch cannot display stale results. |
| N2 | Compatibility | Preserve existing API, serial scheduling, ownership fencing, deadlines and validation-only winner selection. | Existing fast checks and affected ordinary integration gates pass. |

## Constraints and scope

Use packaged dashboard JavaScript/HTML/CSS and existing `/api/v1/tuning-jobs`
routes. No dependencies, API/schema changes, worker changes, migrations, new
parallelism or live AI calls. API keys remain in memory; stored recovery arguments
contain no credentials. The test split is evaluated only for the selected winner
through the existing execution flow. Do not modify the original run or artifacts.

## Design

Use a dedicated tuning UI module wired into experiment details and workspace
refresh/session restoration. Dialog defaults match the existing tuning contract:
five trials, 300-second overall budget, sampler seed 42, learning rate
0.0001–0.05 logarithmically sampled, batch sizes 8/16/32, and hidden units
8–64 in steps of 8. Base config comes from the source experiment, including its
per-trial runtime limit and training seed. Show both runtime limits distinctly.
Allow editing all search ranges and sampler seed within current API constraints.
Validate bounds, distinct batch choices and hidden-unit step alignment before review.

Freeze exact arguments and a generated submission key before POST; block replacement
submissions while unresolved. Preserve them in project-scoped session storage.
Transport failures, invalid success bodies and uncertain server errors keep recovery
available; an explicit retry uses the identical request/key. A definitive initial
client rejection reports the API error. A rejection after an uncertain attempt
does not erase the unresolved identity. Project changes during a mutation remain
blocked using the dashboard's existing mutation guard. Workspace refresh polls
saved tuning status, retaining cancellation and trial inspection.

Update the dashboard guide and tuning-panel description to cover manual searches.

## Acceptance and verification

Run the locked training-extra Ruff lint/format, non-integration pytest with coverage,
and `uv pip check` commands from AGENTS.md. Validate JavaScript syntax and exercise
dialogs, cancel-before-submit, algorithm eligibility, configuration binding, error
reporting and exact replay in a browser. Use a disposable real-service project and
small existing classification fixture for a three-trial serial worker search;
retain request/result evidence and screenshots. No performance claim is planned.

Run affected tuning and experiment ordinary integration checks with both
`MLPP_RUN_INTEGRATION=1` and `MLPP_RUN_WORKER_INTEGRATION=1` using the verification
guide. No recovery-worker implementation changes are proposed; if those become
necessary, revise this plan and include the isolated recovery gate. Seek independent
review of the browser submission/recovery state transitions; disclose unavailable
review. Check documentation links and `git diff --check`, fetch again, integrate
incoming work if applicable, then commit and push.

## Risks and rollback

The source experiment may reference a deleted record, or dispatch may fail after
admission. Surface actual API errors and preserve uncertain submission identity;
never silently create a replacement search. Small runtime budgets can finish with
fewer trials or no final test evaluation; display saved outcomes without promises.
Rollback removes UI changes while retaining accepted searches and backend records.

## Human review and approval

Pending Jacob's explicit approval of this written scope, including the Optuna
interpretation, MLP limitation and proposed settings. Implementation has not begun.

## Implementation outcome

Pending approval and implementation. Plan-only validation: source inspection,
local documentation link checks and `git diff --check`; no application gate claimed.
