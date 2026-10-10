# Local conversational workflows with LangChain

- Status: approved; implementation in progress
- Date: 2026-10-06
- Last revised: 2026-10-07; human implementation approval recorded
- Source baseline for this revision: `ba6334f7c968f01d544cc513e76b3e65d96c63df` / `main`
- Request: align the next milestone 4 slice with the supplied
  [course requirements](../project/course-requirements.md) and local pre-trained inference.
  The [conversation tools](../guides/workflows.md#conversation-tool-layer) are already delivered.
- Human reviewer/approval: repository user, 2026-10-07, approved this revised
  local LangChain/Ollama plan in this conversation before implementation.
- Independent review: pending for state transitions, ownership predicates,
  retry behavior, and resource arithmetic; no independent review is claimed.

## Proposed behavior and purpose

An engineer asks about experiments, compares validation results, or prepares a
training/tuning submission in a project-scoped conversation. LangChain connects
to a locally served pre-trained language model. The assistant uses the existing
typed tools, asks for missing inputs, guides pipeline steps, and grounds tuning
suggestions in project history and documented practices.
A mutation first produces an exact action for inspection, including identifiers,
expanded defaults, objective, and budgets. A separate authenticated confirmation
executes that saved action without another model call. Dialogue, tool evidence,
decisions, and uncertain outcomes remain inspectable after restart.

This slice addresses course C3 and the conversational-suggestion part of C5.
Separate domain services (C2), monitoring summaries/fixes (C6), LangChain-generated
Python snippets (C7), and Kubernetes/CI/CD (C8) remain required follow-up work in
the [roadmap](../../PLAN.md#implementation-milestones). They are not delivered by
this plan. The managed PyTorch classifier and the pre-trained conversation model
have different roles; training a code language model is not a course requirement.

## Clarification and critique

Source establishes that [access](../../src/ml_pipeline_pro/access.py) uses project
headers and optional project keys, not individual identities/roles. The
[dispatcher](../../src/ml_pipeline_pro/tools.py) already validates 13 tools and
evidence; submission retries and cancellation belong to the existing APIs.
There is no LangChain/model-adapter package, chat route, or dialogue/action collection.

The earlier draft in `ba6334f` proposed OpenAI following an initial clarification.
The user subsequently supplied the course instructions and requested alignment
with the local-model direction discussed in this session. This revision replaces
that unapproved hosted design. Previously selected **per-action confirmation**
and **stored dialogue/action evidence** are retained; detailed contracts and
limits remain proposals for review:

- Confirm each exact mutation separately; a chat message or model-produced
  approval never grants mutation permission. Any authenticated holder of the
  project's key can decide an action; person-level attribution remains unavailable.
- Store secret-redacted dialogue and public tool/action evidence in MongoDB until
  explicit operator deletion. No automatic expiry of audit evidence. This is a
  local-development policy; retention/deletion and identity need a separate design
  before shared use. Redaction cannot identify every possible secret in free text.
- Use one non-streaming request at a time per conversation, one proposed mutation
  per turn, bounded history, and no autonomous mutation/retry or background agent.
- Use a local pre-trained model through LangChain's `ChatOllama`; configure its
  tag explicitly, record its artifact digest/license and runtime version, and
  verify tool calling on the target machine. No paid external API or model key,
  automatic model downloads, cloud fallback, or external tracing is included.
- Preserve existing optional project keys in local development and required keys
  in production. Access and confirmation use trusted host context even when
  inference is local; they do not create individual user identities.

Review must resolve objections to the detailed contracts, desired resource
limits, and whether the acceptance scenarios match the intended workflow.
Clarification answers do not approve implementation of the whole plan.

The existing REST API and tool example already support scripted workflows. A
scripted command interface would be simpler, but would not establish course C3's
pre-trained-model/LangChain integration. Confirmation lets the human validate
interpretation and keeps execution independent of model availability. Local
inference adds installation, memory, and latency constraints; its capability must
be demonstrated rather than assumed from hardware specifications. Keep a small
host-controlled loop and persistence instead of a framework-managed autonomous
agent. LangChain is required by the supplied instructions.

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | Query/compare via existing tools; scope every conversation, action, and referenced record to the authenticated project. | Valid-key foreign-project reads/decisions return not-found; normal query/comparison returns matching records. |
| F2 | Functional | Incomplete or invalid arguments produce missing-input guidance; no submission until complete arguments and exact-action confirmation. | Missing dataset/model, runtime, tuning objective/trials/total budget cases dispatch no mutation; confirmed valid actions submit. |
| F3 | Functional | Persist the expanded immutable action before confirmation; approve/reject only that action and fingerprint, never model-controlled context. | Altered arguments/hash, fabricated approval, stale proposal, and hostile record instructions cannot dispatch. |
| F4 | Functional | Retain dialogue, public evidence, decisions, correlations, and outcomes; reuse one submission key for every retry of an action. | Restart/replay and ambiguous-response cases retain one experiment/job and the original action/key; queue errors retain saved IDs. |
| F5 | Functional | Return actual record facts separately from generated interpretation; reject unsupported citations and preserve job status meanings. | Fabricated IDs/metric facts rejected; queued never becomes completed; comparison uses validation metrics. |
| F6 | Functional | Use LangChain with a real local pre-trained model for guided dialogue and tuning suggestions grounded in recorded history. | Real-model scenarios reach correct validated tools, guide missing pipeline steps, cite relevant prior trials, and require confirmation of any suggestion. |
| N1 | Reliability | Bound model/tool calls, payloads, deadlines, and context; fail safely on model/storage/API errors. | Boundary/timeout/oversize tests, interrupted requests, and storage failure before/after dispatch; direct API still works. |
| N2 | Concurrency | Reject competing/stale turns and duplicate action claims across API processes; external calls never run in retryable transactions. | Real-MongoDB interleavings demonstrate one claimant, stale-write rejection, and same-key retry after lost ownership. |
| N3 | Compatibility | Preserve existing API, tool defaults, worker ownership, serial training, budgets, artifacts, and opt-in gates. | Existing fast, ordinary integration, and isolated recovery suites remain passing without a local model/runtime. |

## Constraints and scope

Reuse the existing tool catalog and HTTP API enforcement boundary. No arbitrary
URLs, code execution, dataset uploads, artifact contents, version registration,
new training defaults, worker concurrency, or changes to selection/recovery.
Keys, headers, project, correlation, origin, and submission key remain host-bound.
Do not infer authorization from persisted dialogue or treat retrieved text as
instructions. Preserve [evidence metadata](../memory/conversation-response-evidence.md)
and [transaction fences](../memory/tuning-parent-fence.md).

Chat requires transaction-capable MongoDB. Model availability is not added to
existing readiness, and disabled/unconfigured chat cannot break direct API startup.
No browser UI, streaming, embeddings, externally hosted inference, or production
capacity/performance claims are included. Service extraction needs its own
reviewed design, retaining the shared transactional tracking/tuning boundary.

## Design

### Interfaces and modules

Add `conversation_schemas.py`, `conversation_store.py`, `conversation_model.py`,
`conversation_service.py`, and `conversation_api.py` under the canonical package.
Define a model protocol with an injected deterministic implementation for tests.
Add locked runtime dependencies on `langchain-core` and `langchain-ollama`; resolve
compatible versions during implementation and record them rather than inventing
version constraints now. Lazy construction avoids model-dependent startup.
Lifespan owns and closes the model adapter and tool HTTP clients. Ollama runs in
a separate host process or container with a retained model volume; it does not
change CPU training dependencies, worker limits, or training concurrency.

All new routes use existing project access, error envelopes, and correlation IDs;
request models forbid extra fields and use existing resource-ID restrictions:

Replays keep original execution correlations in the stored outcome while the
current HTTP envelope/header uses the current request's correlation ID.

| Route | Contract |
| --- | --- |
| `POST /api/v1/chat` | `request_id`, `message`, `expected_revision`, optional `conversation_id`; revision 0 starts a conversation. Return conversation/turn IDs, revision, turn status, message, required-input locations, verified facts/evidence, and optional pending action. |
| `GET /api/v1/conversations/{conversation_id}` | Paginated turns in ascending sequence and conversation revision; `limit=50` (1-100), `offset=0`. Current action states accompany their originating turns. |
| `GET /api/v1/conversations/{conversation_id}/actions/{action_id}` | Public proposal, fingerprint, decision/execution state, safe attempt outcomes and evidence; omit credentials, submission key, and owner tokens. |
| `POST /api/v1/conversations/{conversation_id}/actions/{action_id}/decision` | `decision=approve\|reject` and `arguments_hash`; edits require a new proposal. No model call. Return saved action/outcome, or HTTP 202 for an existing active execution. |

Exact `request_id`/body replay returns the saved turn (202 while running) without
another model call; another body under that ID returns 409
`chat_idempotency_conflict`. Other explicit errors include 409
`conversation_conflict` / `action_conflict`, 404 `conversation_not_found` /
`action_not_found`, 503 `chat_unavailable` / `model_unavailable`, 504
`chat_timeout`, and 422 `chat_limit_exceeded` / `model_invalid_response`.
Existing schema/storage handlers retain their codes. A failed recorded turn is
available through history and same-ID replay; retrying generation needs a new
request ID. Infrastructure errors report saved turn/action IDs when known.

### Local model, inputs, and evidence

Use `ChatOllama` with application-owned context and the existing tool schemas.
Pydantic remains authoritative for required arguments/defaults. Reject malformed
output and multiple tool calls before dispatch; disable automatic retries and
execute tools serially. Use only an explicitly configured loopback or private
Compose/Kubernetes inference endpoint. Start the runtime with cloud features
disabled (`OLLAMA_NO_CLOUD=1`), require a locally installed model artifact, and
never fall back to external inference. Official
[LangChain integration](https://docs.langchain.com/oss/python/integrations/chat/ollama)
and [Ollama local-only configuration](https://docs.ollama.com/faq#how-do-i-disable-ollama-cloud-features)
were checked October 6, 2026. No built-in web/code tools or external tracing.

The host runs read tools serially. On a valid mutating call it stops, persists a
proposal, and returns `awaiting_confirmation`; it never passes model-supplied
permission/context to the dispatcher. Missing fields come from validation, with
no new defaults for required budgets/objectives. The prompt requests clarification
instead of guessing; schema validation cannot prove semantic understanding of
natural language. Human approval of the displayed exact action validates that
interpretation. Prompt evaluations must specifically test unprovided values.

Model context contains redacted user/assistant text and selected public tool
records, never source CSVs, artifact bytes, credentials, or private persistence
fields. Persist dialogue/evidence, not internal model reasoning. History is
bounded to complete turns, with omitted history disclosed. Known configured keys
and connection credentials are redacted before storage, model submission,
response, and logs; extend logging redaction for the model adapter's loggers.

Model-selected citation IDs must belong to successful tool evidence in the
turn. For numeric/status/winner facts, accept references to supported record
fields and have the host render their actual values; never trust model-supplied
values. Generated prose remains interpretation, not independently verified
measurement. Persist the evidence snapshot used for the answer; a later answer
refreshes mutable job state rather than presenting old status as current.
Guide dataset/model selection, budgets, objectives, submission, progress, and
comparison using recorded project evidence. Suggestions may propose supported
search ranges/configuration from prior validation-only outcomes, but cannot invent
missing required budgets/objectives, override worker bounds, or use holdout metrics
to select a configuration. The exact-action review distinguishes suggested values
from user-supplied values. Documented practice guidance carries its source; failed
or absent history is reported rather than fabricated.

### Persistence, claims, and uncertain execution

Use additive `conversations`, `conversation_turns`, and `conversation_actions`
collections with schema version 1. Unique indexes cover `(project_id, request_id)`
and `(project_id, conversation_id, sequence)`; history/action lookups include
project and conversation. No existing collection migration or TTL deletion.

A transaction reserves the turn and advances the matching conversation revision,
recording its owner token and absolute deadline. A second active turn or wrong
revision conflicts. Turn states are `running` followed by `completed`,
`needs_input`, `awaiting_confirmation`, `failed`, or `interrupted`. Reads/new
requests reconcile expired runs to `interrupted`; generation is not resumed
automatically. Every turn completion/proposal write must fence the matching
unexpired conversation owner with a write in the same transaction. Expired owners
cannot publish answers/actions after reconciliation. Model/HTTP calls stay
outside transactions, whose callbacks may run more than once.

An action freezes its expanded arguments, canonical SHA-256 fingerprint, originating
turn/revision, expiry, and one host-generated submission key. Pending proposals
expire after 15 minutes or become superseded by a newer turn. Decision transactions
write the matching conversation revision and action together, resolving races
with new turns. This revision check applies to first approval; retry of an
already approved `unknown` action uses its immutable identity/fingerprint and
attempt claim, even if the conversation has advanced. States are
`pending_confirmation` -> `rejected`, `expired`,
`superseded`, or `running`; `running` -> `succeeded`, `failed`, or `unknown`.
Confirmation records project-key authentication and correlation, not a fabricated
person identity. Rejection cannot revoke an already started action.

Persist approval and an execution-attempt token/deadline before dispatch. Each
completion update checks that token, running state, and unexpired deadline.
Concurrent/replayed approval returns current
state; terminal outcomes never dispatch again. On expired execution, timeout,
transport/malformed response, or upstream 5xx, record `unknown`, preserving safe
errors and any saved job IDs. Storage loss after dispatch can leave `running`;
reconciliation likewise marks uncertainty. Never equate a missing audit result
with a failed submission. An explicit repeat approval of the same fingerprint
may retry `unknown` with the original body/key and a new attempt token. Limit to
three total dispatch attempts; exhaustion requires operator investigation and
must not create a replacement action/key automatically. Definitive validation,
authorization, and other 4xx errors are `failed`.

Training/tuning API idempotency prevents duplicate records even if the old HTTP
call finishes during replay. Cancellation has no submission key: repeat only the
same target using existing API semantics, including terminal-job conflicts.
An error on replay does not prove an earlier uncertain request was never accepted;
retain both attempt outcomes and refresh the referenced record when possible.
Successful action persistence is independent of any later generated explanation.
Clients can inspect its outcome without the language model.

### Configuration and limits

Add these documented settings; limits are proposals, not measured capacity:

| Setting | Default / rule |
| --- | --- |
| `MLPP_CHAT_ENABLED` | `false`; disabled chat routes return `chat_unavailable`. |
| `MLPP_CHAT_BACKEND`, `MLPP_CHAT_MODEL`, `MLPP_CHAT_MODEL_ORIGIN` | Backend `ollama`; no model tag default; model origin `http://127.0.0.1:11434`. Enabled chat requires an installed local artifact and transaction-capable storage. No external-provider key setting. |
| `MLPP_CHAT_API_ORIGIN` | `http://127.0.0.1:8000`; trusted origin validation matches the tool adapter, never request Host/model arguments. |
| `MLPP_CHAT_TIMEOUT_SECONDS`, `MLPP_CHAT_MODEL_TIMEOUT_SECONDS` | 60 overall / 20 per model call; positive finite values, at most 120 / 60, model timeout no greater than overall. These are proposed limits, not measured local latency. |
| `MLPP_CHAT_ACTION_TIMEOUT_SECONDS` | 30 per confirmation dispatch; positive finite, at most 60. Its absolute deadline is also the action attempt's claim expiry. |
| `MLPP_CHAT_MAX_MODEL_CALLS`, `MLPP_CHAT_MAX_TOOL_CALLS`, `MLPP_CHAT_MAX_OUTPUT_TOKENS` | 5 / 4 / 1024; bounded to 1-10 / 1-8 / 128-4096. Count invalid proposals against the call limit. |
| `MLPP_CHAT_CONTEXT_TOKENS` | 8192, bounded to 1024-16384 and the selected model's supported window. Apply an explicit runtime context limit; reject inputs exceeding the verified budget. |

Fixed first-slice caps: 64 KiB new-route request bodies, 8 KiB UTF-8 message text,
64 KiB serialized model context including tools, 128 KiB tool HTTP responses,
256 KiB persisted turn/action payloads, and ten complete prior turns. Check before
dispatch/storage; oversized tool results fail rather than truncate evidence.
Add optional `max_response_bytes=None` to `HttpToolTransport`, preserving its
existing default. Chat supplies the cap and streams/counts decoded response bytes
before JSON parsing. Validate at and above limits, including multibyte text and
chunked/compressed responses. Deadline checks bound local dispatch/commit; cancelling
a local HTTP request cannot undo inference already running or an accepted job.
Load/install the model during setup, not automatically during requests. Document
runtime memory/context settings and measure both cold and warm inference. Model
context includes instructions and tool schemas; verify actual tokenization and
overflow behavior for the chosen artifact rather than silently dropping inputs.

Update README endpoints, `.env.example`, Compose's explicit chat opt-in, tool/chat
guides, roadmap/status, repository contracts, memory fixtures, and CI reports.
Document history/audit retention and local model data flow before enabling the
route. Keep inference resources separate from the existing training worker.

## Acceptance and verification

Implement in reviewable steps: schemas/model contract; durable claims and
replay; bounded read loop; proposals/decisions; API/docs; real-service and opt-in
real local-model evaluations. Run focused tests after each step, retaining failures.

1. Scripted-model/API tests cover queries, validation comparison, missing and
   hallucinated required inputs, complete confirmed training/tuning, rejection,
   cancellation, hostile records, bad citations/facts, and configured-key access
   (F1-F5). Negative cases use valid authentication and otherwise valid data to
   reach the claimed boundary. Do not assert exact model wording.
2. Boundary/failure tests cover call limits, UTF-8/payload caps, SDK retry disabling,
   timeouts, partial responses, redaction, cleanup, and storage loss before/after
   dispatch (N1). Test disabled chat and a failing model alongside working direct
   API routes. Preserve existing assertions; justify any fixture/test changes.
3. Real-MongoDB tests pause competing turn/decision transactions and expired owners,
   verifying one claimant and unchanged stale state (N2). A disposable API process
   is killed after submission acceptance but before audit completion; same-action
   confirmation after restart must retain one job and recover its evidence.
   Ordinary integration uses the scripted model and real API/queue/workers to
   confirm training/tuning, compare results, and cancel tuning (F4, N3).
4. Before the application commit run all repository fast checks, `uv build`, and
   ordinary integration with **both** `MLPP_RUN_INTEGRATION=1` and
   `MLPP_RUN_WORKER_INTEGRATION=1`, following [README setup](../../README.md#run-checks).
   Run the existing isolated recovery suite serially with
   `MLPP_RUN_RECOVERY_INTEGRATION=1` using [recovery setup](../guides/verification.md#run-the-suite).
   Missing services or selected-case skips are verification gaps.
5. Add `evaluations/test_conversation_model.py` outside default `tests/`
   discovery, with a separately registered `local_model_eval` marker, requiring
   `MLPP_RUN_LOCAL_MODEL_EVAL=1`, an installed local artifact, and explicit
   request/token/runtime budgets. No API key, paid call, cloud fallback, or model
   download during tests. Keep it out of ordinary fast/service gates and run in
   a documented local or separately provisioned CI job. Use ten synthetic
   scenarios: read, comparison, missing
   dataset/model, missing runtime, missing tuning objective, missing tuning limits,
   unsupported action, foreign project, hostile record, and evidence/status accuracy.
   Include pipeline guidance and a history-grounded tuning suggestion across
   those scenarios (F6). Each must satisfy action/access/evidence checks; never
   hide failures through retries. A missing runtime/artifact or exceeded budget
   is a reported gap. Live evaluation proposes actions without launching training.
   Reserve each call's output-token allowance, count requests, and enforce an
   overall suite deadline before admitting another call. Record actual resource
   use and limits; do not infer cost or latency from hardware specifications.
   Run explicitly with
   `uv run --locked --extra training pytest evaluations/test_conversation_model.py -m local_model_eval`.
   Document and exercise setup plus this gate on the target machine before
   calling local conversation delivered. Deterministic stubs alone do not meet C3.

Seek independent review of claim transactions, action/turn states, replay,
uncertain outcomes, and byte/token arithmetic; record reviewer, exact submitted
revision, findings, and resolutions. Availability is unestablished; self-review
is not independent review. Retain JUnit, redacted state snapshots/failure traces,
model artifact/tag/digest/license, runtime/package versions, prompt/config hashes,
token counts, context limits, timings and memory observations, source
revision, and image identifiers. Upload retained evidence in CI; ignored local
artifacts alone are not a shared archive. No latency/productivity claims planned.

## Risks and rollback

Model interpretation and redaction remain imperfect; exact-action review,
deterministic boundaries, and adversarial evaluation limit rather than eliminate
those risks. Multi-process races and lost responses need real database/process
evidence, not only memory fakes. Per-turn budgets are not global quotas or a
shared-deployment capacity guarantee. History omission can require fresh inputs.

Disable `MLPP_CHAT_ENABLED` to stop new generation/decisions; keep authenticated
history/action reads available. Let current bounded requests finish or record
uncertainty before reverting code/dependencies. Retain additive collections and
indexes for inspection; never delete jobs/artifacts as rollback. Old binaries
ignore these collections. Never replay pending/unknown actions automatically on
upgrade or rollback; later schema changes require a reviewed migration.

## Human review and approval

- Reviewer/date/decision: repository user, 2026-10-07, approved implementation.
- Clarifications: per-action confirmation and stored dialogue/action evidence,
  October 6, 2026. The user later supplied the course instructions and requested
  relevant documents be corrected; this revises the earlier unapproved OpenAI
  proposal to local pre-trained inference through LangChain.
- Approved scope: routes, local model/runtime/dependencies, project access,
  per-action confirmation, persisted text/evidence and retention, state/claim/retry
  behavior, resource limits, and acceptance gates above.
- Approval reference: user message, "use the previous model instead and i aprove
  the plan". Retain the existing LangChain/ChatOllama direction and native tool
  protocol; the proposed DeepSeek-specific JSON adapter is not adopted. The
  preceding plan did not select an exact model tag; the installed artifact and
  target-machine evaluation remain required. The documented contracts and limits
  are approved; independent review remains outstanding.
- Material changes require plan revision and renewed review under the
  [development method](../project/development-methodology.md#the-five-stage-loop).

## Implementation outcome

Implementation started after the October 7 approval recorded above. Record
source revisions, actual dependency/model
versions, commands/environment, requirement-mapped results/skips/warnings, raw
evidence/archive locations, justified test changes, independent review and
resolutions, deviations/reapproval, durable findings, and completion commit/push.

### Person A foundation, October 8, 2026

The repository user identified themselves as Person A and requested starting that
work. On baseline `f0ec2ad`, branch `person-a/conversation-foundation`, this first
approved implementation step adds strict conversation/model/public-action schemas,
canonical finite-JSON fingerprints, the injected model interface and 13 native
tool descriptions, validated chat settings, and locked LangChain dependencies.
The earlier stash was inspected; schema/interface ideas were reused and corrected,
while its unfinished adapter/store/service/routes were not restored. The stash
remains intact. There is no new design approval or expansion into A2/A3.

Windows/PowerShell, Python 3.11.5, uv 0.12.23: locked training sync, Ruff lint and
format, **292 fast tests** (81 new; 31 integration cases deselected; zero selected
skips), and compatibility of 105 installed packages passed. Both distributions
built. Native tool descriptions passed LangChain compatibility checks while
retaining required budgets and the existing catalog. Dependency versions include
`langchain-core 1.6.9`, `langchain-ollama 1.1.0`, and `ollama 0.6.3`.

Package inspection found a leftover `.uv-cache` included in the first source
archive. Adding root Git/Docker exclusions reduced the rebuilt archive from
1602 to 92 members. Inspection confirmed the new modules in the wheel and no
cache, virtual environment, local tools, `.env`, or artifact paths in the source
archive. uv still emits its general warning about a cache inside the workspace;
the inspected distributions exclude it. Both CI-style dependency audits found
no known vulnerabilities: the runtime audit could not query the CPU-suffixed
PyTorch package, and the separate base-release audit passed with its standard
`--no-deps` advisory warning.

Tests were added for UTF-8 boundaries, trusted-context exclusion, exact decision
shape, host-supplied fact values, one-call/reply output, stable action fingerprints,
native tool descriptions, origins/tags, and setting budgets. A failing dotenv
test established that strict integer fields rejected environment strings; parsing
decimal strings fixed this while preserving boolean/fraction rejection. No
existing assertions, skips, worker limits, or live-service gates changed.

Retained [execution/source/package provenance](../evidence/2026-10-08-conversation-foundation/results.json)
and [raw fast-test output](../evidence/2026-10-08-conversation-foundation/unit.txt)
are checked in. The original JUnit and local outputs are in ignored
`artifacts/conversation-foundation-validation/`; the existing CI will retain its
own unit/integration/recovery reports when run. Remote CI results are not yet
claimed. Documentation links/anchors, the example environment, and whitespace
are validated with this change; final commit/push is recorded in Git history and
the task response.

**Outstanding:** inference adapter/artifact setup, durable dialogue/action claims,
bounded read/confirmation loops, chat routes/lifespan/Compose integration,
real-MongoDB race and process-loss evidence, and live-model evaluation. Docker
Desktop's Linux engine was unavailable, so ordinary integration and isolated
recovery were not run; this slice changes no MongoDB/queue/worker/recovery code.
No clean-checkout setup or model inference is claimed. Independent review is
unavailable in this session; self-review covered schema, origin and byte-limit
arithmetic and does not substitute for Person B/human review. These gaps remain
before A1/course C3/C5 can be called delivered. The approved contracts, defaults,
and acceptance criteria remain unchanged.

### Person A local adapter, October 8, 2026

The repository user requested the next Person A step on baseline `8637173`,
branch `person-a/conversation-foundation`. This continues A1's recorded October 7
approval. The adapter uses the real locked `ChatOllama.bind_tools` and native
protocol against a deterministic HTTP runtime in tests; no unfinished stash code
was restored. It performs lazy local-artifact/capability/context inspection,
returns one proposal or strict final reply, bounds requests/responses/usage and
deadlines, redacts known secrets, disables tracing/cloud-key inheritance,
redirects/proxies/retries, and closes both SDK clients. The host still owns
argument validation, citations, persistence, confirmation, and dispatch.

Token admission receives the actual SDK-normalized HTTP payload and reserves
the full output allowance. A failing exact-payload comparison exposed differences
in pre-SDK messages/tools; moving admission to the HTTP request hook corrected
the mechanism. Raw response hooks reject incomplete replies and malformed native
arguments before SDK normalization. Generation requires an injected,
artifact-specific tokenizer/template counter; no unverified generic estimate or
counter is supplied. Artifact/tokenization and actual overflow evaluation remain
open. This implements the admission interface within the approved limits; it does
not establish a working installed model or change approved API/default contracts.

Windows/PowerShell, Python 3.11.5, uv 0.12.23: locked training sync, Ruff lint,
format (**81 files**), **336 fast tests** (44 added: 37 adapter and seven logging;
31 integration cases deselected; zero selected skips), and compatibility of
105 installed packages passed. Both distributions built; package contents were
inspected for the new adapter and ignored-file exclusions. `langsmith 0.14.5` is
now a direct dependency for the tracing-disable context; no locked package
version changed. LangChain/Ollama versions remain those in the foundation record.
The build retains uv's general workspace-cache warning; inspected archives
exclude caches. An initial editable-build attempt could not contact PyPI under
the sandbox network restriction; cached offline sync succeeded, and the final
standard locked sync and offline package build passed.

Added tests verify lazy inspection/identity, exact native request/tool payloads,
incomplete mutation proposals without execution, partial/multiple/malformed
responses, forged fact values, usage limits, exact UTF-8 context and decoded
response byte boundaries (including gzip/chunks), output-token reservation,
safe errors/no retries, absolute inference timeout/cancellation/cleanup,
redirect/cloud-key/tracing isolation, and configured secret redaction. Existing
assertions and live-service gates were preserved. Logger tests save/restore all
modified logger state. These tests prove adapter boundaries, not natural-language
understanding, citation support, real tokenizer correctness, or model quality.

Retained [source/execution/package provenance](../evidence/2026-10-08-conversation-adapter/results.json)
and [raw fast-test output](../evidence/2026-10-08-conversation-adapter/unit.txt)
are checked in. Local JUnit/output remain in ignored
`artifacts/conversation-adapter-validation/`. The
[SDK finding](../memory/conversation-ollama-boundary.md) records the durable
normalization/credential behavior. README, environment comments, development
guide, roadmap, course checklist and status retain the distinction between this
tested implementation step and outstanding A1/course evidence. Documentation
links/examples and staged whitespace are checked before commit/push; Git history
and the task response record whether the remote received the change.

**Outstanding:** selected installed artifact/license/runtime evidence, verified
tokenizer/template counter, cold/warm resource observations and ten-scenario
real-model evaluation; dialogue/action persistence and claims; host loop and
grounding; decisions and routes/lifespan/Compose integration; MongoDB races and
lost-response/process recovery. The Ollama endpoint at `127.0.0.1:11434` was
unavailable. Docker's daemon pipe was absent, so ordinary integration and isolated
recovery could not run; this slice changes no MongoDB/queue/worker/recovery code.
No live-model inference, clean-checkout setup, remote CI, or course-row closure is
claimed. Independent review is unavailable in this session; self-review covered
payload/token arithmetic, raw SDK normalization, failure paths and cleanup and
is not independent review. Person B/human review remains required for A1.

### Person A durable turn store, October 8, 2026

The user's "go ahead and start next" request continues the October 7 A1 approval
on baseline `813a01d`, branch `person-a/conversation-foundation`. The next slice
implements schema-v1 additive conversation/turn/action collections, unique
request/sequence/action indexes, host-private turn claims, scoped exact-request
replay, optimistic revisions, fenced completion, immutable validated pending
proposals and ascending public history. Expired turns interrupt without automatic
generation replay. Pending proposals expire or are superseded; all child-state
transitions write the parent in the same transaction. Decisions, execution
claims/dispatch and uncertain-outcome recovery are deliberately still pending.
No new public route/configuration default, worker ownership or concurrency change
is introduced. The store is not instantiated by the current API.

Proposals reuse the existing mutating-tool schemas through `validated_proposal`;
missing budgets/objectives remain errors and defaults expand before hashing.
Turn/action IDs and the submission key are allocated outside retryable database
callbacks. Public output omits owner/submission tokens and preserves the original
execution correlation. Redaction and the 256 KiB whole-record cap apply before
storage. The [development guide](../guides/conversation-development.md#durable-turn-and-proposal-storage)
records the private persistence/repository contracts and integration boundaries.

Three new local cases check schema/default authority, trusted-field exclusion,
exact UTF-8 record limits, and invalid deadlines/pagination before database work.
Sixteen new real-MongoDB cases cover scoped replay/restart, keys/redaction,
revision/active-turn conflicts, history, expiry/reconciliation, immutable saved
proposal/key, supersession, rejected stale/forged completions and oversize writes,
two concurrent first-request snapshots, two competing revision snapshots,
old-owner snapshot takeovers for answers/proposals, and a fault-injected
transaction retry retaining identical action IDs/keys. They use actual sessions;
controlled barriers force the claimed interleavings. These are store tests,
not HTTP authentication or chat process-loss evidence. No existing assertion,
skip, opt-in gate or worker limit was weakened. Newly authored epoch assertions
were corrected from an assumed 20 to the actual existing default 30 in source.

A precision regression failed with first/replayed deadlines at `123456` versus
`123000` microseconds. The store now constructs clock/deadline/expiry values at
UTC BSON millisecond precision. The same regression asserts exact deadline and
full pending-proposal replay equality; it passed at the real persistence
boundary. The original effective stored deadline is retained without extension.
The [durable finding](../memory/conversation-store-replay.md) links the mechanism.

Final Windows/PowerShell checks use Python 3.11.5, uv 0.12.23 and the locked
dependencies: training sync, Ruff lint/format (84 files), **339 fast cases**
(47 integration cases deselected), **37 ordinary integration cases** with both
flags, and **ten serial isolated recovery cases**, with zero selected-case skips.
Installed compatibility covers 105 packages; both distributions build and their
contents are inspected. The workspace-cache build warning persists; inspected
archives exclude caches, virtual environments, local tools, `.env` and artifacts.
Docker Desktop was started in the background; isolated ordinary project
`mlpp-conversation` uses ports 18000/37017/16379. Recovery uses its own generated
project and prescribed ports. It was rerun after the precision fix because the
first passing recovery image contained the earlier store source. Retain the
final image/source identity with the raw results, rather than treating that
earlier run as final-source evidence. Existing domain API/worker source is
unchanged. Temporary test databases and recovery stacks are removed by fixtures;
the ordinary test stack is stopped after evidence collection, preserving volumes.

Tracked [execution/source/image/package provenance](../evidence/2026-10-08-conversation-store/results.json)
and raw [fast output](../evidence/2026-10-08-conversation-store/unit.txt),
[ordinary output](../evidence/2026-10-08-conversation-store/integration.txt),
[recovery output](../evidence/2026-10-08-conversation-store/recovery.txt) and
[before-fix precision failure](../evidence/2026-10-08-conversation-store/precision-before.txt)
retain shared evidence. JUnit and additional logs/state snapshots remain under
ignored `artifacts/conversation-store-validation/` and `artifacts/recovery-validation/`;
the tracked reports retain their counts and source hashes. Existing CI retains
its own reports when run; no remote CI result is claimed. Documentation
links/examples, source claims and staged whitespace are checked before commit.

**Outstanding:** the bounded host loop and evidence grounding, exact action
decisions/attempt claims/dispatch, unknown-outcome retries and chat-process-loss
tests, API/lifespan/Compose integration, installed-artifact tokenizer verification
and the live-model evaluation. C3/C5 remain open. Independent review is
unavailable in this session; implementing-assistant self-review covered parent
write predicates, state transitions, retry identity, time/byte bounds and
failure rollback and is not independent review. Person B/human review remains
required. The approved contracts and acceptance criteria remain unchanged;
Git history and the task response record the final commit/push outcome.

### Person A bounded host loop, October 8, 2026

The user's "go next" request continues the approved A1 design on baseline
`8b02465`, branch `person-a/conversation-foundation`. The service now connects
injected model, scoped read transport and durable store: it replays without
generation, bounds serial model/read calls and original deadlines, selects ten
labelled historical pairs, renders supplied current-turn facts, and validates
complete mutation proposals plus referenced records before saving them. A valid
mutation stops at `awaiting_confirmation`; no mutation HTTP call or model-based
approval occurs. No new route, main/lifespan wiring, worker behavior or default
configuration is introduced. API/worker ownership remains with Person B; the
caller owns injected-client cleanup. The stash was not restored.

The loop forces read-only trusted context, strips submission/correlation/private
metadata from model context, redacts known credentials, and omits holdout metrics
and artifact/dependency/URI data from inference. Current-turn successful
snapshots alone support citations/facts; historical status needs a fresh read.
Field resolution supports scalar identity/config/status/validation/comparison
references and rejects absent/private/holdout/ambiguous facts. Parent/source ID
references do not fabricate unfetched parent fields. Interpretation stays
separate from host-rendered values. Schema completeness cannot prove whether
natural-language inputs supplied a budget, and arbitrary generated prose is not
independently verified; prompt evaluation and exact human review remain required.

`HttpToolTransport` adds the reviewed optional `max_response_bytes=None` cap,
preserving existing callers. Chat requires a cap no greater than 128 KiB; decoded
stream/gzip bytes are counted before JSON parsing. The host also enforces context,
normalized snapshot and output-record caps. Oversized records fail as a whole;
a minimal failure explicitly marks evidence not saved. Per-model failures are
recorded safely, overall deadline expiry reconciles interruption, cancellation
propagates, and storage failures expose known saved IDs without claiming failure
of an uncertain commit. Existing shared reply instructions/model error type
move to the protocol module; adapter imports remain compatible and their content
is unchanged. Dependencies/lock versions and public tracking/tuning schemas are
unchanged.

A new regression removed only API status from an otherwise valid experiment
response. Before the fix the host completed with a reconstructed default queued
fact. Per-call response capture now projects validated values onto supplied
fields before context/audit/grounding; the same assertion rejects the unsupported
fact. Exported dispatcher behavior and configuration-default expansion remain
unchanged. The [durable finding](../memory/conversation-supplied-facts.md) records
this distinction. Another new oversized-output case exposed reliance on the
store's cap in a memory substitute; a host publication guard now fails before
storage and saves the explicit minimal failure. Test fixtures were corrected to
the existing `DatasetRecord.num_classes` contract rather than changing schemas.
Existing assertions and gates were preserved.

Windows/PowerShell, Python 3.11.5, uv 0.12.23: locked training sync, Ruff lint,
format (91 files), **381 fast tests**, **41 ordinary integration cases** with
both flags, and **ten serial recovery cases** passed with zero selected skips.
There are 42 new fast cases (32 service, four grounding, six transport) and four
new real-service cases. Scripted cases cover queued versus completed facts,
validation comparison, unsupported/absent/cross-turn facts, exact replay,
missing budgets/objectives, proposal preflight/foreign references, call/context/
record limits, malformed output/usage, timeouts/cancellation/storage failure,
hostile data, secret/trace redaction and disabled generation. Stream cases check
exact UTF-8 decoded boundaries and gzip/chunk cleanup. Real cases use scoped HTTP
and real MongoDB for read/restart replay, a history-based saved proposal without
a new job, actual deadline interruption, and direct API availability after model
failure. Historical validation values in that scenario are labelled synthetic
fixtures, not newly measured training quality or model reasoning.

Installed compatibility covers 105 packages; both distributions build, and
contents are inspected for the new modules/ignored-file exclusions. The uv
workspace-cache warning remains; inspected archives exclude caches, local tools,
virtual environments, `.env` and artifacts. Ordinary project `mlpp-conversation`
uses ports 18000/37017/16379; recovery has its own generated stack/ports. Image
identities and loop/grounding/transport/worker hashes match tested source.
Fixtures remove generated metadata/recovery stacks; the ordinary test stack is
stopped after collection with volumes preserved. No concurrent training, new
paid model service, language-model download or external tracing was introduced.

Tracked [execution/source/image/package provenance](../evidence/2026-10-08-conversation-loop/results.json),
[fast output](../evidence/2026-10-08-conversation-loop/unit.txt),
[ordinary output](../evidence/2026-10-08-conversation-loop/integration.txt),
[recovery output](../evidence/2026-10-08-conversation-loop/recovery.txt),
[before-fix fact failure](../evidence/2026-10-08-conversation-loop/default-fact-before.txt)
and JUnit/recovery-state archive retain shared evidence. Additional local output
remains in ignored `artifacts/conversation-loop-validation/` and recovery
directories. Documentation links/examples, source claims and staged whitespace
are checked before commit/push. Remote CI and clean-checkout onboarding are not
claimed.

**Outstanding:** exact action decisions/execution claims/dispatch and unknown
outcome recovery; chat routes/lifespan/Compose integration; additional decision
races and chat-process loss; installed-artifact tokenizer/overflow verification,
resource observations and ten-scenario real-model evaluation. C3/C5 remain open.
Independent review is unavailable in this session; implementing-assistant
self-review covers resource arithmetic, source-field provenance, project/permission
binding, state/failure paths and cleanup and is not independent review. Person B/
human review remains required. Approved contracts/acceptance criteria are retained;
Git history and the task response record the final commit/push outcome.

Original draft preparation checks (October 6, 2026, original baseline `32df698`,
Windows/PowerShell):
local Markdown validation passed for 17 documents and 144 links/anchors; the two
proposed shell commands parsed; all nine template sections are present with no
placeholders. Source inspection confirmed the 13-tool baseline and absent
conversation modules/provider dependencies. Official provider pages were opened
and checked, and `git diff --check` passed. These are documentation checks;
application, real-service, and live-provider acceptance evidence was pending.
Those counts describe the original draft, not validation of this revision.

### Person A confirmed actions and HTTP integration, October 8, 2026

The user's request to finish Person A continues the existing October 7 A1
approval on source baseline `2b9dfaf`, branch `person-a/conversation-foundation`.
The separately pushed A2-A4 designs await human review; they do not expand A1.

Added exact project-scoped approval/rejection, transactional action claims and
parent-fenced completion; dispatch occurs only after the claim commits and never
inside a retryable transaction. Active and terminal decision replays dispatch
nothing. Pending expiry/supersession conflicts with approval. Explicit retry of
an approved unknown action retains its original body/key after later turns, with
three total attempts. Expired owners, malformed/transport responses and upstream
5xx retain uncertainty; later 4xx cannot erase an earlier uncertain submission.
Queue errors retain accepted IDs and a scoped refresh when available. No model
call participates in confirmation, cancellation or outcome inspection.

The four approved routes now use existing project authentication, schemas,
error/correlation handling and paginated history. Disabled chat rejects generation
and decisions while keeping authenticated audit reads. Running replays return
202; the HTTP correlation remains current while saved executions remain original.
The app lifespan closes model/HTTP clients without contacting inference at
construction or adding model availability to readiness. Chunked chat/decision
bodies are capped before JSON parsing. The app integration patch is available
for Person B's later service extraction; no worker concurrency change is included.
A real locked-SDK/mock-HTTP regression reproduced unprepared generation at the
new route boundary. Native artifact preparation is now lazy inside generation;
safe provenance is refreshed even on generation failure. The unchanged new
assertion verifies a completed turn with the inspected digest and no startup
requests. [Before-fix evidence](../evidence/2026-10-08-conversation-actions/lazy-model-before.txt)
is retained; the counter/runtime values in this test are fixtures.

Controlled MongoDB snapshots reproduced late action completion at natural expiry
without takeover: a deadline predicate captured before an await was reused at the
final write. The same mechanism was confirmed in existing turn completion.
Both final mutations now rebuild their deadline predicates using current time.
Retained [action failure](../evidence/2026-10-08-conversation-actions/expired-completion-before.txt)
and [turn failure](../evidence/2026-10-08-conversation-actions/expired-turn-before.txt)
show the unchanged failing assertions; the same tests pass after correction.
An additional [timeout regression](../evidence/2026-10-08-conversation-actions/refresh-timeout-before.txt)
confirmed that optional record refresh could consume the deadline before saving
a known accepted ID. Refresh now uses one dependency-timeout allowance only when
two remain, reserving time for audit persistence; missing refresh is explicit.
The unchanged new assertion now reaches and verifies saved accepted-ID evidence.
The [durable finding](../memory/conversation-action-uncertainty.md) records this
mechanism and uncertain-response behavior.

New tests cover exact hashes, valid foreign-project access, redaction, replay,
three-attempt exhaustion, later-4xx uncertainty, forced competing approvals/new
turns, expired completion snapshots and preserved active turn ownership. The
real-service gate confirms training, tuning and queued cancellation through the
API. A disposable chat API process pauses after real domain acceptance, is killed,
then restarted after natural attempt expiry; same-action confirmation resolves
to exactly one job with the original key. New HTTP tests cover disabled audit
reads, body streaming, project keys, 202 replay and client cleanup. Existing
assertions/gates remain unchanged; one new existing-store regression verifies
the confirmed deadline mechanism. The cancellation fixture is deliberately
unqueued to test cancellation independently of worker timing.

The opt-in ten-scenario live-model gate is now supplied outside default test
discovery, with a registered marker, explicit installed tag/counter factory,
50-call/context-reservation budget and one 600-second suite deadline. It retains
safe turns, usage/timing, source/counter/model identity and resource observations;
checks compare counter counts with actual runtime prompt usage. Four deterministic
harness regressions cover request/deadline admission, counter mismatch and missing
total tuning budget versus a supplied per-trial runtime. The gate is skipped here
because no installed artifact/counter was selected; this is not acceptance evidence.

Final verification passed on Windows/Python 3.11.5 with the locked dependencies:
402 fast cases (76% host coverage), 56 ordinary integration cases with both flags,
ten isolated recovery cases run serially, and 27 targeted store/action boundary
cases. These selected gates had zero failures/skips. Locked sync, Ruff lint/format,
dependency compatibility and source/wheel builds passed. The separate live gate
had one opt-in skip representing the unexecuted ten-scenario session; this remains
a gap. Initial restricted-network package builds failed fetching build metadata;
authorized builds succeeded and the final cache is outside the source tree.

[Source/config/package/image manifests and native exit codes](../evidence/2026-10-08-conversation-actions/results.json),
[fast output](../evidence/2026-10-08-conversation-actions/unit.txt),
[ordinary output](../evidence/2026-10-08-conversation-actions/integration.txt),
[recovery output](../evidence/2026-10-08-conversation-actions/recovery.txt),
JUnit and the [recovery state/log archive](../evidence/2026-10-08-conversation-actions/recovery-state-logs.tar.gz)
retain shared evidence. Final records distinguish current-source verification
from the earlier historical runs. Documentation links/examples and endpoint
inventory were checked; the current wheel contains 36 canonical application
modules and its source archive excludes private/cache/ignored artifact paths.
Remote CI is not claimed. Authentication provenance now records project-key mode
only when keys are enforced; its regression explicitly configures the key fixture
and separately checks optional-key local mode without weakening the assertion.
An [oversized-audit regression](../evidence/2026-10-08-conversation-actions/oversized-id-before.txt)
also preserves known accepted IDs in the minimal explicit unknown result;
the unchanged new assertion passes after the before-fix failure.

**Outstanding:** selected installed artifact and verified tokenizer/template
counter, opt-in ten-scenario real-model evaluation, resource observations and
clean-checkout onboarding. Local `127.0.0.1:11434/api/tags` did not respond within
two seconds, including an unsandboxed probe; no runtime/model was installed or
downloaded here. The default Ollama adapter still fails closed without a verified
counter. C3/C5 remain open. Independent review is unavailable in this session;
implementing-assistant review is self-review, covering states, deadline predicates,
project/permission binding, private keys, uncertain outcomes and payload limits.
Person B/human review remains required. Commit/push outcome is recorded in Git
and the task response after final verification.

### Person A continuation review, October 9, 2026

The user's request to continue Person A resumes the approved A1 work on
`9675b28`. The action/routes slice was still uncommitted. Source inspection covered
exact fingerprints, project/authentication binding, transaction parent writes,
expiry predicates, attempt exhaustion, same-key replay, uncertain outcomes,
client cleanup and the live-evaluation admission arithmetic. This is implementing-
assistant self-review; no independent reviewer is available in this session.
Independent review remains outstanding before closing A1.

All 78 source/test/evaluation file hashes and 22 raw evidence hashes matched the
October 8 action-slice manifest. The repository review reran locked sync, Ruff
lint/format, the full fast suite (402 passed, 66 integration/recovery cases
deselected, 76% coverage), and dependency compatibility successfully. The saved
56 ordinary integration and ten serial recovery passes apply to the unchanged
application/test files; those suites were not rerun during this continuation.
No assertions, skips or gates changed.

Forward-looking guide text, the example environment comment and roadmap counts
were corrected to match the implemented routes/actions and retained evidence.
The earlier manifest remains historical, including its original configuration
and package hashes; only documentation and the `.env.example` comment changed
after source verification. A new offline source/wheel build passed. Its inside-
source cache warning was checked against the archive: private/cache/ignored
paths are absent and the wheel includes all 36 canonical application modules.
Documentation checks validated 25 documents, 283 local links/anchors, two Python
examples, 21 PowerShell examples and whitespace before this outcome addition;
the final link/whitespace checks are repeated before commit.

Staged-file verification found Git's LF normalization changed three raw evidence
files (`format.txt`, `images.txt`, `lint.txt`) from their recorded hashes.
This action-slice evidence folder now disables text normalization in
`.gitattributes`, keeping execution evidence byte-for-byte. Its native CRLF line
endings are recognized by whitespace checks; other whitespace rules remain
enabled and earlier evidence folders retain their existing attributes.
Source hashes already matched the staged files;
all raw evidence and archive hashes are checked again after restaging.

The target has 31.1 GiB RAM, an AMD Ryzen 7 7800X3D CPU and an AMD Radeon RX 9070;
these observations do not establish inference capacity or latency. The default
Ollama origin remains unavailable. Artifact selection, a verified counter and
retained real-model execution/onboarding remain pending; no model download or
course-row closure is claimed. A2-A4 remain under their separately written plans
and have no recorded design approval.

Course-alignment documentation checks (October 6-7, 2026, baseline `ba6334f`,
Windows/PowerShell): 19 Markdown documents and 192 local links/anchors validated;
two Python examples and nine PowerShell commands/examples parsed. Source checks
matched all 21 current API operations to README, the single-API/13-tool baseline,
and absent LangChain/model modules. All nine supplied instructions have checklist
rows. The implemented tool plan's original approval, design, criteria, and results
and the historical ownership/recovery/tool validation sections are preserved.
Raw local check output/provenance is in ignored
`artifacts/course-docs-alignment-validation/`; final staged whitespace checks and
commit/push are reported with this documentation change. No application or local
inference acceptance run is claimed.

### Person A selected tokenizer and failed live evaluation, October 9, 2026

The user's continuation request resumes the approved A1 artifact-selection and
token-admission work on `a4bdbe4`, preserving the completed documentation
reorganization. The standalone Ollama 0.40.2 runtime and explicit Qwen 2.5 7B/14B
Q4_K_M artifacts were installed under ignored `.tools/local-model-setup/`.
Installed metadata retains artifact/weight digests, Apache 2.0 licenses,
runtime/template identity and observed Vulkan GPU allocation. No weights or
tokenizer data enter Git, the wheel or the containers.

The new explicit counter verifies the runtime/artifact/template identities and
local tokenizer checksum, renders the exact Go chat/tool template and reserves
the full output allowance before HTTP inference. All 151665 available tokenizer
entries and 151387 merges match both installed GGUFs; 399 padded entries are
unused. Eight stock-profile probes matched exact rendered prompts and runtime
prompt counts. A real SDK request admitted 7680 input plus 512 reserved output
at context 8192; 7681 input failed before any HTTP inference request.
The explicit API factory inspects and loads the counter lazily within the first
bounded generation call, preserving offline startup, direct API and audit reads.
The application's default adapter still fails closed without a supplied counter.

Source and runtime render inspection exposed a pinned-runtime defect: the stock
template prints a Go function struct where it advertises JSON. Explicit local
template profiles JSON-encode signatures and request one native call while
retaining the pre-trained weights and native tool protocol. These profiles are
reproducible from installed weights; the setup script rejects unexpected source
or occupied target identities. Profile recreation produced the same 14B digest.

All six live attempts are retained, including the initial pre-inference identity
failure. Subsequent stock 7B prompt revisions passed 1, 2 and 5 of the ten
scenarios. The explicit 7B template profile passed 6; the 14B profile with explicit
per-trial/total-budget guidance passed 3. **Every acceptance attempt failed.**
Observed failures include prose appended to JSON, invalid citation structures,
missing proposals and incorrect runtime budgets. The original ten scenarios,
strict parser and assertions remain unchanged; no repair/extraction/retry hides
failures. The 14B cold setup observation was one output token under an explicit
120-second setup deadline, not a quality result. Saved timing/GPU allocation
values do not establish capacity or latency guarantees.

Final host verification: 420 fast cases, 56 ordinary integration cases with both
flags and ten serial isolated recovery cases passed with zero failures/skips.
Locked sync, Ruff lint/format, dependency compatibility and package builds passed.
The wheel contains 37 canonical application modules; source archives exclude
private/cache/model paths. Eighteen new regressions cover actual retained stock
rendering, wrong profile/tokenizer identities, bounded tokenizer reads,
unsupported requests and lazy lifecycle failures. Their assertions implement
admission/startup requirements; no existing test was weakened.

[The shared manifest](../evidence/2026-10-09-qwen-counter/results.json) links a
byte-preserving raw archive containing every live JSON/JUnit result, intermediate
source hashes, runtime/license/profile observations, tokenizer/boundary probes,
current source/package manifests and passing service/recovery evidence.
Attempt 1's shell wrapper returned zero while pytest failed; its native exit was
not captured. Later failures returned native exit 1. Attempt 6 retains instruction
and factory hashes but lacks the full counter snapshot before the later lazy-API
wrapper addition; the final snapshot applies to the passing host gates.
These provenance limits are explicit in the manifest.

Documentation verification passed for 32 Markdown documents, 318 local
links/anchors, two Python examples, 29 PowerShell examples and the source-backed
25-operation API inventory. Staged whitespace and archive/source hashes are
checked before committing. Commit and push outcomes are recorded in Git and the
completion handoff.

**Outstanding:** A1/F6 real-model quality acceptance, independent review of
rendering/resource arithmetic and existing state transitions, human model-quality
review, and complete clean-checkout onboarding. C3/C5 stay open. Review performed
here is implementing-assistant self-review; no independent reviewer is available.
The [runtime memory](../memory/conversation-qwen-runtime.md) records the confirmed
mechanism and rejected approaches. A typed completion tool remains an unimplemented
design hypothesis requiring renewed review. A2-A4 remain pending approval.

The [typed completion follow-up](2026-10-09-conversation-typed-completion-plan.md)
defines that bounded protocol experiment and preserves the original semantic
acceptance gates. Its approval remains pending; it has not been implemented.

### Person A approved typed completion, October 10, 2026

The user approved the [typed-completion follow-up](2026-10-09-conversation-typed-completion-plan.md)
on October 10. Its implementation uses one adapter-only completion function and
the unchanged public reply contract, includes all 14 native schemas in admission
and provenance, and preserves the public 13-domain-tool catalog and confirmation
boundaries. Its outcome records the new SDK/host/real-store checks, exact runtime
token boundary and original ten-scenario live evaluation.

The selected 7B profile passed only three scenarios; acceptance failed. Saved
turns show wrong per-trial budgets and inappropriate reuse of missing limits.
A separate diagnostic observed repeated native calls ending at the output limit.
No action was dispatched and no acceptance assertion or budget changed. The
October 9 approval-pending statement above remains historical; the new protocol
is approved and implemented. A1/C3/C5, independent review, human model-quality
review and complete clean-checkout onboarding remain outstanding. A2-A4 are not
approved by this protocol decision.
