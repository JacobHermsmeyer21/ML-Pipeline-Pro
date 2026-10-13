# Native Ollama lifecycle wrapping can hide snippet generation

Recorded October 13, 2026 at application revision `7754826` during a project audit.

`conversation_clients` wraps `OllamaConversationModel` instances/subclasses in
`_LazyOllama`. That wrapper exposes `generate`/`close` but no `generate_snippet`.
`ConversationService` discovers snippet support with `getattr`; a wrapped native
adapter therefore has no generator even if its underlying model implements one.
When it requests a draft, the host saves a failed `model_unavailable` turn.

The [endpoint probe](../evidence/2026-10-13-project-audit/snippet_route_probe.py)
uses a scripted native subclass, the canonical lifespan/HTTP route and existing
in-memory test storage. Direct service use succeeds with one generation call;
wrapped HTTP use fails before any generation call. A non-Ollama factory control
also succeeds through HTTP. [Observed results](../evidence/2026-10-13-project-audit/results.json)
retain the diagnostic and its limits. No application fix was made.

Scope: `QwenConversationModel` is a composition adapter, not an Ollama subclass,
and exposes `generate_snippet`, so its documented factory avoids this defect.
The default bare adapter also needs a verified token counter before inference.
This finding does not establish live-model quality or real-store correctness.

October 13 fix under the [approved midterm plan](../plans/2026-10-13-midterm-delivery-plan.md):
the lazy wrapper now exposes `generate_snippet`, prepares the native adapter and
delegates generation. The added
[HTTP regression](../../tests/test_conversation_api.py) failed before the fix and
passes afterward, including saved draft/history replay without reinference and
lifespan closure. This is scripted HTTP evidence, not live model acceptance.
The original audit/probe above remains historical evidence of the defect.

Revisit when the lifecycle or model-capability interface changes. Verify the
configured HTTP factory, lazy preparation, shared generation budget and closure
at the route boundary; direct host/model tests alone miss this wrapper branch.
