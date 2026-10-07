# Provider-independent conversation tools

- Status: awaiting review
- Date: 2026-10-06
- Source baseline: `ec174e575e15c29af7a2ed2eede181a76312b099` / `main`
- Request: follow the roadmap and implement its next conversation tool slice.
- Human reviewer/approval: pending; the roadmap and implementation request do
  not establish review of the design choices below.
- Independent review: not performed. This slice introduces no worker concurrency,
  ownership mechanism, state machine, or rate/size arithmetic. Human design and
  implementation review remain required under the [development method](../development-methodology.md).

## Proposed behavior and purpose

Provide a small Python tool catalog and dispatcher that a future conversation
provider can call to inspect experiments, compare validation results, submit
bounded jobs, and cancel tuning. A trusted application supplies project access
and mutation permission. Tool arguments describe the requested operation, and
results contain API records, evidence references, and correlation IDs.

The first slice is independently usable and testable without a model provider.
It establishes the tool boundary for [milestone 4](../../PLAN.md#implementation-milestones);
provider configuration, natural-language dialogue, `/api/v1/chat`, durable
conversation/action records, and live-provider evaluation follow in a separate
reviewed design. This slice alone does not complete milestone 4.

## Clarification and critique

Source inspection establishes that [tracking routes](../../src/ml_pipeline_pro/api.py)
and [tuning routes](../../src/ml_pipeline_pro/tuning_api.py) already implement the
operations, project reference checks, submission idempotency, comparison rules,
and cancellation. [Project access](../../src/ml_pipeline_pro/access.py) checks
configured keys; development without keys still trusts the selected project.
There is no conversation module, provider dependency, or approved feature plan.

Proposed decisions requiring human review:

- Scope is the tool layer and a deterministic example, before a chat endpoint.
- Use the existing HTTP APIs rather than duplicate their domain logic or call
  route functions directly. API authorization remains the enforcement boundary.
- Mutations require a trusted caller's explicit opt-in; the default is read-only.
  This permission is local execution policy, not a user identity/role system.
- Submission requires explicit budgets; tuning also requires an explicit
  validation objective. The tool does not guess absent required values. Existing
  API defaults for other training/search parameters are documented and reused.
- A trusted caller supplies one stable submission key per intentional action and
  retains it for retries. Provider-generated arguments cannot change that key.

The case against a separate tool layer is that a normal API client already does
this work. Its additional value is a bounded, typed catalog suitable for provider
integration, consistent errors, and evidence-bearing outputs. A lighter option
is documenting HTTP calls only, but that does not establish or test provider tool
validation. Extracting shared domain services is another option; it changes
working application paths and is broader than this initial slice. HTTP adds
serialization and service availability requirements; no latency improvement is
claimed. Provider choice and conversational approval/audit persistence are
intentionally deferred, rather than silently selected here. No additional intent
question is needed if the proposed scope and decisions are approved.

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | Publish named tools with JSON argument schemas and mutation flags; reject unsupported names and extra arguments. | Catalog/schema tests and invalid-call tests; no request dispatched. |
| F2 | Functional | Inspect datasets, models, experiments, tuning jobs, and trials with existing pagination/filter behavior. | Deterministic transport and real-app tests; matching IDs and bounded pages. |
| F3 | Functional | Compare 2-20 distinct succeeded experiments on one dataset using validation F1/accuracy. | Correct winner/evidence; duplicate IDs, mixed datasets, incomplete metrics, and test objectives rejected. |
| F4 | Functional | Submit training/tuning only with explicit budgets, approved mutation permission, and a trusted submission key. | Missing fields/permission/key produce errors before dispatch; valid calls produce API jobs. |
| F5 | Functional | Preserve submission idempotency and tuning cancellation behavior. | Same key/body returns one record; changed body returns conflict; queued/running/terminal cancellation tests. |
| F6 | Functional | Bind project, credentials, API origin, and correlation ID outside tool arguments; preserve API access checks. | Attempts to override context rejected; valid-key foreign references return not-found; invalid keys return forbidden. |
| F7 | Functional | Return public-schema data and record evidence; errors retain safe codes, correlation IDs, and saved job IDs where available. | Public-field filtering, evidence identity checks, queue-error and redaction tests. |
| N1 | Reliability | Provider independence, finite HTTP timeouts, explicit resource cleanup, no automatic retries or redirect following. | Stub execution, timeout/redirect/malformed-response tests, context-manager cleanup checks. |
| N2 | Compatibility | Preserve existing routes, persistence, workers, selection, and locked dependency behavior. | Existing fast gates and real-service workflow/ownership/recovery gates pass. |

## Constraints and scope

No new HTTP route, collection, migration, worker behavior, or environment setting
is included. Job status transitions, ownership fences, serial concurrency,
training artifacts, validation-based selection, and final test evaluation remain
under their existing implementations. The tool cannot register datasets/models,
download artifacts, register versions, cancel standalone experiments, execute
code, or choose arbitrary HTTP methods/URLs. Existing APIs remain independently
usable when tool dispatch fails. There are no performance claims or benchmarks
in this scope.

## Design

Add `tool_schemas.py`, `tools.py`, and `tool_transport.py` under the canonical
application package. A transport protocol permits deterministic stubs. The HTTP
implementation uses an owned `httpx.AsyncClient` with explicit async context
management. Promote the existing `httpx>=0.27,<1` dev constraint into runtime
dependencies and update the lockfile; introduce no provider package.

The allowlisted catalog maps only these names to existing `/api/v1` operations:

| Names | API operations |
| --- | --- |
| `list_datasets`, `get_dataset`, `list_models`, `get_model` | Existing dataset/model GET routes |
| `list_experiments`, `get_experiment`, `compare_experiments` | Existing experiment GET routes and comparison |
| `list_tuning_jobs`, `get_tuning_job`, `list_tuning_trials` | Existing tuning GET routes |
| `create_experiment`, `create_tuning_job`, `cancel_tuning_job` | Existing experiment/tuning submission and tuning cancellation POST routes |

Expose typed call, execution-context, evidence, and success/error result models.
Reuse [request/result schemas](../../src/ml_pipeline_pro/schemas.py) and
[tuning schemas](../../src/ml_pipeline_pro/tuning_schemas.py); tool-specific
argument models forbid extras. Read defaults are `limit=50`, `offset=0`, with
the existing 1-100/nonnegative bounds and experiment status/model filters.
Comparison defaults to `validation_f1`. Submission wrappers require
`config.max_runtime_seconds`; tuning additionally requires `objective_metric`,
`limits.max_trials`, and `limits.max_runtime_seconds`. Remaining schema defaults
are advertised in the catalog. Missing values are validation errors with field
locations for a future provider to turn into clarification questions.

Trusted context binds a validated project ID, optional secret API key, validated
correlation ID, `allow_mutations=False`, and optional submission key. API origin
is constructor configuration: an HTTP(S) origin without userinfo, path, query,
or fragment. Tool arguments cannot supply URLs, headers, credentials, context,
or submission keys. Tool resource IDs are single opaque segments restricted to
letters, digits, underscores, and hyphens (1-128 characters); this accommodates
current UUID records and prevents tool-controlled route traversal. The HTTP
adapter constructs paths from the catalog and sends the bound headers.

The default HTTP timeout is 10 seconds per connect/read/write/pool phase, with
a positive finite constructor override. This is an inactivity/phase timeout,
not an overall job or request deadline. Redirects are refused and calls are not
retried automatically. After an ambiguous submission timeout, the caller retries
the same body/key. Responses are parsed into the existing public result schemas;
private persistence fields never appear in successful tool results.

Success results contain tool name, correlation ID, HTTP status, public data, and
evidence references identifying returned dataset/model/experiment/job/trial IDs.
Comparison identifies every returned experiment and the winner; trial evidence
includes its parent job and experiment. A returned `queued` job means accepted,
not completed training. API errors retain the [error envelope](../../src/ml_pipeline_pro/errors.py)
and safe resource details. Local validation, denied mutation, transport failure,
and invalid upstream payloads have distinct fixed error codes; validation lists
field locations/types without raw input or exception text. Responses and client
representations must not expose keys. Outputs are record evidence, not generated
explanations or durable action audit records.

Add `examples/tools_local.py` using a deterministic stub and document its exact
purpose, runtime use, permission/budget/key behavior, and deferred chat scope in
README and a tool guide. Update roadmap/status to distinguish this slice from
the still-planned conversational interface. Extend existing test fixtures only
where needed; do not weaken assertions or service gates.

## Acceptance and verification

1. Add focused catalog/dispatcher tests with a deterministic scripted provider
   stub. Assert invalid input and missing permission never reach transport (F1,
   F4). Run the example without provider credentials or external services.
2. Exercise the HTTP adapter against the real FastAPI app with existing memory
   repositories, including configured project keys and foreign-project records.
   Cover the full operation catalog, comparison, idempotency, cancellation,
   error/resource/correlation preservation, and public evidence (F2-F7). Negative
   cases must begin with valid authentication and otherwise valid inputs so the
   intended boundary is reached. Use a transport mock for timeout, redirect,
   malformed-body, and cleanup behavior (N1).
3. Add opt-in real-service coverage invoking the tool adapter against a rebuilt
   API: submit/retry one training job and one bounded tuning job, read results
   and trials, and cancel a separate tuning job. Preserve project cleanup and
   existing integration opt-ins. This verifies the HTTP wrapper at the actual
   submission boundary; memory tests alone are insufficient.
4. Run `uv sync --locked --extra training`, Ruff check/format, the non-integration
   suite with coverage, `uv pip check`, and `uv build`. Because tools invoke queue
   and MongoDB-backed mutations, run ordinary integration with both
   `MLPP_RUN_INTEGRATION=1` and `MLPP_RUN_WORKER_INTEGRATION=1`, then the isolated
   serial recovery suite with `MLPP_RUN_RECOVERY_INTEGRATION=1`. Follow the
   [README](../../README.md#run-checks) and [recovery setup](../recovery.md#run-the-suite).
5. Inspect the final diff, validate local documentation links/anchors and example
   syntax, and run `git diff --check`. Save commands, source revision, environment,
   JUnit/raw evidence, warning/skip counts, and requirement mappings. Missing
   services or unavailable checks are gaps, not passes. Update plan outcomes,
   commit the completed slice, and push to `origin`.

Review focuses on context isolation, path construction, missing-budget behavior,
credential/error leakage, idempotent retries, and whether evidence reflects
returned public records. No live-provider evaluation is required for this slice;
no live-provider or full conversational capability will be claimed. If scope
expands to concurrency, state machines, or arithmetic, obtain renewed design
review and seek independent implementation review as required by AGENTS.md.

## Risks and rollback

HTTP adds an availability boundary and may produce an ambiguous submission
outcome; stable caller-owned keys and saved API job IDs are the recovery path.
Explicit tool budgets differ from API convenience defaults, so document this
difference and test it. Mutation permission does not constitute durable audit or
authorization beyond the API key/project contract; integrating a live autonomous
provider requires the later action-approval/audit design. Returned record text
is untrusted data for future provider prompts.

Rollback removes the tool modules, example, guide, and runtime dependency
promotion. No stored-record rollback is needed. Jobs already accepted remain
ordinary API jobs and retain their IDs/artifacts. No existing route or worker
version compatibility changes are planned.

## Human review and approval

- Reviewer: pending.
- Decision/date/reference: pending.
- Approved scope: none yet; proposed scope is F1-F7/N1-N2 and the design above.
- Requested revisions: pending.
- Implementation begins only after explicit review/approval of this written
  plan, per [AGENTS.md](../../AGENTS.md#development-method).

## Implementation outcome

Implementation has not started. Plan preparation at the source baseline above
changed this document and added review links to roadmap/status only.

- Documentation validation: Python 3.11.5 on Windows 10, using
  `.venv/Scripts/python.exe artifacts/conversation-plan-validation/check_plan.py`.
  All 46 local links/anchors passed; generated OpenAPI confirmed all 13 proposed
  tools map to existing operations. No executable examples were added. API and
  tuning source syntax parsed successfully; `git diff --check` passed.
- Raw evidence: local ignored
  `artifacts/conversation-plan-validation/documentation-checks.json`, recording
  baseline, environment, documents, and checked links. The first validation
  harness attempted direct route enumeration, which does not support this
  installed FastAPI's included-router wrappers; using generated OpenAPI corrected
  the inspection without changing application code or acceptance criteria.
- Installed HTTPX 0.28.1 constructor/timeout documentation was inspected for the
  proposed adapter behavior. The tool shell does not currently find `uv` on PATH;
  locate the executable before application verification.
- Application acceptance tests, example execution, runtime lock/build checks,
  real-service gates, and independent implementation review are pending. None
  is claimed for this documentation-only preparation.
- Plan commit/push result: reported in the review handoff and Git history.
