# Conversation development

Person A starts with A1 in the [two-person allocation](plans/2026-10-08-two-person-course-completion-plan.md).
Its [conversation design](plans/2026-10-06-conversation-workflows-plan.md)
already has October 7 implementation approval. This first slice supplies the
strict request/public-action/model-reply schemas, canonical fingerprints,
injected model interface, native descriptions of the existing 13 tools,
validated configuration, and locked `langchain-core` / `langchain-ollama` dependencies.

The next A1 slice adds [the local adapter](../src/ml_pipeline_pro/conversation_ollama.py)
with native tool proposals, installed-artifact inspection, deadline/byte/token
admission, fixed safe errors, redaction, and client cleanup. Deterministic tests
exercise the real locked SDK against an in-memory HTTP transport.
A third A1 slice adds [the durable store](../src/ml_pipeline_pro/conversation_store.py)
for turn claims/replay, scoped history, and immutable pending proposals, with
real-MongoDB transaction-race coverage. Chat routes, the host loop, and action
decisions/dispatch remain pending. `MLPP_CHAT_ENABLED=true` does not enable chat yet.
Direct tracking/tuning routes continue to use their existing contracts. Course
C3/C5 remain outstanding; installing dependencies and scripted tests do not
establish a working pre-trained model.

## Configuration

Settings follow the approved design and are listed in [.env.example](../.env.example).
Environment variables override `.env`. The adapter consumes inference settings;
the API does not construct it yet.

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
| `MLPP_CHAT_CONTEXT_TOKENS` | 8192; integer 1024-16384; adapter checks advertised model support and requires an artifact-specific token counter. Actual tokenization/overflow evidence is still outstanding. |

Call/token settings accept decimal integer strings from environment files and
reject booleans or fractional values. These are approved limits, not measured
capacity. Schema validation enforces the 8 KiB UTF-8 user-message limit and
requires exactly one tool call or final reply per model step. The 64 KiB request
and context, 128 KiB tool response, 256 KiB saved-record, and ten-turn history
caps belong to the approved service design. The adapter enforces 64 KiB serialized
context including instructions/tools; the store enforces saved-record limits.
The upcoming service must enforce request, tool-response, and model-history boundaries.

## Model and action boundaries

The model interface describes calls; the host will bind trusted project/key,
correlation, submission key, and mutation permission. Chat request bodies cannot
supply those fields. A decision accepts only `approve`/`reject` and the exact
saved fingerprint; edited arguments need a new proposal. The schema cannot
authorize an action or prove that a citation is supported. Turn claims/completion
and pending proposals are persisted now. Grounded fact rendering, action
decisions, and dispatch orchestration remain host implementation work.

Model replies request record IDs and field references, without supplying verified
fact values. Actual values must come from successful public tool evidence. Action
fingerprints use sorted, compact, finite JSON encoded as UTF-8 after existing tool
validation expands defaults. Required runtime/objective/tuning limits retain the
existing tool rules.

The adapter uses the [official LangChain ChatOllama integration](https://docs.langchain.com/oss/python/integrations/chat/ollama)
and native `bind_tools` protocol. Run the separately installed Ollama server with
`OLLAMA_NO_CLOUD=1` in **its** environment, per [Ollama's local-only setup](https://docs.ollama.com/faq#how-do-i-disable-ollama-cloud-features).
Artifact selection, retained digest/license/runtime evidence, tokenization checks,
cold and warm inference, and the approved ten-scenario live evaluation remain
outstanding. No model download or inference belongs in the ordinary test gate.

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

The `counter` receives the exact SDK-normalized Ollama request at the HTTP request
hook, including messages and tools. It must use the selected artifact's tokenizer
and runtime chat/tool template, including special tokens. Verify it against
runtime prompt counts and overflow tests before integrating the adapter into a
chat route. No counter is supplied in this slice: inspection still works, but
generation fails with `model_unavailable`. Tests inject synthetic counts to prove
admission boundaries; they do not establish tokenization accuracy. Admission
reserves the entire output allowance before the HTTP inference request.

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
records or adding TTL deletion. The application does not instantiate this store
yet. Its host-private `TurnClaim` must never be returned as an API response;
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
until explicit operator deletion. This slice provides no action approval,
execution claims, dispatch, unknown-outcome retry, or attempt reconciliation.
Those state transitions and chat-process loss tests remain required A1 work.

## Verify this slice and continue A1

From the repository root:

```powershell
uv sync --locked --extra training
uv run --locked --extra training pytest tests/test_conversation_schemas.py tests/test_conversation_model.py tests/test_conversation_config.py
uv run --locked --extra training pytest tests/test_conversation_ollama.py tests/test_logging.py
uv run --locked --extra training pytest tests/test_conversation_store.py
```

The tests cover UTF-8 boundaries, trusted-context exclusion, exact decision shape,
fact references, native LangChain tool compatibility, configuration failures,
SDK-normalized token admission, response limits, error/retry behavior,
credential/tracing isolation, and cleanup.
They supplement the [full fast gate](verification.md#fast-checks), dependency
compatibility, and package build. No existing assertion or live-service gate is
relaxed. The store adds MongoDB collections/transactions; run the full
[ordinary integration gate](verification.md#ordinary-integration) with both
flags, including [its real transaction cases](../tests/integration/test_conversation_store.py),
and the separate serial recovery gate. Existing worker/tuning ownership behavior
is unchanged. Store tests use real sessions and controlled interleavings;
local pure-boundary tests alone do not establish snapshot-isolation correctness.

Continue the approved plan in reviewable steps: select the artifact and verify
its tokenizer/runtime behavior; implement the bounded host read loop and
evidence grounding; exact action decisions/execution claims; API/lifespan/docs
integration with Person B; further action races and lost-response/chat-process
recovery; and the opt-in live-model gate. The stash
named `Before requested origin reset 2026-10-08` is preserved as unfinished source,
not acceptance evidence. Review every reused portion rather than applying it in
bulk. Independent review of state/claim/retry/resource arithmetic remains pending.
