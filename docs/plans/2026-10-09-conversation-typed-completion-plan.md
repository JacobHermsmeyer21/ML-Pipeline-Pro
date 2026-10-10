# Native typed completion for conversation replies

- Status: implemented; real-model acceptance failed (3/10); A1 remains open
- Date: 2026-10-09
- Source baseline: `33ba46c`, `person-a/conversation-foundation`
- Request: continue Person A's approved A1 conversation work
- Human reviewer/approval: repository user; approved October 10, 2026
- Independent review: unavailable in this session; request review of protocol and admission arithmetic before closing A1

## Proposed behavior and purpose

Add a model-facing native `finish_conversation` function whose arguments are the
existing strict `ModelReply` schema. The adapter converts that one function call
to `ModelStep.reply`; the host validates citations, renders supplied facts and
finishes the turn through its existing path. This gives the model one native
function protocol for both reads/proposals and final explanations or missing-input
requests. It adds no HTTP operation or mutation permission.

This is a material update to the approved A1 model protocol. The October 7
approval did not explicitly approve a completion function. The
[retained October 9 failures](../evidence/2026-10-09-qwen-counter/results.json)
motivate this plan but do not establish that the proposed change works.

## Clarification and critique

Source resolves the execution boundary: the adapter currently exposes 13 domain
functions, parses native calls as `ToolCall`, and parses free-text final replies
as strict JSON. `ModelReply` already excludes model-supplied fact values and
private execution context. The host already distinguishes replies from proposals;
the completion function can translate into that interface without a persistence
change.

Observed replies appended prose to JSON, used invalid citation objects or omitted
proposals. Explicit JSON/schema prompts and a corrected native tool template
improved some scenarios; neither tested model passed all ten. The 7B profile also
misassigned a total tuning budget to the per-trial field. A completion function
may improve syntax, but it cannot prove intent, provenance or arithmetic.
The unchanged semantic acceptance checks remain necessary.

Simpler alternatives were tried: clearer prompts, explicit schema, one-call
template guidance and a larger model. Extracting a JSON substring or repairing
arguments would hide failures and is rejected. Switching runtimes or model
families would require a separately verified tokenizer/template profile. This
small protocol experiment reuses the installed artifacts and existing reply
contract; it remains a hypothesis until measured.

Human decision approved October 10: add this native completion channel and
proposal-specific descriptions under the constraints below. No other unresolved
intent choice is needed to implement this bounded experiment. If it still fails,
retain the result and plan another reviewed approach; do not expand scope or
declare A1 delivered.

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | One valid `finish_conversation` call becomes a typed reply, including guidance, refusals and missing inputs. | Real locked SDK with in-memory transport and host-loop regression. |
| F2 | Functional | Completion never reaches the domain dispatcher, grants permission, creates a proposal or makes a mutation HTTP request. | Dispatcher-spy and real API/store cases; existing confirmation tests pass. |
| F3 | Functional | Reject malformed/extra arguments, supplied fact values, invalid native arguments, mixed completion prose and multiple calls; retain strict legacy JSON replies. | Negative SDK-boundary cases and existing parser assertions. |
| F4 | Functional | Domain functions remain proposals; requested per-trial and total budgets keep their exact paths and values. | Existing ten-scenario history/tuning and missing-input assertions unchanged. |
| N1 | Resources | Count all 14 native schemas in host byte admission and exact SDK token admission; completion consumes a model call but no HTTP tool call. | Schema inventory, exact-payload count, budget and overflow regressions. |
| N2 | Compatibility | Preserve all public APIs, the 13-domain-tool catalog, project access, confirmation, replay and persisted schemas. | Existing fast, ordinary and serial recovery gates. |
| F5 | Acceptance | The selected real local model passes all ten original scenarios without retries, repair, assertion weakening or additional budgets. | Opt-in JSON/JUnit archive with source/model/runtime/token provenance. |

## Constraints and scope

Keep `ModelReply`, `ModelStep`, `/api/v1` schemas, stored turns/actions and all
trusted execution fields unchanged. No database migration, new route, automatic
download, model default, cloud fallback, worker/concurrency change or code
execution is in scope. Direct API/audit access and lazy offline startup retain
their current behavior. The existing local profiles remain explicitly selected;
tokenizer/runtime/template identity still fails closed.

A2 snippets, A3 diagnosis, A4 retrieval, Person B service/deployment work and
automatic natural-language budget extraction are excluded. Do not add host rules
that silently rewrite model-proposed budgets to pass the live gate.

## Design

In [conversation_model.py](../../src/ml_pipeline_pro/conversation_model.py), retain
`model_tools()` as the 13-domain-tool description contract. Add one shared helper
for actual native conversation bindings: clone those descriptions, explicitly
describe mutating functions as proposals requiring later human confirmation, and
append `finish_conversation` with `ModelReply.model_json_schema()`. The completion
schema contains no authorization field or verified value. Its defaults and strict
validation remain exactly those of `ModelReply`; do not introduce another reply
schema. The updated instructions prefer a native completion and distinguish it
from domain reads/proposals, while keeping the legacy strict JSON channel valid.

In [conversation_ollama.py](../../src/ml_pipeline_pro/conversation_ollama.py), bind
the shared 14-function list and hash that actual list in provenance. Intercept
exactly one `finish_conversation` call before constructing a `ToolCall`, require
empty free-text content for this completion branch, redact and strictly validate
its arguments, then return `ModelStep(reply=..., usage=...)`. Retain raw-response
duplicate-key/native argument validation and safe error handling. Invalid
completion content becomes `model_invalid_response`; no retry or repair follows.
Unknown domain calls and legacy replies retain their existing validation paths.

Use the same native list in
[host context admission](../../src/ml_pipeline_pro/conversation_service.py) and
[evaluation budget/count checks](../../evaluations/test_conversation_model.py).
Otherwise the host would omit the completion schema from its byte/count estimate.
The explicit Qwen counter already renders incoming native schemas dynamically;
do not change its pinned identities or pretend earlier 13-function prompt counts
are new-protocol measurements. Record new instruction/tool hashes and actual
runtime counts. A completion uses one inference reservation and the existing reply
path; it does not consume a domain read allowance.

Update deterministic SDK/host fixtures, the conversation guide and the A1 outcome.
Existing assertions that `model_tools()` equals the 13-domain-tool catalog remain
valid. Add separate assertions for the 14 native conversation bindings and their
absence from public dispatch. Test changes must follow these requirements, not
weaken current behavior. No new configuration or persistence version is needed.

## Acceptance and verification

Run focused model/adapter/host/grounding/counter/evaluation-harness tests after
each meaningful step. Negative cases must reach the actual SDK/native parser,
host dispatcher and admission preconditions. Test the added schema at the
64 KiB context limit and reserve output tokens at the existing 8192-token boundary;
retain both admitted and pre-dispatch rejected observations for the new payload.

Before the application commit, run all
[fast checks](../guides/verification.md#fast-checks), `uv build`, the full ordinary
integration gate with both `MLPP_RUN_INTEGRATION=1` and
`MLPP_RUN_WORKER_INTEGRATION=1`, and the isolated serial recovery gate with
`MLPP_RUN_RECOVERY_INTEGRATION=1`. Retain JUnit/native exits, current source/package
hashes, container identities and recovery evidence. No selected skips count as
passes. Request independent review of completion isolation and schema/token
arithmetic; record unavailable review as a gap.

Run the original opt-in gate once for an explicitly selected profile, initially
`mlpp-qwen2.5:7b-instruct-q4_K_M-json-tools-v1`, with
`evaluations.qwen_counter:create_counter`. Keep the existing ten scenarios,
50-call/409600-reserved-token/512-output-token limits and one 600-second suite
deadline, including preparation. No scenario reruns or retries within acceptance.
If a code fix warrants another full run, retain both failed and subsequent runs
with their different source hashes. All ten scenarios must pass; partial passes
remain failures. Generated guidance still requires human quality review.

Passing this protocol experiment alone does not close A1: independent review and
a successful complete clean-checkout tutorial remain required by the original
plan. No performance threshold or capacity claim is introduced here.

## Risks and rollback

An extra function adds context tokens and may cause premature completion instead
of reads or proposals. A native call can still invent budgets or unsupported
facts. Grounding, exact confirmation and all live semantic checks remain the
boundaries for those failures; report unresolved failures without changing gates.

Rollback the protocol commit and restart API instances; keep audit records,
proposals, jobs and artifacts. Saved public reply/turn schemas are unchanged,
and the strict legacy JSON path remains compatible. The explicit model profiles
and tokenizer need no modification. Mixed API versions may expose different
native lists during generation; recorded instruction/tool hashes identify them.

## Human review and approval

- Reviewer: repository user
- Decision/date/reference: approved October 10, 2026 in the conversation:
  "I approve the typed plan, start implementing"
- Approved scope: the native completion translation, proposal-only native
  descriptions, complete 14-schema admission/provenance and tests/evidence above.
  This approval does not extend to the excluded A2-A4 or Person B work.
- Independent reviewer/findings/resolutions: unavailable; pending before A1 closure

## Implementation outcome

### Original plan verification, October 9

Documentation verification passed for 33 Markdown documents and 326 local
links/anchors, two Python examples, 29 PowerShell examples and the 25-operation
API inventory. This plan adds no executable examples. Source review traced the
current native binding/parser, host admission and evaluation reservation paths;
application and live-model gates were not rerun for this documentation-only
change. Staged whitespace is checked before commit. Git and the completion
handoff record commit/push outcomes. Implementing-assistant review is self-review.

### Approved implementation, October 10

The user approved this protocol experiment on October 10 before application
edits. `native_conversation_tools()` now supplies the 13 existing domain schemas
with proposal-only mutation descriptions plus `finish_conversation`, using the
unchanged `ModelReply` schema. The adapter intercepts one completion with empty
free-text content and returns a typed reply. Strict legacy replies and raw
duplicate-key/native argument checks remain active. Host byte admission and the
live counter inventory include all 14 bindings; the public catalog, routes,
stored schemas, confirmation and recovery behavior are unchanged.

Twenty-six added fast cases and two added real-service cases check the new
requirements: strict completion translation and rejection at the locked SDK,
redaction, exact 512-output token reservation, host context overflow with the
added schema, dispatcher isolation, one-read tool allowance followed by
completion, evidence grounding, MongoDB persistence/replay and absence of saved
actions. The request inventory assertion changes from 13 to 14 for N1; the
public 13-tool assertion is unchanged. The added SDK metadata assertions check
its actual parameter projection, not equality with the fuller host schema.
No existing acceptance assertion, skip, scenario or budget was weakened.

The new real-runtime 14-function request admitted exactly 7,680 input tokens
plus 512 reserved output tokens at context 8,192. Input 7,681 was rejected before
HTTP inference; the admitted request reported exactly 7,680 runtime input tokens.
These are new-protocol admission observations, not reused 13-function counts.

The one original ten-scenario acceptance run used
`mlpp-qwen2.5:7b-instruct-q4_K_M-json-tools-v1`, unchanged 50-call/409600-token/
512-output/600-second limits and no retries or repairs. **Acceptance failed:
three scenarios passed and seven failed**, with native pytest exit 1. Five turns
failed with `model_invalid_response`; the comparison/history proposal substituted
the 40-second total budget for the requested 10-second per-trial runtime, and
the missing-limits turn borrowed prior values and proposed tuning instead of
asking for inputs. No mutation was dispatched. A separate read-only diagnostic
observed one read followed by 23 repeated native reads in one response, ending
with `done_reason=length`; it is diagnosis evidence, not an acceptance rerun.

All 446 fast cases, 58 ordinary integration cases and ten serial isolated recovery
cases passed with zero failures or selected skips. Host coverage is 77.29%; it
excludes container execution. Locked sync, Ruff lint/format, dependency compatibility and
offline source/wheel builds passed. Real-service checks use an isolated rebuilt
Compose stack and both required flags; recovery uses its separate opt-in flag.
Package inspection verifies all 37 canonical modules and excludes private,
cache and model paths. Documentation checks validate local links/anchors, two
Python examples, 29 PowerShell examples and all 25 documented API operations.

[The evidence manifest](../evidence/2026-10-10-typed-completion/results.json)
links a byte-preserving raw archive containing native exits, JSON/JUnit outputs,
the separate diagnostic, new runtime token observations, source/support/package
hashes, container identities and recovery snapshots/logs. Fast, ordinary, recovery
and live runs share the same retained application/test source hashes. Earlier
focused development failures are also retained. No weights, tokenizer data or
private environment files are archived; no remote CI or performance result is
claimed. Commit/push outcomes are recorded in Git and the completion handoff.

Review performed here is implementing-assistant self-review of completion
isolation, strict parsing, full-schema byte admission, exact SDK token admission
and unchanged permission/persistence paths. An independent reviewer was
unavailable; independent review, human model-quality review and complete
clean-checkout onboarding remain outstanding. F5 and semantic F4 acceptance,
A1 and course C3/C5 remain open. The approved experiment is implemented, but
it does not fix real-model reliability. Any next approach requires another
reviewed plan rather than accepting partial scenario passes.
