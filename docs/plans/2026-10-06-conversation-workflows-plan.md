# Provider-backed conversational workflows

- Status: awaiting review; implementation has not started
- Date: 2026-10-06
- Source baseline: `32df698f9bf8974268019a9d28c8608cbc344090` / `main`
- Request: write the next milestone 4 implementation plan after the delivered
  [conversation tools](../conversation-tools.md).
- Human reviewer/approval: pending. The request to write this plan does not
  approve its implementation or extend the earlier tool-layer approval.
- Independent review: pending for state transitions, ownership predicates,
  retry behavior, and resource arithmetic; no independent review is claimed.

## Proposed behavior and purpose

An engineer asks about experiments, compares validation results, or prepares a
training/tuning submission in a project-scoped conversation. The assistant uses
the existing typed tools, asks for missing inputs, and returns supporting records.
A mutation first produces an exact action for inspection, including identifiers,
expanded defaults, objective, and budgets. A separate authenticated confirmation
executes that saved action without another provider call. Dialogue, tool evidence,
decisions, and uncertain outcomes remain inspectable after restart.

This is the next [milestone 4 slice](../../PLAN.md#implementation-milestones),
covering conversation through confirmed submission/cancellation. Its acceptance
does not establish monitoring, generated-code execution, or shared deployment.

## Clarification and critique

Source establishes that [access](../../src/ml_pipeline_pro/access.py) uses project
headers and optional project keys, not individual identities/roles. The
[dispatcher](../../src/ml_pipeline_pro/tools.py) already validates 13 tools and
evidence; submission retries and cancellation belong to the existing APIs.
There is no provider package, chat route, or dialogue/action collection.

The user selected **OpenAI**, **confirmation of each action**, and **stored
dialogue/action evidence** in the planning clarifications. Detailed contracts
and limits below remain proposals for review:

- Confirm each exact mutation separately; a chat message or model-produced
  approval never grants mutation permission. Any authenticated holder of the
  project's key can decide an action; person-level attribution remains unavailable.
- Store secret-redacted dialogue and public tool/action evidence in MongoDB until
  explicit operator deletion. No automatic expiry of audit evidence. This is a
  local-development policy; retention/deletion and identity need a separate design
  before shared use. Redaction cannot identify every possible secret in free text.
- Use one non-streaming request at a time per conversation, one proposed mutation
  per turn, bounded history, and no autonomous mutation/retry or background agent.
- Require an explicitly configured model ID; do not guess the user's account
  access, model choice, pricing, or credentials. Live use also requires project
  keys, including development, because the route invokes a paid external service.

Review must resolve objections to the detailed contracts, desired resource
limits, and whether the acceptance scenarios match the intended workflow.
Clarification answers do not approve implementation of the whole plan.

The existing REST API and tool example already support scripted workflows. A
read-only assistant would be simpler, but would not meet conversational submission
acceptance. Confirmation adds a client round trip and durable state; it lets the
human validate the model's interpretation and keeps execution independent of
provider availability. A direct provider SDK would reduce framework dependencies;
use the roadmap's LangChain adapter without its agent/checkpointer stack, keeping
the small execution loop and persistence under application control.

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | Query/compare via existing tools; scope every conversation, action, and referenced record to the authenticated project. | Valid-key foreign-project reads/decisions return not-found; normal query/comparison returns matching records. |
| F2 | Functional | Incomplete or invalid arguments produce missing-input guidance; no submission until complete arguments and exact-action confirmation. | Missing dataset/model, runtime, tuning objective/trials/total budget cases dispatch no mutation; confirmed valid actions submit. |
| F3 | Functional | Persist the expanded immutable action before confirmation; approve/reject only that action and fingerprint, never provider-controlled context. | Altered arguments/hash, fabricated approval, stale proposal, and hostile record instructions cannot dispatch. |
| F4 | Functional | Retain dialogue, public evidence, decisions, correlations, and outcomes; reuse one submission key for every retry of an action. | Restart/replay and ambiguous-response cases retain one experiment/job and the original action/key; queue errors retain saved IDs. |
| F5 | Functional | Return actual record facts separately from generated interpretation; reject unsupported citations and preserve job status meanings. | Fabricated IDs/metric facts rejected; queued never becomes completed; comparison uses validation metrics. |
| N1 | Reliability | Bound provider/tool calls, payloads, deadlines, and context; fail safely on provider/storage/API errors. | Boundary/timeout/oversize tests, interrupted requests, and storage failure before/after dispatch; direct API still works. |
| N2 | Concurrency | Reject competing/stale turns and duplicate action claims across API processes; external calls never run in retryable transactions. | Real-MongoDB interleavings demonstrate one claimant, stale-write rejection, and same-key retry after lost ownership. |
| N3 | Compatibility | Preserve existing API, tool defaults, worker ownership, serial training, budgets, artifacts, and opt-in gates. | Existing fast, ordinary integration, and isolated recovery suites remain passing without provider credentials. |

## Constraints and scope

Reuse the existing tool catalog and HTTP API enforcement boundary. No arbitrary
URLs, code execution, dataset uploads, artifact contents, version registration,
new training defaults, worker concurrency, or changes to selection/recovery.
Keys, headers, project, correlation, origin, and submission key remain host-bound.
Do not infer authorization from persisted dialogue or treat retrieved text as
instructions. Preserve [evidence metadata](../memory/conversation-response-evidence.md)
and [transaction fences](../memory/tuning-parent-fence.md).

Chat requires transaction-capable MongoDB. Provider availability is not added to
existing readiness, and disabled/unconfigured chat cannot break direct API startup.
No browser UI, streaming, embeddings, provider-owned conversation storage, or
production capacity/performance claims are included.

## Design

### Interfaces and modules

Add `conversation_schemas.py`, `conversation_store.py`, `conversation_provider.py`,
`conversation_service.py`, and `conversation_api.py` under the canonical package.
Define a provider protocol with an injected deterministic implementation for tests.
Add locked runtime dependencies on `langchain-core` and `langchain-openai`; resolve
compatible versions during implementation and record them rather than inventing
version constraints now. Lazy provider construction avoids credential-dependent
startup. Lifespan owns and closes the provider and tool HTTP clients.

All new routes use existing project access, error envelopes, and correlation IDs;
request models forbid extra fields and use existing resource-ID restrictions:

Replays keep original execution correlations in the stored outcome while the
current HTTP envelope/header uses the current request's correlation ID.

| Route | Contract |
| --- | --- |
| `POST /api/v1/chat` | `request_id`, `message`, `expected_revision`, optional `conversation_id`; revision 0 starts a conversation. Return conversation/turn IDs, revision, turn status, message, required-input locations, verified facts/evidence, and optional pending action. |
| `GET /api/v1/conversations/{conversation_id}` | Paginated turns in ascending sequence and conversation revision; `limit=50` (1-100), `offset=0`. Current action states accompany their originating turns. |
| `GET /api/v1/conversations/{conversation_id}/actions/{action_id}` | Public proposal, fingerprint, decision/execution state, safe attempt outcomes and evidence; omit credentials, submission key, and owner tokens. |
| `POST /api/v1/conversations/{conversation_id}/actions/{action_id}/decision` | `decision=approve\|reject` and `arguments_hash`; edits require a new proposal. No provider call. Return saved action/outcome, or HTTP 202 for an existing active execution. |

Exact `request_id`/body replay returns the saved turn (202 while running) without
another provider call; another body under that ID returns 409
`chat_idempotency_conflict`. Other explicit errors include 409
`conversation_conflict` / `action_conflict`, 404 `conversation_not_found` /
`action_not_found`, 503 `chat_unavailable` / `provider_unavailable`, 504
`chat_timeout`, and 422 `chat_limit_exceeded` / `provider_invalid_response`.
Existing schema/storage handlers retain their codes. A failed recorded turn is
available through history and same-ID replay; retrying generation needs a new
request ID. Infrastructure errors report saved turn/action IDs when known.

### Provider, inputs, and evidence

Use `ChatOpenAI` with the Responses API, application-owned context, `store=False`,
automatic SDK retries disabled, and parallel tool calls disabled. Bind catalog
schemas with `strict=False` to preserve optional/defaulted arguments; Pydantic
remains authoritative. Reject malformed output and multiple tool calls before
dispatch. Official [LangChain integration](https://docs.langchain.com/oss/python/integrations/chat/openai)
and [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)
were checked October 6, 2026; strict provider schemas have different optional-field
requirements. Do not add built-in provider tools or external tracing.

The host runs read tools serially. On a valid mutating call it stops, persists a
proposal, and returns `awaiting_confirmation`; it never passes model-supplied
permission/context to the dispatcher. Missing fields come from validation, with
no new defaults for required budgets/objectives. The prompt requests clarification
instead of guessing; schema validation cannot prove semantic understanding of
natural language. Human approval of the displayed exact action validates that
interpretation. Prompt evaluations must specifically test unprovided values.

Provider context contains redacted user/assistant text and selected public tool
records, never source CSVs, artifact bytes, credentials, or private persistence
fields. Opaque continuation items remain ephemeral within a turn. History is
bounded to complete turns, with omitted history disclosed. Known configured keys
and connection credentials are redacted before storage, provider submission,
response, and logs; extend logging redaction for provider SDK loggers.

Provider-selected citation IDs must belong to successful tool evidence in the
turn. For numeric/status/winner facts, accept references to supported record
fields and have the host render their actual values; never trust provider-supplied
values. Generated prose remains interpretation, not independently verified
measurement. Persist the evidence snapshot used for the answer; a later answer
refreshes mutable job state rather than presenting old status as current.
`store=False` does not promise zero provider retention; the
[OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data)
describe separate abuse-monitoring retention.

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
cannot publish answers/actions after reconciliation. Provider/HTTP calls stay
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
Clients can inspect its outcome without the provider.

### Configuration and limits

Add these documented settings; limits are proposals, not measured capacity:

| Setting | Default / rule |
| --- | --- |
| `MLPP_CHAT_ENABLED` | `false`; disabled chat routes return `chat_unavailable`. |
| `MLPP_CHAT_PROVIDER`, `MLPP_CHAT_MODEL`, `MLPP_CHAT_API_KEY` | Provider `openai`; no model/key default. Enabled live chat requires model, secret key, project keys, and transaction-capable storage. |
| `MLPP_CHAT_API_ORIGIN` | `http://127.0.0.1:8000`; trusted origin validation matches the tool adapter, never request Host/model arguments. |
| `MLPP_CHAT_TIMEOUT_SECONDS`, `MLPP_CHAT_PROVIDER_TIMEOUT_SECONDS` | 60 overall / 20 per provider call; positive finite values, at most 120 / 60, provider timeout no greater than overall. |
| `MLPP_CHAT_ACTION_TIMEOUT_SECONDS` | 30 per confirmation dispatch; positive finite, at most 60. Its absolute deadline is also the action attempt's claim expiry. |
| `MLPP_CHAT_MAX_PROVIDER_CALLS`, `MLPP_CHAT_MAX_TOOL_CALLS`, `MLPP_CHAT_MAX_OUTPUT_TOKENS` | 5 / 4 / 1024; bounded to 1-10 / 1-8 / 128-4096. Count invalid proposals against the call limit. |

Fixed first-slice caps: 64 KiB new-route request bodies, 8 KiB UTF-8 message text,
64 KiB serialized provider context including tools, 128 KiB tool HTTP responses,
256 KiB persisted turn/action payloads, and ten complete prior turns. Check before
dispatch/storage; oversized tool results fail rather than truncate evidence.
Add optional `max_response_bytes=None` to `HttpToolTransport`, preserving its
existing default. Chat supplies the cap and streams/counts decoded response bytes
before JSON parsing. Validate at and above limits, including multibyte text and
chunked/compressed responses. Deadline checks bound local dispatch/commit; cancelling
a local HTTP request cannot undo provider billing or a remotely accepted job.

Update README endpoints, `.env.example`, Compose's explicit chat opt-in, tool/chat
guides, roadmap/status, repository contracts, memory fixtures, and CI reports.
Document history/audit retention and provider data flow before enabling the route.

## Acceptance and verification

Implement in reviewable steps: schemas/provider contract; durable claims and
replay; bounded read loop; proposals/decisions; API/docs; real-service and opt-in
provider evaluations. Run focused tests after each step, retaining failures.

1. Scripted-provider/API tests cover queries, validation comparison, missing and
   hallucinated required inputs, complete confirmed training/tuning, rejection,
   cancellation, hostile records, bad citations/facts, and configured-key access
   (F1-F5). Negative cases use valid authentication and otherwise valid data to
   reach the claimed boundary. Do not assert exact model wording.
2. Boundary/failure tests cover call limits, UTF-8/payload caps, SDK retry disabling,
   timeouts, partial responses, redaction, cleanup, and storage loss before/after
   dispatch (N1). Test disabled chat and a failing provider alongside working direct
   API routes. Preserve existing assertions; justify any fixture/test changes.
3. Real-MongoDB tests pause competing turn/decision transactions and expired owners,
   verifying one claimant and unchanged stale state (N2). A disposable API process
   is killed after submission acceptance but before audit completion; same-action
   confirmation after restart must retain one job and recover its evidence.
   Ordinary integration uses the scripted provider and real API/queue/workers to
   confirm training/tuning, compare results, and cancel tuning (F4, N3).
4. Before the application commit run all repository fast checks, `uv build`, and
   ordinary integration with **both** `MLPP_RUN_INTEGRATION=1` and
   `MLPP_RUN_WORKER_INTEGRATION=1`, following [README setup](../../README.md#run-checks).
   Run the existing isolated recovery suite serially with
   `MLPP_RUN_RECOVERY_INTEGRATION=1` using [recovery setup](../recovery.md#run-the-suite).
   Missing services or selected-case skips are verification gaps.
5. Add `evaluations/test_conversation_provider.py` outside default `tests/`
   discovery, with a separately registered `provider_eval` marker, requiring
   `MLPP_RUN_PROVIDER_EVAL=1`, explicit model/key, and operator-supplied request,
   token, and USD budgets with dated model pricing. Keep it out of ordinary CI
   and fast/service gates. Use ten synthetic scenarios: read, comparison, missing
   dataset/model, missing runtime, missing tuning objective, missing tuning limits,
   unsupported action, foreign project, hostile record, and evidence/status accuracy.
   Each must satisfy action/access/evidence checks; never hide failed scenarios
   through retries. Missing credentials/budget or a budget-exhausted scenario is a
   reported gap. Live evaluation proposes actions without running paid training.
   Reserve the worst-case billable token cost before each provider call, then
   reconcile reported usage; unsupported pricing/token accounting fails closed.
   The USD budget is a local admission bound using the supplied rates, not a
   provider billing guarantee. Run explicitly with
   `uv run --locked --extra training pytest evaluations/test_conversation_provider.py -m provider_eval`.

Seek independent review of claim transactions, action/turn states, replay,
uncertain outcomes, and byte/token arithmetic; record reviewer, exact submitted
revision, findings, and resolutions. Availability is unestablished; self-review
is not independent review. Retain JUnit, redacted state snapshots/failure traces,
provider model/package versions, prompt/config hashes, usage/cost inputs, source
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

- Reviewer/date/decision: pending.
- Confirmed clarifications: repository user selected OpenAI, per-action
  confirmation, and stored dialogue/action evidence, October 6, 2026.
- Approval scope to review: routes, provider/dependencies, project-key requirement,
  per-action confirmation, persisted text/evidence and retention, state/claim/retry
  behavior, resource limits, and acceptance gates above.
- Model ID, detailed limits/contracts, and independent reviewer: pending review
  or operator configuration as specified above; no model/cost measurement claimed.
- Explicit implementation approval reference and requested revisions: not yet given.
  Material changes require plan revision and renewed review under the
  [development method](../development-methodology.md#the-five-stage-loop).

## Implementation outcome

Not implemented. After approval, record source revisions, actual dependency/model
versions, commands/environment, requirement-mapped results/skips/warnings, raw
evidence/archive locations, justified test changes, independent review and
resolutions, deviations/reapproval, durable findings, and completion commit/push.

Plan preparation checks (October 6, 2026, baseline above, Windows/PowerShell):
local Markdown validation passed for 17 documents and 144 links/anchors; the two
proposed shell commands parsed; all nine template sections are present with no
placeholders. Source inspection confirmed the 13-tool baseline and absent
conversation modules/provider dependencies. Official provider pages were opened
and checked, and `git diff --check` passed. These are documentation checks;
application, real-service, and live-provider acceptance evidence is pending.
