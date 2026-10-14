# Guided midterm conversation

Use the pinned 7B profile from [local model setup](local-model-setup.md), the
[domain Compose stack](domain-services.md), and the host Qwen factory. Native mode
remains the default; explicitly select guided mode for this demonstration:

```powershell
$env:MLPP_CHAT_ENABLED = 'true'
$env:MLPP_CHAT_PROTOCOL = 'guided'
$env:MLPP_CHAT_MODEL = 'mlpp-qwen2.5:7b-instruct-q4_K_M-json-tools-v1'
uv run --locked --extra training uvicorn examples.qwen_chat_app:create_app --factory `
    --port 8001 --no-access-log
```

The API on 8001 uses MongoDB/Redis and tools on 8000. Use the same project/key on
both. Start with `Inspect experiment YOUR_ID` or `Inspect model YOUR_ID`; then ask
for training with your dataset/model IDs and per-trial runtime. For tuning provide
a validation objective, trial count and total runtime as well. Ask to compare
saved experiments before a tuning suggestion. Review the pending action and use
the existing [exact confirmation workflow](conversation-development.md).

Generate Python with `Generate Python ...` (optionally `Please`), using the four
[draft profiles](snippet-generation.md). Drafts never submit work or execute code.
Replay/history are durable and do not generate again. Responses with unsupported
grammar/evidence fail safely. Current reads supply facts; model prose remains an
interpretation. Test metrics never select tuning winners.

Guided mode constrains one JSON step and uses small host guards for explicit
English absence and `Inspect [experiment|model|dataset] ID` commands. It is not
general intent recognition or proof that every positive value was supplied.
Historical assistant records retain evidence/status/interpretation; earlier user
instructions are not replayed as current input. Exact confirmation remains required.

## Reproduce acceptance

The original ten/seven scenarios and budgets remain intact. Synthetic records in
these gates are not measured ML results. Neither gate executes generated Python.

```powershell
$env:MLPP_RUN_LOCAL_MODEL_EVAL = '1'
$env:MLPP_CHAT_PROTOCOL = 'guided'
try {
    uv run --locked --extra training pytest evaluations/test_conversation_model.py `
        --local-model 'mlpp-qwen2.5:7b-instruct-q4_K_M-json-tools-v1' `
        --token-counter 'evaluations.qwen_counter:create_counter' `
        --eval-output 'artifacts/guided-demo/conversation.json'
    if ($LASTEXITCODE -ne 0) { throw 'Conversation acceptance failed.' }
    uv run --locked --extra training pytest evaluations/test_snippet_model.py `
        --local-model 'mlpp-qwen2.5:7b-instruct-q4_K_M-json-tools-v1' `
        --eval-output 'artifacts/guided-demo/snippets.json'
    if ($LASTEXITCODE -ne 0) { throw 'Snippet acceptance failed.' }
} finally {
    Remove-Item Env:MLPP_RUN_LOCAL_MODEL_EVAL
}
```

October 13: all ten conversation and seven snippet cases pass on one evaluated
7B revision/profile, with exact transmitted prompt/runtime counts. A real local
model/MongoDB HTTP run saves/replays a validated draft, checks history/foreign
access and creates no experiment. See [retained evidence](../evidence/2026-10-13-guided-demo/results.json)
and [outputs for human review](../evidence/2026-10-13-guided-demo/human-review.md).
Jacob reviewed the saved examples as clear/useful on October 13. Final delivery
gates pass all ten conversation and seven snippet cases with the original 20-second
call and 120-second suite limits. Earlier slower runs timed out on the longer tuning
draft; their throughput variation is not attributed to an established cause. A
30-second diagnostic finished every call below 20 seconds, so no deadline change
was selected. The 3B alternative failed semantics and is excluded. A fresh checkout,
environment/storage and full Kubernetes/local-model walkthrough also pass. See
[final evidence and limits](../evidence/2026-10-13-midterm-delivery/README.md).
Older native failures remain historical evidence; these results do not establish
universal model reliability, another runtime or concurrent capacity.

Guided provenance `tools_hash` identifies the base protocol schema; actual format
schemas vary with current reads/guards and their hashes are retained in the live
gates. Snippet `instructions_hash` identifies the base instructions;
`rendered_instructions_hash` identifies the selected method's syntax guidance.
Header hints contain constant environment variable names, never credentials.
