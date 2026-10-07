# API response defaults must not invent tool evidence

Recorded October 6, 2026 during the approved conversation tool implementation.

The shared `Record` schema generates an ID and UTC timestamps when they are
absent. These defaults are useful for new database records, but a tool parsing
an incomplete upstream response can accidentally produce invented record IDs
or times. Three regressions removing `id`, `created_at`, or `updated_at` from a
model-list response returned tool success before the response guard was added.

The dispatcher now requires upstream identity, project, schema-version, and
timestamp metadata before parsing public record schemas. It rejects incomplete
responses as `tool_invalid_response`. Source:
[response parser](../../src/ml_pipeline_pro/tools.py),
[boundary regressions](../../tests/test_tool_transport.py), and the
[approved plan/outcome](../plans/2026-10-06-conversation-tools-plan.md).
Before-fix failure evidence is retained locally in ignored
`artifacts/conversation-tools-validation/missing-fields-before.xml`.

This finding concerns parsing API evidence, not constructing new records or
changing repository defaults. Revisit when adding tool outputs or changing
response serialization; evidence metadata must be returned, not generated.
