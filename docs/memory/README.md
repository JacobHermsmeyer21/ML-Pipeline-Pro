# Project memory

Read this index at session start, then the entries relevant to the work. These are
evidence-linked project findings shared across tools. [AGENTS.md](../../AGENTS.md)
holds standing rules; [plans](../plans/template.md) hold change-specific decisions.

| Finding | Scope |
| --- | --- |
| [Source packaging admits an ignored nested example](source-package-ignore-exception.md) | Existing workspace versus clean checkout, Git/build selection discrepancy, archive inspection |
| [CPU inference can overrun observed API timeout boundaries](cpu-inference-timeout-overrun.md) | Retained slow prompt/late 504, correct 99-second direct first step, resource sampling gaps and unresolved mechanism |
| [Laptop Qwen prompt processing dominates the first read](qwen-prompt-processing-cost.md) | Exact token cost, slower 2/3-thread laptop screens, no retained optimization and incomplete CPU attribution despite process sampling |
| [Laptop prerequisites and reboot boundary](laptop-test-prerequisites.md) | Installed Docker/WSL/Ollama locations, restart requirement and CPU gate failures |
| [Requested inspection facts need a reply constraint](requested-inspection-facts.md) | Current scalar lookup references, omitted model facts and replay without repair |
| [Minimal monitoring/deployment boundaries](minimal-monitoring-deployment.md) | Immutable replay precision, scoped advice provenance, Kubernetes discovery and runtime setup |
| [Guided grammar needs semantic gates](guided-model-boundary.md) | Narrow intent guards, current snapshot facts and per-method snippet guidance |
| [Course scope requires pre-trained models and separate services](course-deliverable-scope.md) | Course acceptance, local inference, service architecture, and Kubernetes |
| [A read-only parent check cannot fence tuning child writes](tuning-parent-fence.md) | MongoDB transactions and ownership takeover |
| [Final evaluation must preserve recorded training artifacts](evaluation-artifacts.md) | Artifact persistence and recovery |
| [API response defaults must not invent tool evidence](conversation-response-evidence.md) | Conversation tools and public record provenance |
| [Ollama admission needs exact SDK requests and credential isolation](conversation-ollama-boundary.md) | Local conversation adapter, token admission, SDK lifecycle |
| [Conversation completion needs a parent write and BSON-precision time](conversation-store-replay.md) | Durable turn/proposal claims, replay and transaction retries |
| [Conversation facts must exclude default-only API fields](conversation-supplied-facts.md) | Host loop, response capture and grounded record facts |
| [Later errors cannot erase an uncertain submission](conversation-action-uncertainty.md) | Exact decisions, attempt ownership, same-key retries and killed-chat recovery |
| [Qwen token counts depend on the pinned runtime template](conversation-qwen-runtime.md) | Explicit artifact identity, Go rendering, token admission and failed live evaluation |
| [A native completion function does not establish model reliability](conversation-typed-completion.md) | Completion isolation, 14-schema admission, repeated native calls and semantic failures |
| [Generated snippets need exact API shape and independent acceptance](snippet-generation-boundary.md) | Restricted Python, shared call budgets, retained generation failures and API shape checks |
| [Native Ollama wrapping can hide snippet generation](conversation-snippet-lifecycle.md) | HTTP lifespan capability loss, reproduced native-adapter scope and unaffected Qwen composition |

Keep one durable finding per file. Include date, evidence, limits, and when to
revisit it. Index new findings here. Record rejected approaches only when source
or an execution establishes why they failed; label untested ideas as hypotheses.
Remove stale conclusions or mark them superseded with a replacement reference.
