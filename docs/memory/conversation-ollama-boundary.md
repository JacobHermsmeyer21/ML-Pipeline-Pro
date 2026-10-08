# Ollama requests need SDK-normalized admission and local credential isolation

Recorded October 8, 2026 on the Person A adapter slice, baseline `8637173`.

The locked Ollama SDK (`0.6.3`) inherits `OLLAMA_API_KEY`, defaults to following
redirects, and normalizes LangChain messages/tools before HTTP submission.
An adapter regression comparing the pre-SDK token-counter input with the actual
HTTP JSON failed: message fields and tool schemas differed. Token admission now
runs at the HTTP request hook, where the counter receives the exact sent payload.
Both SDK clients remove inherited authorization, disable redirects/proxy
inheritance/retries, and close through the adapter lifecycle.

[Adapter source](../../src/ml_pipeline_pro/conversation_ollama.py) and
[actual-SDK HTTP regressions](../../tests/test_conversation_ollama.py) establish
these boundaries without a live runtime. Response hooks also validate raw native
arguments before LangChain can normalize malformed output. The tests cover
compressed decoded-byte limits and cleanup as well as exact request equality.
The [approved plan outcome](../plans/2026-10-06-conversation-workflows-plan.md#person-a-local-adapter-october-8-2026)
links retained fast-gate evidence and limitations.

This is not a verified tokenizer: generation requires an injected counter
matching the chosen artifact and runtime chat/tool template. The artifact,
counter accuracy, overflow behavior, live model quality, and immutable identity
during use remain acceptance work. Revisit request normalization, credential
inheritance, lifecycle access, and response hooks when upgrading the locked SDKs.
