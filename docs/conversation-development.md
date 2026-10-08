# Conversation development

Person A starts with A1 in the [two-person allocation](plans/2026-10-08-two-person-course-completion-plan.md).
Its [conversation design](plans/2026-10-06-conversation-workflows-plan.md)
already has October 7 implementation approval. This first slice supplies the
strict request/public-action/model-reply schemas, canonical fingerprints,
injected model interface, native descriptions of the existing 13 tools,
validated configuration, and locked `langchain-core` / `langchain-ollama` dependencies.

There is no chat route, conversation persistence, inference adapter, or automatic
tool execution in this slice. `MLPP_CHAT_ENABLED=true` does not enable chat yet.
Direct tracking/tuning routes continue to use their existing contracts. Course
C3/C5 remain outstanding; installing dependencies and scripted tests do not
establish a working pre-trained model.

## Configuration

Settings follow the approved design and are listed in [.env.example](../.env.example).
Environment variables override `.env`. Inference settings become active when
the adapter/service is implemented; the settings below are validated now.

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
| `MLPP_CHAT_CONTEXT_TOKENS` | 8192; integer 1024-16384; installed-model support and actual tokenization still need adapter/evaluation checks. |

Call/token settings accept decimal integer strings from environment files and
reject booleans or fractional values. These are approved limits, not measured
capacity. Schema validation enforces the 8 KiB UTF-8 user-message limit and
requires exactly one tool call or final reply per model step. The 64 KiB request
and context, 128 KiB tool response, 256 KiB saved-record, and ten-turn history
caps are constants for the upcoming service; schema definitions alone do not
enforce those whole-payload/transport/history boundaries.

## Model and action boundaries

The model interface describes calls; the host will bind trusted project/key,
correlation, submission key, and mutation permission. Chat request bodies cannot
supply those fields. A decision accepts only `approve`/`reject` and the exact
saved fingerprint; edited arguments need a new proposal. The schema cannot
authorize an action or prove that a citation is supported. Persistence,
revision/ownership checks, grounded fact rendering, redaction, and dispatch remain
the next implementation steps.

Model replies request record IDs and field references, without supplying verified
fact values. Actual values must come from successful public tool evidence. Action
fingerprints use sorted, compact, finite JSON encoded as UTF-8 after existing tool
validation expands defaults. Required runtime/objective/tuning limits retain the
existing tool rules.

The adapter will use the [official LangChain ChatOllama integration](https://docs.langchain.com/oss/python/integrations/chat/ollama)
and native `bind_tools` protocol. Run the separately installed Ollama server with
`OLLAMA_NO_CLOUD=1` in **its** environment, per [Ollama's local-only setup](https://docs.ollama.com/faq#how-do-i-disable-ollama-cloud-features).
Artifact selection, digest/license/runtime recording, tokenization checks, cold
and warm inference, and the approved ten-scenario live evaluation remain
outstanding. No model download or inference belongs in the ordinary test gate.

## Verify this slice and continue A1

From the repository root:

```powershell
uv sync --locked --extra training
uv run --locked --extra training pytest tests/test_conversation_schemas.py tests/test_conversation_model.py tests/test_conversation_config.py
```

The tests cover UTF-8 boundaries, trusted-context exclusion, exact decision shape,
fact references, native LangChain tool compatibility, and configuration failures.
They supplement the [full fast gate](verification.md#fast-checks), dependency
compatibility, and package build. No existing assertion or live-service gate is
relaxed. This slice makes no MongoDB, queue, worker, or recovery changes.

Continue the approved plan in reviewable steps: implement/evaluate the local
adapter; durable turn claims/replay; the bounded read loop; saved proposals and
exact decisions; API/lifespan/docs integration with Person B; real-MongoDB races
and lost-response/process recovery; and the opt-in live-model gate. The stash
named `Before requested origin reset 2026-10-08` is preserved as unfinished source,
not acceptance evidence. Review every reused portion rather than applying it in
bulk. Independent review of state/claim/retry/resource arithmetic remains pending.
