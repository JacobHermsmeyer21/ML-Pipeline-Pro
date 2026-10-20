# OpenAI agent setup

OpenAI is the default agent backend. Chat remains disabled until enabled.
The agent still uses LangChain and the existing project-scoped tools; mutations
require separate exact-action human confirmation. Python drafts are saved for
review and never executed. Monitoring interpretations remain separate from observations.

## Host setup

Copy `.env.example` to `.env` only if `.env` does not already exist. Place the
following settings in that ignored file; never put the actual key in documentation,
chat, Git or a browser-side setting:

```dotenv
OPENAI_API_KEY=replace-with-your-key
MLPP_CHAT_ENABLED=true
MLPP_CHAT_BACKEND=openai
MLPP_CHAT_PROTOCOL=native
MLPP_CHAT_MODEL=gpt-5.4-mini
```

Remove a local `MLPP_CHAT_TOKENIZER_PATH` setting when selecting OpenAI. Keep the
local Ollama model-origin setting unchanged; it is not the hosted endpoint.
Restart the API after changing settings. Construction, history, replay and saved
action decisions do not make inference requests. A missing key keeps the direct
API available and returns `model_unavailable` for fresh generation. Authentication,
quota and network failures do not fall back to another provider.

Run `uv sync --locked --extra training`, then
`uv run --locked --extra training uvicorn ml_pipeline_pro.main:create_app --factory`.
The API also needs the normal MongoDB/Redis services; see the
[development setup](../../README.md#development-setup). Existing `/api/v1/chat`,
history/action, snippet and monitoring routes retain their contracts.
Monitoring remains its own service: start
`uv run --locked --extra training uvicorn ml_pipeline_pro.main:create_monitoring_app --factory --port 8002`
for its routes, or use the separate-domain Compose setup below.

The adapter uses the official HTTPS endpoint, Responses through LangChain,
reasoning effort `none`, standard tier, zero SDK retries and one tool call per
response. It counts the actual normalized request before generation and preserves
the 8192-token context, 1024-token output, five-model-call/four-tool-call,
20-second model-call and 60-second turn defaults. Counting is inside that deadline.
Provider latency or incompatible output can fail safely; do not enlarge limits
just to label a scenario successful. Guided/local-tokenizer/unbounded settings
are rejected for OpenAI.

Prompts, bounded history and supplied tool records leave the machine. Known keys
are redacted; raw datasets and training artifacts are not uploaded by this adapter.
Tracing is disabled. `store=false` avoids using provider response state for replay,
but is not a zero-retention promise; consult
[OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data).

## Local compatibility

For the retained local course demonstration, explicitly set
`MLPP_CHAT_BACKEND=ollama` and use the evaluated tag, guided protocol and tokenizer
from [local setup](local-model-setup.md). `compose.ai.yaml`, local Kubernetes
patches and Qwen examples select Ollama explicitly. Hosted success does not replace
the retained local evidence or close the bounded laptop deployment gap.

## Compose and Kubernetes

For separate domain services, use `compose.openai.yaml` as the last override:

```powershell
docker compose -f compose.yaml -f compose.services.yaml -f compose.monitoring.yaml `
    -f compose.openai.yaml up --build --wait --wait-timeout 300
```

This enables inference only on model/monitoring APIs and clears the credential
on workers, the scheduler and tuning API. Keep `.env` private. Avoid printing
rendered Compose configuration because interpolation includes the key.

For Kubernetes, follow [cluster setup](kubernetes-demo.md) and create a private
`mlpp-openai` Secret in `mlpp-demo` with key `OPENAI_API_KEY`, using your secret
manager or an ignored local env file. Never commit the populated Secret or pass
the key as a shell-command literal. The checked-in `deploy/kubernetes/openai-patch.json`
references that Secret without embedding it. For each of `model-api` and
`monitoring-api`, replace `DOMAIN_NAME` in a temporary copy with the container name
and apply it as a strategic merge patch. Validate readiness and review enabled
settings before making an inference request. Do not apply the local Ollama patch
after the OpenAI patch. No credential or paid test gate is added to CI.

## Verification and cost

Normal unit/integration/CI tests use scripted transports and make no paid calls.
The [approved plan](../plans/2026-10-20-openai-agent-provider-plan.md) authorizes
at most $2 for all live implementation testing, including failures and reruns.
The controlled runner uses one persistent reservation ledger and serial execution;
it reserves conservatively before sending and retains uncertain charges. Its
budget does not limit normal interactive use or other activity on the API account.
Do not delete/reset the ledger to resume a run. Actual API prices, account access,
live model quality and human usefulness remain separate acceptance checks.

From the repository root, with the key configured and current pricing reviewed:

```powershell
$env:MLPP_RUN_OPENAI_EVAL = '1'
uv run --locked --extra training python -m evaluations.openai_runner --suite all
```

The runner reuses the original ten conversation and seven draft scenarios and adds
two monitoring scenarios. It retains results under `artifacts/openai-provider/`
and refuses a stale pricing date, different model, concurrent runner or exhausted
ledger. Jacob approved counting at an estimated full input rate with a byte/framing
allowance because the dedicated counting tariff is unconfirmed. Reservations are
estimates and are retained even for completed requests; they are not a reconciled
provider bill. A missing/failed/unrun case remains outstanding.

October 20 acceptance: ten conversation and seven draft scenarios pass, along
with normal/partial monitoring and a real-ID HTTP/worker walkthrough including
empty-data rejection and offline replay. All live attempts together reserve an
estimated $1.686037. See [raw evidence and review limits](../evidence/2026-10-20-openai-provider/README.md).
Human usefulness review of the new hosted outputs remains pending.

## Rejected conversation replies

A saved turn with `status: failed` can be returned by `/api/v1/chat` with HTTP 200:
the turn was saved successfully, but its `error.http_status` records the internal
failure (for example, 422 for `model_invalid_response`). Inspect the turn's
`correlation_id` and `error.details.validation_stage` / `validation_reason`.
New validation failures use fixed categories for provider envelopes, reply schema,
host steps/usage and evidence resolution. Reasons distinguish unsupported fact
fields, absent fields, ambiguous records, unknown citations and nonscalar facts.
They contain no raw model output or rejected field names. Legacy failures retain
their generic message; unavailable details cannot be recovered retroactively.

The [reply-validation plan](../plans/2026-10-20-agent-reply-validation-plan.md)
has its own additional $0.25 authorization and $0.23 conservative reservation
stop. Its opt-in runner is `python -m evaluations.reply_validation_runner --phase
baseline` or `--phase acceptance`, with `MLPP_RUN_OPENAI_EVAL=1`. It uses the
existing demo experiment, creates fresh conversations, and submits no training or
tuning work. It saves each phase once and keeps a separate ledger under
`artifacts/agent-reply-validation/`; preserve reports and reservations on failure.
The earlier $2 ledger and authorization remain unchanged.
