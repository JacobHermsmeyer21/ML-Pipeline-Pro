# Claude API chat backend

- Status: draft
- Date: 2026-10-20
- Source baseline: `d259343` on `dashboard-redesign` (branch `claude-chat-backend`)
- Request: "USE CLAUDE AS I GAVE YOU MY CLAUDE API KEY" (repository owner, October 20)
- Human reviewer/approval: pending
- Independent review: different-vendor reviewer unavailable; same-vendor subagent
  review of the adapter boundary planned and disclosed as such

## Proposed behavior and purpose

The Pipeline agent can run on Claude through the Anthropic API instead of the local
Qwen model served by Ollama. An operator selects it with `MLPP_CHAT_BACKEND=anthropic`.
The agent keeps the same behavior: typed read tools, proposals that need exact human
approval, reviewable Python drafts that are never executed, and monitoring
explanations. It answers faster and better than a 7B model on a laptop CPU, which is
the open laptop-inference bottleneck.

## Clarification and critique

Facts from source:

- The adapter boundary is `ConversationModel` in `conversation_model.py`.
  `OllamaConversationModel` (`conversation_ollama.py`, through LangChain) implements
  `generate`, `generate_snippet` and `generate_monitoring`. These return `ModelStep`
  (exactly one of a tool call, a reply or a snippet) or `MonitoringStep`.
- `conversation_api.py` constructs the Ollama adapter directly.
- `Settings.chat_backend` is `Literal["ollama"]`.
- Admission currently requires a verified Qwen token counter.

Case against:

- The course scope (`AGENTS.md`, `docs/project/course-requirements.md`) targets
  LangChain with **locally served** pre-trained models. Using a paid external API is
  not required and may not count toward that item.
- Conversation text and tool results (dataset names, metrics, record IDs) leave the
  machine and are sent to Anthropic.
- The API costs money per request.

Why it survives: the owner asked for it explicitly. The design keeps Ollama as the
default backend, so the course's local-model path and its evidence stay intact, and
Claude is an opt-in alternative. Whether the instructor accepts Claude for the
local-model requirement is the owner's question to settle. This plan does not mark
that requirement changed.

Decisions:

- **Official SDK.** The Claude adapter uses the official `anthropic` Python SDK (the
  Anthropic-recommended client), not a LangChain wrapper. LangChain stays on the Ollama
  path. (Implementer's call; the alternative `langchain-anthropic` would keep LangChain
  on both paths but adds a third-party layer the vendor guidance advises against.)
- **Default model.** `claude-opus-5-5`, configurable through `MLPP_CHAT_MODEL` (for
  example `claude-sonnet-5-5` or `claude-haiku-5-5` for lower cost). It runs with
  adaptive thinking (always on for this model) and an explicit effort setting,
  `MLPP_CHAT_EFFORT`, default `medium`.

Questions for the owner (do not block a draft):

1. Is Opus 5.5 the right default, or do you want Sonnet 5.5 or Haiku 5.5 for cost
   and speed?
2. Has the instructor accepted an external API for the local-model requirement?

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | With `MLPP_CHAT_BACKEND=anthropic`, chat turns produce the same `ModelStep` kinds (tool call, reply, snippet) and monitoring produces `MonitoringStep`. Tool results, approvals and history work unchanged. | Unit tests with an injected fake Anthropic client for each step kind; existing conversation-service tests pass with the new adapter. |
| F2 | Functional | Mutating tools are still only proposals. No action runs without the exact-action approval. | Existing action tests parameterized over both adapters. |
| F3 | Functional | The dashboard shows which backend answers ("Claude (Anthropic API)" vs "Local model on this machine"). | `/dashboard/config.json` exposes `chat_backend`; pytest and Playwright check the label. |
| N1 | Non-functional | The API key is a secret: never logged, never in errors, provenance, `config.json` or the repository. It is read only from `MLPP_ANTHROPIC_API_KEY`. | Redaction tests; `config.json` test asserts no key; `.env` stays gitignored. |
| N2 | Non-functional | Existing chat limits hold: model-call/tool-call counts, output token cap, context budget (via `messages.count_tokens`), per-call and per-turn timeouts. API errors map to existing fixed `ConversationModelError` codes. | Tests for timeout, 401, 429, 5xx, refusal and oversize context. |
| N3 | Non-functional | Ollama stays the default; with no Anthropic settings, behavior and all current tests are unchanged. | Full fast gates; integration gates unaffected. |
| N4 | Non-functional | One opt-in live check (`MLPP_RUN_ANTHROPIC=1`) makes real calls of a few cents, only with the owner's go-ahead. | Recorded live run: one read turn, one proposal, one snippet. |

## Constraints and scope

Unchanged: `/api/v1` schemas, idempotency, project scoping, exact-action confirmation,
snippet validation (drafts never executed), history storage and the Ollama/Qwen path
with its token counter. Excluded: the Vercel deployment, removing Ollama, prompt
caching tuning, streaming to the browser.

## Design

- `config.py`:
  - `chat_backend: Literal["ollama", "anthropic"]`
  - `anthropic_api_key: SecretStr | None` (env `MLPP_ANTHROPIC_API_KEY`)
  - `chat_effort: Literal["low", "medium", "high"] = "medium"`
  - Validation: `anthropic` requires the key. `chat_model` defaults to
    `claude-opus-5-5` for `anthropic`, and the origin and tokenizer checks apply to
    Ollama only.
  - Anthropic calls need longer timeouts than the Ollama defaults, so the documented
    profile uses a 90-second model call and a 120-second turn, inside the existing
    300-second ceilings.
- New `conversation_anthropic.py`, `AnthropicConversationModel`, using
  `anthropic.AsyncAnthropic`:
  - **Tools:** `native_conversation_tools()` is converted to Anthropic tool
    definitions (`name`, `description`, `input_schema`, `strict: true`).
    `tool_choice` is `auto`; forced tool choice is rejected by this model.
  - **Native step:** the instructions go in `system` (cached prefix). The reply is
    exactly one `tool_use` block: `finish_conversation` becomes a `ModelReply`, any
    other tool becomes a `ToolCall`. Anything else is treated as invalid output.
  - **Snippet and monitoring steps:** structured outputs (`output_config.format` with
    the `SnippetCandidate` / `MonitoringAdvice` JSON schema), validated with Pydantic
    as today. Monitoring IDs are still constrained to measured observations.
  - **Admission:** `messages.count_tokens` checks the context budget before each
    call. `max_tokens` is set from `chat_max_output_tokens` with headroom for thinking.
  - **Stop reasons:** `refusal` and `max_tokens` become `ConversationModelError`
    codes. Typed SDK errors map to the existing codes (`model_unavailable`,
    `chat_limit_exceeded`, …). The SDK's own retries are capped so a turn's timeout
    still bounds wall time.
  - **Provenance:** records backend, model ID, request ID and the instructions and
    tools hashes. It never records the key.
- `conversation_api.py`: builds the adapter for the configured backend.
- `dashboard_api.py`: `config.json` gains `chat_backend`. `app.js` shows the label.
  The dashboard build is regenerated.
- Dependencies: add `anthropic` to `pyproject.toml` and the lockfile (`uv lock`).
- Docs: `.env.example` (`MLPP_CHAT_BACKEND`, `MLPP_ANTHROPIC_API_KEY`,
  `MLPP_CHAT_EFFORT`, timeout profile), `docs/guides/conversation-development.md` and
  the README chat note. Compose and Kubernetes pass the key from the environment or a
  Secret, never baked into an image.

## Acceptance and verification

- Fast gates from `AGENTS.md`, `uv build`, and the dashboard `npm run check` /
  `test:e2e` for the label.
- New unit tests use an injected fake async client, so they make no network calls.
- The live check runs once after the owner approves the spend.
- The ordinary integration gates are unaffected. Docker is unavailable on this
  machine, so those gates run in CI.

## Risks and rollback

Risks:

- Cost overrun. Mitigated by the existing call caps plus the effort and model
  settings.
- Data leaving the machine. Documented, and opt-in only.
- Course-scope mismatch. Ollama stays the default, and the owner decides.
- Model output that doesn't fit the step schema. Strict tools, structured outputs and
  Pydantic validation, with existing invalid-output errors.

Rollback: set `MLPP_CHAT_BACKEND=ollama` or revert. Stored conversations and records
are unaffected.

## Human review and approval

Pending.

## Implementation outcome

Fill this section after implementation without weakening the criteria above.
