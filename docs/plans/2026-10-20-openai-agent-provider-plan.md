# Make OpenAI the default agent provider

- Status: awaiting human review; implementation has not started
- Date: 2026-10-20 (America/New_York)
- Source baseline: `e7c8e76` / `main`; fetched `origin/main` matches this revision
- Request: use OpenAI API calls for the application agent and create a written plan
- Human reviewer/approval: Jacob; default-provider and $2 test-budget decisions
  confirmed in this session; approval of this written design remains pending
- Independent review: seek a separate reviewer for token/cost arithmetic and
  request lifecycle isolation before claiming acceptance; availability unknown

## Proposed behavior and purpose

When chat is enabled, use OpenAI through LangChain for conversation, tuning
suggestions, Python drafts and monitoring diagnosis. Keep the current tools,
grounded facts, saved history and exact-action human confirmation. Preserve an
explicit Ollama option for the evaluated local course demonstration. Chat remains
disabled until an operator enables it; merely installing the update makes no calls.

This extends C3/C5/C6/C7/C9 in the [course checklist](../project/course-requirements.md)
without removing the local model path, service separation, deployment or existing
acceptance obligations. Hosted success will not close the outstanding bounded
local-laptop deployment gap or retroactively pass failed local runs.

## Clarification and critique

Jacob selected **OpenAI as the default** and authorized **at most $2 total for
implementation testing**, reporting approximately $10 available in his API account.
The balance is user-reported, not inspected. This is a ceiling, not a spending
target, and includes smoke probes, failed/uncertain requests and reruns. No paid
calls occur while preparing this plan. Credentials will be configured outside Git.

Propose `gpt-5.4-mini` as the initial configurable model with reasoning effort
`none`, standard service tier and no hosted tools. Its documented function calling,
structured outputs and token prices make it a reasonable candidate for these
bounded tasks; account access and task quality are unverified. The
[model page](https://developers.openai.com/api/docs/models/gpt-5.4-mini) lists
$0.75 input and $4.50 output per million tokens. Recheck availability and pricing
before execution and record the actual returned model identity. This choice is
part of the design for review, not an assertion of tested reliability.

Hosted inference introduces external data transfer, ongoing costs, connectivity
and provider limits. Keeping only Ollama is simpler and already has local evidence;
it does not provide the requested hosted option. Changing its origin alone fails
the current local-host, model-tag, runtime and tokenizer contracts. A separate
adapter avoids weakening those boundaries. Replacing the host with an autonomous
agent framework would unnecessarily change authorization and replay behavior.

No additional product-intent decision is required beyond review of the proposed
model, finite limits, data transfer and compatibility behavior below. Key/account
access is an execution prerequisite. Material model/protocol/budget changes require
updated review; an unavailable model must not trigger automatic substitution.

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | OpenAI is the default backend; chat stays opt-in; explicit Ollama still works. | Configuration/factory tests and explicit local-profile regression. |
| F2 | Functional | LangChain generates grounded guidance and bounded training/tuning proposals using existing tools. | Original ten conversation scenarios and real HTTP confirmed-action walkthrough. |
| F3 | Functional | All four draft profiles generate actual Python; current syntax/API validation and review remain required. | Original seven snippet scenarios, saved draft/history replay, no draft-triggered submission. |
| F4 | Functional | Diagnosis separates observations from interpretation and cites supplied observations only. | Normal/partial/empty monitoring cases; real observation/diagnosis HTTP exercise. |
| F5 | Compatibility | Replay, history and decisions work without inference; public schemas, scoping and submission idempotency remain stable. | Scripted HTTP and real MongoDB/recovery gates; zero provider calls on replay. |
| N1 | Security | Only an enabled OpenAI backend sends redacted context to the official provider; secrets never enter public results/logs/traces. | Captured SDK HTTP requests, nested-secret tests and deployment diff review. |
| N2 | Resources | Preserve finite context, byte, output, call and deadline limits; no SDK retries or hidden follow-up generation. | Actual SDK transport tests at boundaries, cancellation and cleanup. |
| N3 | Cost | All live implementation testing together stays within $2.00. | Persistent conservative reservation ledger, refusal tests and retained usage evidence. |

## Constraints and scope

Preserve `/api/v1` request/response models, trusted project context, correlation
IDs, transaction fences, saved deadlines, unknown-action recovery and stable
submission keys. Keep validation-only selection, training-fitted preprocessing,
artifact verification and serial CPU workers. No database migration, new public
route, automatic code execution, automatic remediation or model fine-tuning.

Use [the host interface](../../src/ml_pipeline_pro/conversation_model.py),
[lifespan factory](../../src/ml_pipeline_pro/conversation_api.py) and
[host service](../../src/ml_pipeline_pro/conversation_service.py). Observe the
[adapter boundary](../memory/conversation-ollama-boundary.md),
[capability lifecycle](../memory/conversation-snippet-lifecycle.md),
[supplied facts](../memory/conversation-supplied-facts.md),
[snippet boundary](../memory/snippet-generation-boundary.md) and
[uncertain actions](../memory/conversation-action-uncertainty.md) findings.

## Design

1. **Configuration and rollout.** In `config.py`, accept `openai|ollama` and default
   `chat_backend` to `openai`. Retain `chat_enabled=false`, protocol `native`,
   60-second turn / 20-second model timeouts, five model calls, four tool calls,
   8192 context tokens and 1024 maximum output tokens. Resolve an unset model to
   `gpt-5.4-mini` only for OpenAI; Ollama still requires an explicit installed tag.
   Make model-tag validation backend-aware; keep the private Ollama origin check.
   OpenAI initially supports native protocol only: reject guided, local-tokenizer
   and unbounded-diagnostic combinations with a clear configuration error.
   Pin its endpoint to `https://api.openai.com/v1`; do not inherit alternate SDK
   base URLs, proxies, organization/project overrides or redirect credentials.
   Read `OPENAI_API_KEY` through an explicit settings alias into `SecretStr` and
   pass it explicitly to the client. Missing credentials leave the direct API,
   replay/history and saved decisions available; fresh inference fails safely
   with `model_unavailable`, without falling back to Ollama.

2. **LangChain adapter.** Add `conversation_openai.py` using `ChatOpenAI` with
   Responses API enabled. Lock a compatible `langchain-openai`/OpenAI SDK pair
   against existing LangChain dependencies; verify actual installed behavior
   before relying on constructor parameters. Own/close all inference and counting
   clients in the application lifespan. Implement `generate`, `generate_snippet`
   and `generate_monitoring` with existing `ModelStep`/`MonitoringStep` contracts.
   Reuse instructions and schema validation, disable tracing/callback export,
   streaming, SDK retries and automatic continuation. Keep all request state
   invocation-local; no shared last-response or provider conversation state.

3. **Tools and output.** Bind the existing domain proposals, snippet request and
   `finish_conversation`; set `parallel_tool_calls=false`. Initially set tool
   `strict=false` explicitly to preserve omitted/defaulted arguments and existing
   host missing-input behavior. The
   [function-calling documentation](https://developers.openai.com/api/docs/guides/function-calling)
   describes both this option and stricter schemas' required-field constraints.
   Host validation remains authoritative. Reject malformed arguments, duplicate
   JSON keys, unknown tools, multiple calls, refusals without a valid reply and
   mixed prose/calls. Map completion to `ModelReply`; retain the existing validated
   legacy JSON reply path. Snippet/monitoring invocations expose no domain tools
   and parse their existing JSON schemas, without repairing generated code.
   Prove LangChain converts host-synthesized assistant/tool messages and IDs into
   a valid Responses exchange; do not add provider response IDs to stored history.
   Reconstruct each request from the host's bounded messages, set `store=false`,
   and retain no provider-side conversation dependency.

4. **Admission, provenance and failures.** At the final SDK request boundary,
   check encoded bytes and use the official
   [input-token counter](https://developers.openai.com/api/reference/python/resources/responses/subresources/input_tokens/methods/count)
   on the same normalized model/input/instructions/tools/text-format fields.
   Count before every generation, including drafts and diagnosis, within the
   existing model-call deadline. Reject over-budget/invalid counts and fail closed
   if counting is unavailable; never substitute Qwen counts or silently truncate.
   Reserve output tokens including reasoning; validate returned usage, response
   status and decoded response bytes. Demonstrate count/send payload equality
   through SDK HTTP tests. This introduces a counting request, not an extra model
   generation; record both request types and their durations. Map timeouts to
   `chat_timeout`, limits to `chat_limit_exceeded`, malformed responses to the
   existing invalid-response error, and authentication/rate/quota/network failures
   to fixed `model_unavailable` messages. Never expose SDK exception bodies.
   Cancellation must propagate and release clients; uncertain paid calls remain
   charged in the testing ledger. Preserve safe backend/model/package/schema and
   instruction hashes using existing extensible provenance; add only narrowly
   reviewed allowlist keys if required. Never invent local artifact digests.

5. **Secrets and deployment.** Extend `logging.configured_secrets` and logger
   coverage to the OpenAI key/SDK so chat, monitoring, nested provenance, rejected
   drafts and logs share redaction. Keep raw code intact until the existing
   secret/AST validator rejects it. Document that prompts, bounded history and
   tool snapshots are transmitted externally; omit raw dataset/artifact uploads
   and authorization headers from model input. `store=false` does not promise
   zero retention; link the official
   [data controls](https://developers.openai.com/api/docs/guides/your-data).
   Update `.env.example`, README and conversation/snippet/monitoring guides.
   Add an explicit OpenAI Compose override and Kubernetes secret-reference setup
   for model/monitoring APIs, with no committed key or paid CI gate. Pin all
   existing local Compose/Kubernetes/example/evaluation profiles and Ollama test
   fixtures to `MLPP_CHAT_BACKEND=ollama` so the new default cannot reroute a local
   demo.

6. **One testing budget.** Add a serial, opt-in OpenAI evaluation runner with
   `MLPP_RUN_OPENAI_EVAL=1`, explicit model and one persistent ledger shared across
   all live scenarios/process restarts. Limit total authorization to $2.00;
   reserve at most $1.90 in requests, leaving $0.10 margin. Before each request,
   durably reserve its full upper-bound cost using counted input at the uncached
   rate plus maximum output (including reasoning) at the output rate, with decimal
   arithmetic rounded upward. Include any documented counting charges; verify
   their billing before starting, or reserve conservatively. Never rely on cache
   savings or release uncertain reservations. Before the counting request itself,
   reserve its conservative maximum charge from the configured context ceiling;
   refuse to call if its price cannot be bounded. Reconcile completed requests with
   usage, retain reservations for missing usage, and stop when another maximum
   request cannot fit. Disable retries/parallel test runs and retain the ledger
   across reruns; refuse missing/stale pricing or a changed model. No automatic
   escalation to the remaining account balance. This bounds this controlled
   runner's spend, not unrelated account usage or normal interactive application
   use. Do not expose its test budget as a global application spending guarantee.

## Acceptance and verification

Implement after design approval in three checked, committed/pushed slices:
configuration/secret/provider foundation; complete adapter and HTTP capabilities;
then deployment/docs, budget runner and retained acceptance. Fetch/compare upstream
and `origin/main` before each slice and push, integrating incoming history and
rerunning affected checks without force-pushing.

For F1/F5/N1/N2, run deterministic actual-SDK HTTP and application-lifespan tests
without paid calls: provider selection; missing key; credential isolation; model
validation; exact request/count equality; schema round trips; malformed/multiple
outputs; token/byte ceilings; refused/truncated replies; 401/429/5xx; timeout,
cancellation/closure; nested-secret redaction; and replay/history/decision routes
with a transport that fails if inference is attempted. For N3, exercise exact-fit,
over-cap, rounding, uncertain calls, changed pricing/model and restart reuse of
the reservation ledger before any live probe. Preserve existing assertions.

Run all repository fast gates and packaging checks after application slices:

```powershell
uv sync --locked --extra training
uv run --locked --extra training ruff check .
uv run --locked --extra training ruff format --check .
uv run --locked --extra training pytest -m "not integration" --cov
uv pip check
uv build
```

F5 also requires [ordinary integration](../guides/verification.md#ordinary-integration)
with both `MLPP_RUN_INTEGRATION=1` and `MLPP_RUN_WORKER_INTEGRATION=1`, running
`uv run --locked --extra training pytest -m "integration and not recovery"`.
Run the separate [isolated recovery setup](../guides/verification.md#run-the-suite)
serially with `MLPP_RUN_RECOVERY_INTEGRATION=1` and
`uv run --locked --extra training pytest -m recovery`; retain existing transaction,
ownership and killed-process tests. Use scripted OpenAI transport where appropriate
so ordinary CI/integration never consumes the $2. Validate Compose/Kubernetes
configuration and secret references without printing populated credentials.

For F2/F3, parameterize the [existing evaluations](../../evaluations/conftest.py)
by provider without weakening the original ten conversation/seven snippet scenarios
or local gates. The new opt-in runner must execute those assertions under the
existing default timing limits, not label them local-model passes. Then perform
one real-ID HTTP walkthrough: inspect, train only after exact confirmation, compare,
propose bounded validation-only tuning, save/replay a Python draft, and diagnose
normal/partial/empty observations (F4). Run serially within the shared $2 envelope;
stop when complete rather than spending the balance. Budget exhaustion, missing
services, account denial and selected skips remain explicit acceptance gaps.

Record source revision, installed SDK/LangChain versions, requested/returned model,
instructions/schema hashes, pricing source/date, sanitized raw outputs, timings,
usage and ledger reservations in retained evidence. Distinguish fixture metrics
from real runs, estimated charges from provider-reconciled charges and hosted
results from local evidence. Jacob reviews sample guidance/drafts/diagnosis for
usefulness. Seek independent review of request isolation, lifecycle and token/cost
arithmetic; record reviewer, submitted scope, findings/resolutions or unavailability.
The implementing agent's self-review is not independent review.

## Risks and rollback

Provider/model changes can alter arguments, cost or quality; test the exact model
and locked dependency set. A timeout may still incur billing. Counting increases
latency and sends the same redacted context to the provider before generation.
If the installed LangChain/SDK cannot preserve request admission or host message
semantics, stop and revise the plan rather than bypassing checks or changing host
ownership. Do not increase limits just to pass acceptance.

Operators with a prior local model and no backend setting must explicitly select
Ollama during upgrade. Roll back configuration to `MLPP_CHAT_BACKEND=ollama` plus
the prior local tag/protocol/tokenizer and deployment profile, or disable chat.
Revert implementation commits normally if necessary; no data migration is needed.
Saved turns/drafts/actions retain their original provenance, IDs and deadlines;
never replay a completed turn by generating again or recreate an unknown action.

## Human review and approval

Jacob confirmed the default-provider change and $2 total test ceiling on October
20 in this session. This is approval of those requirements only. Written-plan
approval, reviewer/date/reference and approved scope remain pending; no application
implementation or paid execution is authorized by creating this document alone.

## Implementation outcome

Not implemented. This change adds the plan only. No new model, application,
integration, deployment or paid acceptance results are claimed. Record revisions,
commands/environment/model identities, requirement mapping, raw evidence, test
justifications, review/resolutions, deviations, durable findings and completion
commit/push results here after implementation. Plan preparation checks and its
commit/push outcome are reported separately in the accompanying session response.
