# Conversation development

Person A starts with A1 in the [two-person allocation](../plans/2026-10-08-two-person-course-completion-plan.md).
Its [conversation design](../plans/2026-10-06-conversation-workflows-plan.md)
already has October 7 implementation approval. The foundation supplies the
strict request/public-action/model-reply schemas, canonical fingerprints,
injected model interface, native descriptions of the existing 13 tools,
validated configuration, and locked `langchain-core` / `langchain-ollama` dependencies.

The implemented A1 slices include [the local adapter](../../src/ml_pipeline_pro/conversation_ollama.py)
with native tool proposals, installed-artifact inspection, deadline/byte/token
admission, fixed safe errors, redaction, and client cleanup. Deterministic tests
exercise the real locked SDK against an in-memory HTTP transport.
[The durable store](../../src/ml_pipeline_pro/conversation_store.py) provides support
for turn claims/replay, scoped history, and immutable pending proposals, with
real-MongoDB transaction-race coverage. The bounded
[host loop](../../src/ml_pipeline_pro/conversation_service.py) and
[fact renderer](../../src/ml_pipeline_pro/conversation_grounding.py) have scripted
model tests and real HTTP/MongoDB orchestration tests. Authenticated chat/history/
action routes and exact confirmed dispatch now exist, with transaction-race and
killed-chat-process recovery coverage. An explicit installed Qwen profile now
has a verified tokenizer/runtime counter; its live conversation gate fails.
Direct tracking/tuning routes continue to use their existing contracts. Course
C3/C5 remain outstanding; installing dependencies and scripted tests do not
establish a working pre-trained model.

## Configuration

The approved A2 implementation adds host-only `generate_pipeline_snippet`,
bringing native conversation bindings to 15 while preserving the public 13
domain tools. It generates and validates one Python draft under the original
turn budget and saves its outcome/provenance. The code-generation invocation has
no native tools; its exact SDK payload still passes token admission. See
[the snippet guide](snippet-generation.md) for profiles, boundaries and evaluation.

Settings follow the approved design and are listed in [.env.example](../../.env.example).
Environment variables override `.env`. When chat is enabled and a model tag is
configured, the API constructs the adapter offline and prepares it lazily during
generation. Its default counter remains unset, so inference fails closed until
the selected artifact's verified counter is supplied.

| Setting | Default and validation |
| --- | --- |
| `MLPP_CHAT_ENABLED` | `false`; conversation functionality remains under development. |
| `MLPP_CHAT_BACKEND` | `ollama`; no external provider backend. |
| `MLPP_CHAT_MODEL` | Unset. Use an explicit installed artifact tag; cloud tags are rejected. No automatic download. |
| `MLPP_CHAT_MODEL_ORIGIN` | `http://127.0.0.1:11434`. HTTP(S), no credentials/path/query/fragment, port 1-65535 when specified. Host must be loopback, RFC1918 IPv4, IPv6 ULA, `localhost`, `ollama`, `host.docker.internal`, or `service.namespace.svc.cluster.local`. DNS names are trusted operator configuration; this is not a DNS rebinding guard. |
| `MLPP_CHAT_API_ORIGIN` | `http://127.0.0.1:8000`. Operator-configured HTTP(S) origin, matching the existing tool transport's host policy; no credentials/path/query/fragment. |
| `MLPP_CHAT_TIMEOUT_SECONDS` | 60; positive finite, at most 120. |
| `MLPP_CHAT_MODEL_TIMEOUT_SECONDS` | 20; positive finite, at most 60, no greater than overall timeout. |
| `MLPP_CHAT_ACTION_TIMEOUT_SECONDS` | 30; positive finite, at most 60. |
| `MLPP_CHAT_MAX_MODEL_CALLS` | 5; integer 1-10. |
| `MLPP_CHAT_MAX_TOOL_CALLS` | 4; integer 1-8. |
| `MLPP_CHAT_MAX_OUTPUT_TOKENS` | 1024; integer 128-4096, less than context size. |
| `MLPP_CHAT_CONTEXT_TOKENS` | 8192; integer 1024-16384; adapter checks advertised model support and requires an artifact-specific token counter. The explicit Qwen profile has retained tokenization/overflow evidence at 8192. |

Call/token settings accept decimal integer strings from environment files and
reject booleans or fractional values. These are approved limits, not measured
capacity. Schema validation enforces the 8 KiB UTF-8 user-message limit and
requires exactly one tool call or final reply per model step. The 64 KiB request
and context, 128 KiB tool response, 256 KiB saved-record, and ten-turn history
caps belong to the approved service design. The adapter enforces 64 KiB serialized
context including instructions/tools; the store enforces saved-record limits.
The API and host loop enforce request, tool-response, and model-history boundaries.

## Model and action boundaries

The model interface describes calls; the host binds trusted project/key,
correlation, submission key, and mutation permission. Chat request bodies cannot
supply those fields. A decision accepts only `approve`/`reject` and the exact
saved fingerprint; edited arguments need a new proposal. The schema cannot
authorize an action or prove that a citation is supported. Turn claims/completion
and pending proposals are persisted now; the host renders supplied facts and
preflights mutation references. Exact decisions and dispatch use the saved action,
transactional attempt ownership, and original submission key; inference does not
participate in confirmation.

Model replies request record IDs and field references, without supplying verified
fact values. Actual values must come from successful public tool evidence. Action
fingerprints use sorted, compact, finite JSON encoded as UTF-8 after existing tool
validation expands defaults. Required runtime/objective/tuning limits retain the
existing tool rules.

The adapter uses the [official LangChain ChatOllama integration](https://docs.langchain.com/oss/python/integrations/chat/ollama)
and native `bind_tools` protocol. Run the separately installed Ollama server with
`OLLAMA_NO_CLOUD=1` in **its** environment, per [Ollama's local-only setup](https://docs.ollama.com/faq#how-do-i-disable-ollama-cloud-features).
The [local setup guide](local-model-setup.md) describes the installed profiles,
pinned tokenizer, runtime/template checks and failed ten-scenario evaluations.
Successful live acceptance, independent review and clean-checkout onboarding
remain outstanding. No model download or inference belongs in the ordinary test gate.

## Adapter lifecycle and admission

Construct `OllamaConversationModel(settings, count_input_tokens=counter)` only
after the host has selected the local artifact. Construction opens no network
requests. An async context manager calls `prepare()` and closes both clients on
exit, including inspection failure and cancellation. Inspection reads `/api/tags`,
`/api/show`, and `/api/version`; it requires the configured installed tag/digest,
native tool capability, and advertised context support. Provenance captures the
reported digest/runtime, package versions, and license/template/instruction/tool
hashes. A missing license remains `null`; the evaluation must retain and inspect
the actual artifact license. Inspection does not establish model quality or
immutability of an operator-retagged artifact.

The October 10 approved [typed-completion change](../plans/2026-10-09-conversation-typed-completion-plan.md)
binds 14 native functions: the existing 13 domain tools, with proposal-specific
mutation descriptions, and adapter-only `finish_conversation`. Its arguments
use the existing `ModelReply` schema. Exactly one completion with empty free-text
content becomes a reply; malformed arguments, extra fields, supplied fact values,
mixed prose, duplicate keys and multiple calls fail with `model_invalid_response`.
Strict legacy JSON replies remain supported. Completion spends one model call
and no HTTP tool call; it cannot create or confirm a proposal. The public domain
catalog, routes and persisted schemas remain unchanged. Host byte admission
includes all 14 full schemas; token admission counts their exact SDK projection.
The selected 7B profile passed only three of ten original scenarios in the new
run, so successful model acceptance remains outstanding.

The `counter` receives the exact SDK-normalized Ollama request at the HTTP request
hook, including messages and tools. It must use the selected artifact's tokenizer
and runtime chat/tool template, including special tokens. Verify it against
runtime prompt counts and overflow tests before integrating the adapter into a
chat route. The default adapter has no counter and fails with `model_unavailable`.
The explicit [Qwen factory](../../examples/qwen_chat_app.py) lazily verifies the
installed identity and loads the checksum-pinned local tokenizer within the first
bounded generation call. Eight retained stock-profile probes and a real SDK
overflow check establish the selected counter's boundary behavior. Synthetic
adapter tests alone do not establish tokenization accuracy. Admission reserves
the entire output allowance before the HTTP inference request.

The adapter submits a single non-streaming call, sets `num_ctx` and `num_predict`,
and checks reported token usage. Response hooks count decoded chunks up to the
256 KiB record cap before JSON parsing, including compressed/chunked responses.
Partial replies, token-limit termination, malformed native arguments, multiple
calls, invalid JSON, duplicate keys, and model-supplied fact values are rejected.
Final replies are strict `ModelReply` JSON; tool arguments stay incomplete for
the host's typed validation/missing-input guidance. No tool is dispatched here,
and citation support still requires the host's evidence check.

Known configured keys/passwords and recognized credential patterns are redacted
from submitted context and returned replies/arguments. The future service must
also redact stored dialogue and public evidence. Redaction does not detect every
free-text secret. Clients disable proxy inheritance, redirects, automatic
transport retries, cache, thinking output, and LangSmith tracing; inherited
`OLLAMA_API_KEY` headers are removed from both SDK clients. `langsmith` is declared
directly to use its tracing-disable context, with no package-version change.
LangChain debug printing fails closed before inference. Application logging adds
model/HTTP logger namespaces to its configured redaction. Timeout/cancellation
stops the local request; it cannot undo runtime work already started.

## Durable turn and proposal storage

`ConversationStore(database, settings)` uses transaction-capable MongoDB. It
adds three schema-version-1 collections without migrating existing domain
records or adding TTL deletion. The application instantiates it for the chat
routes. Its host-private `TurnClaim` must never be returned as an API response;
return its strict public `ConversationTurn` instead.

| Collection | Stored contract and indexes |
| --- | --- |
| `conversations` | Project/identity/schema/timestamps; conversation `revision`, `fence_revision`, active turn ID, owner token and original absolute deadline. Project/update lookup index. |
| `conversation_turns` | Project/conversation/identity/schema/timestamps; unique `(project_id, request_id)` and `(project_id, conversation_id, sequence)`; original request fingerprint, private owner/deadline and typed public turn snapshot. |
| `conversation_actions` | Project/conversation/turn/identity/schema/timestamps; unique action per originating turn; private submission key and typed public immutable proposal/fingerprint. Public reads omit the key. |

`reserve(context, request, deadline=...)` initializes indexes before reserving.
It uses a transaction to advance the expected revision and reserve one active
turn. Exact project/request/body replay returns the saved turn with no owner
token and no permission to generate; another body returns
`chat_idempotency_conflict`. Competing turns or a wrong revision return
`conversation_conflict`. The saved execution correlation remains the original
one. Clock/deadline/expiry values use UTC milliseconds, matching BSON, so first
responses and saved replays agree without extending the persisted deadline.

`finish(context, claim, public_turn, proposal=...)` writes the matching,
unexpired conversation owner in the same transaction as completion/proposal
persistence. Result identities, original user message and correlation cannot
change. The optional proposal must accompany `awaiting_confirmation`; the
store expands existing mutating-tool schemas, generates its ID/submission key
once outside retryable callbacks, hashes canonical finite arguments, and saves
it before returning. Missing budgets/objectives remain validation errors. No
model/HTTP calls or decisions run in these callbacks. The store enforces the
256 KiB serialized record cap including private bookkeeping and redacts known
configured and trusted-context credentials before saving public content.

`history(project_id, conversation_id, limit=50, offset=0)` returns ascending
turns; `action(project_id, conversation_id, action_id)` returns a scoped public
proposal. Reads/replays/new reservations reconcile expired running turns to
`interrupted`; generation never resumes automatically. Pending proposals expire
after 15 minutes or are superseded by a newer turn. These transitions also
write the parent in the same transaction. History/replay hydrate the current
action state while retaining the originating turn outcome. Audit records remain
until explicit operator deletion. The action slice below adds exact decisions,
execution claims, dispatch, unknown-outcome retries and attempt reconciliation.

## Bounded host loop and supplied evidence

`ConversationService(settings, store, model, transport).chat(context, request)`
accepts trusted host context after authentication. It binds a read-only context
with the saved execution correlation and no submission key, even if its caller
supplied mutation permission. `MLPP_CHAT_ENABLED=false` rejects generation before
model/store calls. Exact request replay returns the saved turn without inference,
including when the injected model is unavailable. The caller's lifespan owns
and closes the injected model and HTTP transport. The HTTP integration below
binds this service to the app lifespan.

The service includes at most ten previous terminal user/assistant pairs, labelled
historical, and discloses omitted history. It selects public tool snapshots,
removes holdout metrics, artifact/dependency/URI contents, private tokens and
correlation metadata from model context, and redacts known configured/context
credentials. The current turn starts a new evidence ledger; previous citations
and mutable statuses require fresh successful reads. Full safe tool snapshots
remain inspectable in the saved turn. History/context limits fail explicitly;
the service does not silently truncate successful evidence to fit the model.

Model and tool requests run serially under the original absolute turn deadline,
configured overall/per-model timeouts and call limits. A malformed or missing
mutation input becomes `needs_input` with schema-derived field locations.
Complete proposals preflight dataset/model or cancellation-target references
through the existing scoped API, consuming the same read budget. Current fetched
records can satisfy those checks. The loop then saves `awaiting_confirmation`
and stops without a mutation HTTP call or another inference call. All expanded
values remain labelled model-proposed. Natural-language intent and whether a
model guessed an unprovided budget still need prompt evaluation and exact human
review; schema completeness alone cannot establish those facts.

For replies, citations must occur in successful current-turn public tool evidence.
Scalar identity/configuration/status/validation-metric fields are resolved from
actual supplied record fields. Supported examples include `name`, `status`,
`metrics.validation_f1`, `config.learning_rate`, `objective_value`,
`best_trial_id`, and `comparison.best_experiment_id`. Related parent/source IDs
may be cited as relationships but their own fields require a fetched record.
Unsupported, missing/private/holdout fields, fabricated IDs and ambiguous IDs
shared by different record kinds fail. Later successful reads replace earlier
record views within a turn. Generated prose is interpretation; structured
`VerifiedFact.value` comes from a validated supplied API snapshot. This does not
prove every factual statement a model might put in free prose.

The existing dispatcher may expand response-schema defaults. A per-read response
capture projects its validated data onto fields actually supplied by the API,
so an omitted status cannot become a verified default `queued` value. This
preserves the exported dispatcher behavior and input default expansion. The
[missing-status regression](../../tests/test_conversation_service.py) reproduces
that mechanism and now rejects the unsupported fact.

Chat requires `HttpToolTransport(..., max_response_bytes=128 * 1024)`. Its new
optional cap defaults to `None` for existing callers. It streams/counts decoded
bytes before JSON parsing and closes on oversize/timeout/cancellation, including
chunked/gzip results. The service also checks normalized snapshots, 64 KiB model
context including native schemas/instructions, and 256 KiB output records.
An unpublishable record fails as a whole; a minimal failed turn explicitly marks
`evidence_not_saved` instead of presenting truncated evidence as success.

Per-model failures and invalid replies are saved as failed turns with safe
error codes/statuses. Local storage failures raise `storage_unavailable` with
known turn/conversation IDs, preserving uncertainty about a commit. Overall
deadline expiry returns `chat_timeout` and reconciles the turn to `interrupted`;
cancellation propagates and leaves expiry reconciliation to subsequent reads.
Owner/revision conflicts are never overwritten with a late failure result.
Direct tracking/tuning APIs remain available independently of inference.

## Verify this slice and continue A1

From the repository root:

```powershell
uv sync --locked --extra training
uv run --locked --extra training pytest tests/test_conversation_schemas.py tests/test_conversation_model.py tests/test_conversation_config.py
uv run --locked --extra training pytest tests/test_conversation_ollama.py tests/test_logging.py
uv run --locked --extra training pytest tests/test_conversation_store.py
uv run --locked --extra training pytest tests/test_conversation_service.py tests/test_conversation_grounding.py tests/test_tool_transport.py
```

The tests cover UTF-8 boundaries, trusted-context exclusion, exact decision shape,
fact references, native LangChain tool compatibility, configuration failures,
SDK-normalized token admission, response limits, error/retry behavior,
credential/tracing isolation, and cleanup.
They supplement the [full fast gate](verification.md#fast-checks), dependency
compatibility, and package build. No existing assertion or live-service gate is
relaxed. The store adds MongoDB collections/transactions; run the full
[ordinary integration gate](verification.md#ordinary-integration) with both
flags, including [its real transaction cases](../../tests/integration/test_conversation_store.py),
and the separate serial recovery gate. Existing worker/tuning ownership behavior
is unchanged. Store tests use real sessions and controlled interleavings;
local pure-boundary tests alone do not establish snapshot-isolation correctness.

Continue the approved plan in reviewable steps: resolve the failed opt-in
live-model gate, review the model and resource evidence, and verify clean-checkout
onboarding with Person B. The stash
named `Before requested origin reset 2026-10-08` is preserved as unfinished source,
not acceptance evidence. Review every reused portion rather than applying it in
bulk. Independent review of state/claim/retry/resource arithmetic remains pending.

## Confirmed actions and HTTP routes

The app now exposes the four approved routes in the README. Generation and
decisions require `MLPP_CHAT_ENABLED=true`; authenticated audit reads work while
generation is disabled. The app lifespan closes both the tool transport and
model. Construction is offline and readiness still checks MongoDB/Redis only.
An embedding host can pass `chat_model_factory` to `create_app` to supply the
selected artifact's verified token counter to `OllamaConversationModel`.
The default adapter fails closed without that counter. The explicit Qwen setup
supplies one; a passing real-model gate remains unfinished acceptance work.
The native adapter is prepared lazily inside the first bounded generation call;
artifact identity is captured after inspection, including failed generation.
Startup, saved replays and decisions do not inspect or call inference.

The store's `decide` method checks the saved immutable tool fingerprint and
project/conversation scope, then writes the parent and action in one transaction.
Only a newly committed `ActionClaim` carries a private attempt token and the
original submission key. The service dispatches outside the transaction, with
host-bound authentication and permission. Rejection, active replays and terminal
replays make no tool or inference call. First approval conflicts with a newer
turn or stale proposal; retry of an approved unknown action retains its identity
after the conversation advances.

Each attempt has the original absolute dispatch deadline. Completion fences the
unexpired token with another parent write; reads reconcile expired running
attempts to `unknown`. Transport failures, malformed responses and upstream 5xx
also retain uncertainty, including accepted IDs returned by queue failures.
A later 4xx does not resolve an earlier uncertain attempt. Explicit repeat
approval retries with the same body/key, to a maximum of three attempts;
exhaustion requires operator investigation. No retry occurs automatically.
Cancellation repeats only the original target through existing API semantics.
History hydrates current action state while retaining the originating turn.

Chat and decision HTTP bodies are limited to 64 KiB before JSON parsing, including
chunked requests. Successful saved evidence is never shortened to fit a record;
an oversized post-dispatch audit returns a minimal unknown result explicitly
marked `evidence_not_saved`, retaining known accepted job IDs. Storage loss preserves uncertainty and reports
known conversation/action IDs.

Example for an already displayed proposal (use its actual IDs and fingerprint):

```powershell
$proposalId = 'saved-action-id'
$conversationId = 'saved-conversation-id'
$argumentsHash = 'displayed-64-character-sha256'
$headers = @{ 'X-Project-ID' = 'demo' }
$decision = @{ decision = 'approve'; arguments_hash = $argumentsHash } | ConvertTo-Json
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/conversations/$conversationId/actions/$proposalId/decision" `
    -Method Post -Headers $headers -ContentType 'application/json' -Body $decision
```

The [real dispatch tests](../../tests/integration/test_conversation_dispatch.py)
confirm training, tuning and cancellation through the scoped API. The process
test pauses a disposable chat API after a real accepted response, kills it,
waits for natural attempt expiry, and restarts it: explicit same-action replay
retains one job and the original key. Controlled
[transaction cases](../../tests/integration/test_conversation_actions.py) cover
competing snapshots, stale proposals and expired attempt owners. These are
host/state evidence; they do not establish real model understanding or an
independent review.

## Opt-in installed-model evaluation

The [evaluation gate](../../evaluations/test_conversation_model.py) runs ten synthetic
scenarios in one bounded session: guided read, validation comparison/history-based
tuning proposal, missing dataset/model, missing runtime, missing objective,
missing tuning limits, unsupported action, foreign project, hostile record and
queued/status evidence. Fixture metrics are synthetic values, not measured
training. The gate never dispatches mutations and performs no model downloads.
Normal test discovery excludes `evaluations/`; its opt-in marker is registered.
An unselected gate is a verification gap, not a real-model pass.

Supply an explicit installed tag and a reviewed local `module:factory` token
counter. The factory receives the inspected public model provenance and returns
a callable counter for the exact SDK request payload. Its `identity` dictionary
must match `artifact_digest`, `runtime_version` and `template_hash`. The gate
records the counter source hash and checks its counts against actual prompt usage.
No generic token estimate or default counter is provided. The explicit
`evaluations.qwen_counter:create_counter` supplies the verified selected-profile
counter. Passing real-model execution remains required A1 work.

The gate admits at most 50 generation calls, reserving the configured full context
allowance before each (default 409,600 total reserved tokens), with 512 output
tokens per call and one 600-second suite deadline including preparation.
Per-turn/per-model/tool limits remain the approved settings. Failed calls consume
reservations; failed scenarios are retained without retries. The JSON report saves
safe turns, prompt/payload hashes, observed token counts/timings, model identity,
counter hash and loaded-model resource observations. Model prose still needs
human quality review. Ollama documents
[prompt token counts](https://docs.ollama.com/api/chat) and
[loaded-model observations](https://docs.ollama.com/api/ps); those returned values
are observations, not performance or resource-capacity guarantees.

After installing/selecting the artifact and verifying its counter:

```powershell
$env:MLPP_RUN_LOCAL_MODEL_EVAL = '1'
try {
    uv run --locked --extra training pytest evaluations/test_conversation_model.py -m local_model_eval `
        --local-model 'your-installed-model:explicit-tag' --token-counter 'reviewed_counter:create_counter' `
        --eval-output 'artifacts/local-model-evaluation/results.json'
} finally {
    Remove-Item Env:MLPP_RUN_LOCAL_MODEL_EVAL
}
```

Archive JSON/JUnit/model/license/resource evidence, including failures, with its
source manifest; ignored local output alone does not establish shared acceptance.
The [October 9 evidence](../evidence/2026-10-09-qwen-counter/results.json)
retains all six attempts. The stock 7B profile reached five of ten passing
scenarios after prompt revisions; its explicit JSON-tools profile reached six,
and the 14B profile reached three. All acceptance runs failed. No course row is
closed by token verification or partial scenario passes.

The [typed completion plan](../plans/2026-10-09-conversation-typed-completion-plan.md)
records the native reply function approved and implemented October 10. Its final
7B run passed only three of ten original scenarios; budget/evidence checks remain
unchanged. The [approved midterm plan](../plans/2026-10-13-midterm-delivery-plan.md)
now prioritizes guided workflows while retaining the original acceptance gates.
