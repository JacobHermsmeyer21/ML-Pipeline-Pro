# A native completion function does not establish model reliability

Date: October 10, 2026. Scope: the approved adapter-only `finish_conversation`
experiment with the installed Qwen 2.5 7B JSON-tools profile and Ollama 0.40.2.

[Raw evidence and provenance](../evidence/2026-10-10-typed-completion/results.json)
retain the acceptance failure, separate diagnostic and passing host/service gates.

The [implementation outcome](../plans/2026-10-09-conversation-typed-completion-plan.md#implementation-outcome)
records user approval, strict translation to the existing reply schema, unchanged
public tools/permissions, SDK/host/store checks and retained execution evidence.
The original ten-scenario live gate passed only three scenarios. A separate
read-only diagnostic observed one initial read followed by 23 repeated native
reads in one response ending with `done_reason=length`; rejection is required,
not a transport recovery opportunity. That diagnostic is separate from acceptance.

The saved acceptance proposal copied a 40-second total tuning budget into the
per-trial budget instead of the requested 10 seconds. The missing-limits scenario
borrowed prior limits and proposed tuning instead of asking for the missing
inputs. No mutation was dispatched. Adding a native completion channel did not
fix these semantic failures; do not relax assertions, repair/rewrite model
arguments or infer that a larger model necessarily solves them.

The SDK projects parameter metadata before sending all 14 native schemas.
Host byte admission includes full schemas; exact token admission includes the
transmitted projection. The new real-runtime request counted exactly 7,680 input
tokens plus 512 reserved output at context 8,192; 7,681 input failed before HTTP
inference. Old 13-function counts remain historical. Keep verified token
admission separate from model-quality acceptance.

Independent review, human model-quality review and complete clean-checkout
onboarding remain outstanding. Revisit after another reviewed prompt/protocol,
runtime or model change; preserve the original semantic acceptance checks.

Later [guided acceptance](../guides/guided-midterm-demo.md) supplies passing
ten/seven gates, human examples and clean onboarding for that separate protocol.
It does not establish native completion reliability or retrospectively pass this
three-of-ten run. See [current status](../project/project-status.md) for remaining
review and bounded CPU-laptop deployment limits.
