# Qwen token counts depend on the pinned Ollama template implementation

Date: October 9, 2026. Scope: explicit Qwen 2.5 Q4_K_M / Ollama 0.40.2 profiles.

The adapter's `template_hash` is the canonical JSON fingerprint of the template
string. A raw template blob SHA-256 is a different identity. The first live
attempt rejected that mismatch before inference; do not interchange the hashes.

In this runtime's Go template path, `templateToolFunction` has no `String()`
method. The stock Qwen template's `{{ .Function }}` therefore renders a Go struct,
despite the surrounding text calling it JSON. Runtime render-only inspection
confirmed this mechanism. The stock counter mirrors that output; the explicit
JSON-tools profile changes it to `{{ json .Function }}` and requests one native
call. Its weights and native `<tool_call>` protocol are unchanged.

The [counter source](../../src/ml_pipeline_pro/conversation_qwen_counter.py)
checks artifact/runtime/template identities and a checksum-pinned local
tokenizer. The [retained fixtures](../../tests/fixtures/qwen_runtime_render.json)
check actual stock-runtime rendering, including Unicode, typed schema projection,
Go number/JSON formatting and collated messages. Eight runtime probes matched
prompt counts; a real SDK call admitted 7680 input plus 512 reserved output at
8192, while 7681 failed before HTTP dispatch.

[Shared raw evidence and provenance](../evidence/2026-10-09-qwen-counter/results.json)
also retain all six failed live attempts. Prompt/schema clarification and the
JSON-tools profile improved some 7B scenarios, but neither 7B nor 14B passed the
unchanged ten-scenario gate. Replies included prose appended to JSON, malformed
citation structure, omitted proposals and incorrect per-trial budgets. Do not
extract a convenient JSON substring, relax assertions or equate a larger model
with a fix. A typed completion tool is an unimplemented design hypothesis that
requires review, and would still need semantic budget/evidence acceptance.

October 10 update: the user approved that experiment and the
[typed-completion outcome](../plans/2026-10-09-conversation-typed-completion-plan.md#implementation-outcome)
records its implementation. The selected 7B profile passed only three of ten
unchanged scenarios; adding a completion function does not establish quality.
See [the new finding](conversation-typed-completion.md) for observed repeated
calls, budget/history errors and the new 14-function admission evidence.

Limits: these observations apply to the exact pinned text/Go-template profiles.
They establish neither conversation delivery nor concurrent capacity. Independent
review and complete clean-checkout onboarding remain unavailable. Revisit after
changing the runtime, template, tokenizer, model artifact or native protocol.
