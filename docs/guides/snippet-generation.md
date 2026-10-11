# Generated Python drafts

With [local model setup](local-model-setup.md) complete and chat enabled, ask
`POST /api/v1/chat` for a Python integration snippet. The supported profiles are
`list_experiments`, `compare_experiments`, `create_experiment`, and
`create_tuning_job`. LangChain generates the Python through the installed model;
the host validates and saves the result in the conversation turn.

Examples of conversational requests:

- "Generate Python listing experiments, limit 50, offset 0. Return a draft."
- "Generate Python comparing exp-a and exp-b by validation_f1. Return a draft."
- "Generate Python submitting training for dataset dataset and model model, with
  a 10-second runtime. Return a draft without submitting training."
- "Generate Python submitting tuning for dataset dataset and model model, with
  10 seconds per trial, validation_f1 objective, two trials and 40 seconds total.
  Return a draft without submitting tuning."

Use your registered IDs. These example identifiers describe inputs, not evidence
that those records exist or that an experiment has completed. Missing submission
identifiers, runtime, objective or tuning limits produce `needs_input` with
specific `inputs.*` locations. See [API access and replay](../reference/api.md).

## Request and inspect a draft

Use the same project headers and request replay rules as other chat requests:

```powershell
$headers = @{ 'X-Project-ID' = 'demo' }
if ($env:MLPP_API_KEY) { $headers['X-API-Key'] = $env:MLPP_API_KEY }
$body = @{
    request_id = 'snippet-list-001'
    expected_revision = 0
    message = 'Generate Python listing experiments, limit 50, offset 0. Return a draft.'
} | ConvertTo-Json
$turn = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/v1/chat' `
    -Headers $headers -ContentType 'application/json' -Body $body
$turn.snippet
```

Inspect `status`, `required_inputs` and `error` on the turn first. A completed
generation has a `snippet` with `status=validated` or `status=rejected` and
`review_required=true`. A rejected result exposes fixed validation issues and
omits code. An unavailable model or exhausted budget saves a failed turn when
storage and turn ownership still permit completion. Storage failure returns the
existing safe error with request/conversation identifiers for inspection.

A validated draft contains `code` and provenance: actual model/runtime identity,
generation instruction hash, normalized safe input hash, observed generation
duration, and reported token counts when supplied. Replaying the original request
or reading conversation history returns the saved draft and provenance without
generating again. Old schema-v1 turns without `snippet` remain readable and do
not acquire generated-code evidence.

Review the code, chosen IDs, configuration and budgets before using it. Validation
checks a restricted Python/API grammar; it does not establish usefulness or
arbitrary Python safety. The application never executes generated Python or
submits a training/tuning job while generating a snippet. A saved draft is separate
from an exact-action proposal and cannot be approved through the action routes.

## Supported Python subset

Drafts use `os`, `httpx` and optionally `json` imports; literal/environment
assignments; and one multiline `with httpx.Client(...)` block containing one
literal supported HTTP request, `response.raise_for_status()` and
`data = response.json()`. Variable rebinding, dynamic calls/imports, definitions,
classes, loops, shell/file access, extra requests and arbitrary destinations reject.
The host checks the exact method/path/query/body against the profile's canonical
API contract and supplied normalized inputs, including runtime/trial budgets.
Comparison uses GET with repeated `experiment_id` query keys and a validation
metric. List responses have the existing bounded page size.

Drafts take the API origin, project and key from `MLPP_API_ORIGIN`,
`MLPP_PROJECT_ID` and `MLPP_API_KEY` in the engineer's execution environment.
Submission drafts also require a caller-chosen stable `MLPP_SUBMISSION_KEY` for
`Idempotency-Key`; reads omit it. The origin has no path suffix. Clients disable
redirects and proxy inheritance and use a timeout between zero and 30 seconds.
Known secrets in generated code cause rejection rather than accepted rewritten
code. Credentials from the host request are never generation inputs.

Generation spends one additional model call within the original conversation's
call limit and deadline; it receives no fresh turn budget and performs at most
one generation call. The adapter admits the exact SDK request with the complete
output-token reservation. Code has an 8 KiB UTF-8 limit within the existing saved
record cap. Ordinary CI uses scripted generation and requires no model download.

## Verify with an installed model

The A2 evaluation is separate from A1's original ten conversation scenarios:

```powershell
$env:MLPP_RUN_LOCAL_MODEL_EVAL = '1'
try {
    uv run --locked --extra training pytest evaluations/test_snippet_model.py `
        --local-model 'mlpp-qwen2.5:7b-instruct-q4_K_M-json-tools-v1' `
        --eval-output 'artifacts/snippet-evaluation/results.json'
} finally {
    Remove-Item Env:MLPP_RUN_LOCAL_MODEL_EVAL
}
```

It checks all four profiles, missing inputs, hostile record text and an
unsupported profile with at most seven generation calls, 1,024 output tokens per
call and a 120-second suite deadline. It saves source/model/prompt provenance,
safe generated outputs and validation results. It does not execute Python,
retry/repair model output, change the original A1 gate, or establish an onboarding
or performance result. Human usefulness review and independent boundary review
remain required. See [A2 outcome](../plans/2026-10-08-person-a-snippet-generation-plan.md#implementation-outcome).
