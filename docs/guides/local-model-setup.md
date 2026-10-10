# Local Qwen setup and token verification

This is an explicit development setup for Person A's approved A1 work.
Token admission has real-runtime evidence; the conversation quality gate still
fails. Keep C3/C5 outstanding. The application and tests never download models.

## Verified setup profile

The retained runs use Windows 10, Python 3.11.5, Ollama 0.40.2, the locked
LangChain SDKs and `tokenizers==0.22.2`. The machine has 31.1 GiB RAM and an
AMD Radeon RX 9070; Ollama reports Vulkan acceleration. These observations do not
establish capacity for another machine or concurrent workloads.

| Artifact | Observed identity and scope |
| --- | --- |
| `qwen2.5:7b-instruct-q4_K_M` | Original 4.7 GB pre-trained weights; its stock-template counter is verified for diagnosis. |
| `mlpp-qwen2.5:7b-instruct-q4_K_M-json-tools-v1` | Same 7B weights with the checked-in native tool template; six of ten scenarios passed in its retained quality run. |
| `mlpp-qwen2.5:14b-instruct-q4_K_M-json-tools-v1` | Same 9.0 GB Qwen 14B weights with that template; three of ten scenarios passed in its retained quality run. |

Both weight artifacts carry Apache 2.0 licenses in their installed metadata.
Retain and inspect the license when setting up another machine. See the official
[7B artifact](https://ollama.com/library/qwen2.5:7b-instruct-q4_K_M),
[14B artifact](https://ollama.com/library/qwen2.5:14b-instruct-q4_K_M), and
[Windows runtime/GPU setup](https://docs.ollama.com/windows).

The table's quality results are the historical October 9 runs. After the approved
[typed-completion change](../plans/2026-10-09-conversation-typed-completion-plan.md),
the 7B JSON-tools profile passed three of ten unchanged scenarios on October 10.
The new 14-function SDK payload admitted 7,680 input tokens plus 512 reserved
output tokens at context 8,192; input 7,681 was rejected before HTTP inference.
These observations verify admission, not conversation quality. No new 14B
quality run or model-weight change is claimed.

The [counter](../../src/ml_pipeline_pro/conversation_qwen_counter.py) accepts only
the pinned artifact/runtime/template identities and tokenizer checksum. The
template fingerprint in public adapter provenance hashes its canonical JSON
string; it differs from the template blob's raw SHA-256. No generic token estimate,
automatic profile selection or alternate-runtime fallback is supplied.

## Install and start the standalone runtime

Use the official Ollama 0.40.2 Windows standalone archive. Download it into an
ignored local directory and verify its published asset checksum:

```powershell
$setupRoot = Join-Path (Get-Location) '.tools/local-model-setup'
New-Item -ItemType Directory -Force -Path $setupRoot | Out-Null
$archivePath = Join-Path $setupRoot 'ollama-windows-amd64-v0.40.2.zip'
curl.exe --location --fail --output $archivePath `
    'https://github.com/ollama/ollama/releases/download/v0.40.2/ollama-windows-amd64.zip'
if ($LASTEXITCODE -ne 0) { throw 'Runtime download failed.' }
if ((Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant() -ne `
    'e29ad1d5063dd4b54b2492d9b00adab2cff9621bfa654b6c92aa8d6f1fdfe7fc') {
    throw 'Runtime checksum mismatch.'
}
Expand-Archive -LiteralPath $archivePath -DestinationPath (Join-Path $setupRoot 'ollama-v0.40.2')
```

In a dedicated terminal, set the server's environment and run it explicitly:

```powershell
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_MODELS = Join-Path (Get-Location) '.tools/local-model-setup/models'
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_GO_TEMPLATE = '1'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_VULKAN = '1'
& '.tools/local-model-setup/ollama-v0.40.2/ollama.exe' serve
```

These process-local values do not change training-worker concurrency. The
counter requires Go-template rendering. Restart the API after changing the
runtime, template, model tag or tokenizer; its inspected profile is cached.
The standalone server can create its normal local Ollama configuration/key
files. Weight storage is directed to the ignored repository directory above.

## Install an explicit artifact and tokenizer

From another terminal, select the artifact for the failure you want to reproduce:

```powershell
& '.tools/local-model-setup/ollama-v0.40.2/ollama.exe' pull qwen2.5:14b-instruct-q4_K_M
if ($LASTEXITCODE -ne 0) { throw 'Explicit model installation failed.' }
uv sync --locked --extra training
uv run --locked --extra training python examples/setup_qwen_profile.py --base-model 14b
if ($LASTEXITCODE -ne 0) { throw 'Local profile creation failed.' }
```

Use `7b` and `qwen2.5:7b-instruct-q4_K_M` to reproduce the smaller profile.
The [setup script](../../examples/setup_qwen_profile.py) checks the installed
source identity before creation and rejects an occupied target tag with another
identity. It reuses installed weights and performs no model pull. The
[template](../../examples/qwen-json-tools.gotmpl) JSON-encodes function definitions
and requests one native call per response. It preserves the pre-trained weights
and `<tool_call>` protocol. This fixes observed template formatting; it does not
establish model understanding or reliable structured replies.

Download the immutable official tokenizer data separately:

```powershell
$tokenizerPath = Join-Path (Get-Location) '.tools/local-model-setup/tokenizer.json'
curl.exe --location --fail --output $tokenizerPath `
    'https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/resolve/a09a35458c702b33eeacc393d103063234e8bc28/tokenizer.json'
if ($LASTEXITCODE -ne 0) { throw 'Tokenizer download failed.' }
if ((Get-FileHash -LiteralPath $tokenizerPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne `
    'c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539') {
    throw 'Tokenizer checksum mismatch.'
}
```

All 151,665 available vocabulary entries and 151,387 merges match both installed
GGUFs; their 399 padding vocabulary entries are marked unused. Their BOS setting
is false. Eight stock-profile probes matched exact runtime rendering and prompt
counts. A real SDK call admitted 7,680 input tokens plus 512 reserved output tokens
at context 8,192; input 7,681 failed before HTTP dispatch. Retained evidence is
linked from the [conversation plan outcome](../plans/2026-10-06-conversation-workflows-plan.md#implementation-outcome).
Those are token-boundary observations, not conversation-quality acceptance.

## Reproduce the live gate and host API

The gate uses synthetic records, never dispatches a mutation, and retains failed
scenarios. The selected profile has failed this gate; expect that failure until
the reviewed follow-up fixes its protocol/quality behavior.

```powershell
$env:MLPP_RUN_LOCAL_MODEL_EVAL = '1'
try {
    uv run --locked --extra training pytest evaluations/test_conversation_model.py -m local_model_eval `
        --local-model 'mlpp-qwen2.5:14b-instruct-q4_K_M-json-tools-v1' `
        --token-counter 'evaluations.qwen_counter:create_counter' `
        --eval-output 'artifacts/local-model-evaluation/results.json' `
        --junitxml 'artifacts/local-model-evaluation/junit.xml'
    $evaluationExit = $LASTEXITCODE
} finally {
    Remove-Item Env:MLPP_RUN_LOCAL_MODEL_EVAL
}
if ($evaluationExit -ne 0) { throw 'Live model acceptance failed; retain the JSON and JUnit evidence.' }
```

For host API development, use the explicit
[factory](../../examples/qwen_chat_app.py) after starting MongoDB/Redis and the
backend workers per [setup](setup.md#develop-the-api-on-your-host):

```powershell
$env:MLPP_CHAT_ENABLED = 'true'
$env:MLPP_CHAT_MODEL = 'mlpp-qwen2.5:14b-instruct-q4_K_M-json-tools-v1'
uv run --locked --extra training uvicorn examples.qwen_chat_app:create_app --factory `
    --port 8001 --no-access-log
```

This API listens on 8001 and its tools use the existing backend on 8000. Keep the
same project/key configuration on both APIs. The factory is offline at startup;
inspection and tokenizer loading occur within the first bounded generation call.
Missing/unsupported setup fails before inference while direct API and audit reads
remain available. History, exact decisions, budgets and project access retain
their existing contracts. No tokenizer or weights are packaged in the wheel or
container. Model-quality acceptance, independent review and a successful complete
clean-checkout conversation tutorial remain outstanding.
