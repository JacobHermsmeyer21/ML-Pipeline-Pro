# A successful lookup does not require the model to return a fact

October 14, 2026: the [approved correction plan](../plans/2026-10-13-requested-inspection-facts-plan.md)
records a demo reply with validation prose but no structured facts. The prior
guided schema allowed omission or an empty list after a successful lookup.

The [current-request guard](../../src/ml_pipeline_pro/conversation_guidance.py)
recognizes narrow positive inspection clauses and requires references only for
supplied scalar fields on the matching current successful record lookup.
The adapter rejects decoded replies that ignore this constraint. It never inserts
references or values; the existing ledger renders values from supplied snapshots.

[Regression cases](../../tests/test_conversation_guidance.py) cover exact SDK format
and token-admission payload, zero metrics, status, absent fields, relationship and
foreign evidence, history/embedded instructions, negation, and persisted host
failure/replay without another model call. These are scripted boundary tests.
Live-model grammar acceptance, failed-record reproduction and a fresh walkthrough
remain unverified on this checkout because its services/runtime are unavailable.
Revisit when widening supported request syntax or tool snapshot shapes.

Later October 14: [prerequisites are installed](../evidence/2026-10-14-prerequisite-setup/README.md)
and all remote CI jobs pass, including 63 real-service cases without skips. The
local CPU model attempts fail (2/10 dialogue, 0/7 snippets); Windows restart is
required for local containers. Successful live correction acceptance remains open.

Same-day branch reconciliation confirmed that the locked LangChain/Ollama SDK
removes tool-message `name` before HTTP admission. Evaluation observers must
derive required references from the original host messages before that projection;
recomputing them from the transmitted messages loses the constraint and falsely
rejects the correct schema. Both gates now retain those references while comparing
the complete actual SDK schema. [Scripted evidence and regression](../evidence/2026-10-14-branch-sync/README.md)
verify this without claiming a new real-model pass.

October 15 evidence update: the [October 14 workstation run](../evidence/2026-10-14-rx9070-walkthrough/README.md)
on clean `add6862` passes all ten/seven original model scenarios and the complete
rebuilt-service walkthrough. A fresh actual experiment returns the explicitly
requested validation-F1 reference and host value 1.0. This supplies real-model
fresh-record acceptance; original failed-record reproduction, separate boundary
review and the other CPU laptop's failed acceptance remain outstanding.
