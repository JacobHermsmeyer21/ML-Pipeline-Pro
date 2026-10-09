# Conversation facts must exclude default-only API fields

Recorded October 8, 2026 on the host-loop step, baseline `8b02465`.

The dispatcher validates public API records using schemas that also define
defaults for record creation. Its identity/time guard prevents invented IDs,
but omitting `ExperimentResult.status` still produced a normalized `queued`
value. A new host-loop regression removed only status from an otherwise valid
API response: the reply completed with a supposedly verified queued fact.

The conversation host now captures each read's actual response locally and
projects validated values onto supplied fields, recursively. Grounding rejects
a fact for an absent field instead of borrowing a schema default. Capture is
per call, with no shared last-response state across conversations. Exported
dispatcher behavior and input-default expansion remain unchanged. Related
parent/source IDs are citation evidence for relationships; their own fields
require a fetched record. Facts use current-turn success snapshots and reject
ambiguous record IDs across kinds.

Evidence: [response capture/loop](../../src/ml_pipeline_pro/conversation_service.py),
[supplied-field renderer](../../src/ml_pipeline_pro/conversation_grounding.py),
[missing-status regression](../../tests/test_conversation_service.py), and
[plan outcome](../plans/2026-10-06-conversation-workflows-plan.md#person-a-bounded-host-loop-october-8-2026).
That outcome links the retained before-fix failure and final checks.

This proves source consistency for structured facts, not the truth of arbitrary
generated prose, semantic budget extraction, actual model quality, or independent
review. A real-model gate and exact-action human review remain required. Revisit
when adding tool output shapes, fact fields or response-schema defaults; never
use reconstructed defaults as measured observations.
