# Person A: reviewed Python snippet generation (A2)

- Status: approved October 10, 2026; implementation in progress
- Date: 2026-10-08
- Source baseline: `2b9dfaf` / `person-a/conversation-foundation`, plus the A1 action/routes slice
- Request: complete the remaining Person A work
- Human reviewer/approval: repository user, October 10, 2026: "I aprove the plan, start on A2"
- Independent review: Person B/human review requested; none performed

## Proposed behavior and purpose

An engineer asks in a conversation for a Python integration example. LangChain
and the selected local model generate the code; the host validates it and returns
a draft explicitly requiring human review. The supported first profiles cover
listing/comparing recorded experiments and submitting bounded training/tuning
through the existing REST API. This supplies course C7 without executing code.

## Clarification and critique

Source fixes the existing API contracts, budgets, project headers and submission
keys. Use these instead of inventing SDK methods or creating another training
engine. Static templates alone do not meet C7; templates may supply constraints
and examples to the model. General arbitrary Python validation cannot establish
safety. Restrict the accepted grammar and reject unsupported constructs rather
than present a syntax check as an execution guarantee.

Proposed intent decisions for review: support only the four profiles above;
return drafts within saved conversation history; require explicit runtime,
objective and trial/overall budgets for submission snippets; do not enable
execution or add notebooks, uploads, deployment code or automatic repair retries.
Any broader profile needs a revised plan. Model artifact/counter selection remains
the open A1 prerequisite; A2's live acceptance cannot close before it.

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | Natural-language input produces local-model-generated Python via LangChain. | Retained real-model draft for each supported profile; prompt/model provenance. |
| F2 | Functional | Missing submission inputs request clarification; no invented budgets or mutation. | Missing dataset/model/runtime/objective/limits tests and zero HTTP mutations. |
| F3 | Functional | Accepted drafts use only the supported API and require human review. | AST/API rejection cases and accepted examples; no executor or mutation dispatch. |
| F4 | Functional | Drafts and validation outcomes are project-scoped and inspectable after replay. | Saved turn/restart/foreign-project cases with original generation provenance. |
| N1 | Reliability | Generation is bounded, redacted and independent of ordinary CI/model availability. | Exact payload/token/deadline, secret, cleanup and disabled/unavailable-model cases. |

## Constraints and scope

Preserve A1's authentication, trusted origins, request replay, ownership fencing,
record cap and validation-only selection. A generated snippet is untrusted text,
never an approved action. Existing exact-action decisions remain unchanged.
Use environment placeholders for origin/project/key and a caller-supplied stable
submission key; include no literal credentials, arbitrary destinations, raw
datasets, artifacts or private persistence. No execution, installation or downloads.

## Design

Add `snippet_schemas.py`, `snippet_generation.py` and `snippet_validation.py`.
Add one model-visible `generate_pipeline_snippet` request to the conversation
catalog with a typed profile and required inputs; host handling bypasses the
domain dispatcher. Extend the typed model step/turn output additively with a
draft containing `code`, `profile`, `review_required=true`, validation issues
and redacted provenance. Generation output is either a validated draft or an
explicit rejected result; rejection is saved, never executed or silently repaired.

Use an injected generation interface backed by the same locked local ChatOllama
stack, exact artifact/counter and credential-isolated clients. Admit at most one
code-generation call in the existing turn's model-call/token/time budgets; count
it against that turn, not a fresh deadline. The draft cap is 8 KiB UTF-8 within
the existing full-record limit. Include actual model digest/runtime, instructions
hash and supplied safe input hash; generation timings/tokens are observed values.

Validate with `ast.parse` and a restricted AST grammar. Permit only reviewed
`os`, `json` and `httpx` imports and straight-line variable assignment, environment
lookup, bounded response inspection and client calls with literal supported
method/path patterns. Forbid dynamic imports, eval/exec, shell/file access,
definitions/classes, arbitrary loops and dynamic attribute/call targets. Check
request bodies against existing Pydantic contracts and project/idempotency header
requirements. API shape fixtures and AST cases define the supported subset;
even accepted drafts require a human to review them before use.

Update native schemas, conversation persistence fixtures, README/example docs
and deterministic/live evaluation cases together. Preserve old saved turns
through optional additive fields; read schema-v1 records without inventing
generated-code evidence. No automatic database migration/deletion is needed.

## Acceptance and verification

Run the full AGENTS fast gate, package build and affected ordinary/isolated
recovery gates. Use scripted generation in normal CI; reach the validator with
otherwise valid profile/input fixtures. Test unsupported imports/API calls,
hard-coded secrets, invented budgets, oversized/malformed output, storage failure,
replay and foreign projects. Keep existing assertions/gates unchanged.

Extend the opt-in A1 local-model gate after its artifact/counter works: one draft
per profile plus missing-input, hostile-record and unsupported-profile scenarios;
at most seven generation calls, 1024 output tokens each and a 120-second total
deadline. A budget failure remains a failure/gap. Retain syntax/API results,
safe drafts, source/config/model identity and raw run evidence; no wording or
speed threshold and no automatic code execution. Human validates usefulness.

## Risks and rollback

The restricted grammar may reject useful code. Expand it only with reviewed
examples and rejection tests; do not loosen it to satisfy one model output.
Disable generation through the existing chat setting or revert new catalog
support. Retain saved drafts/provenance; old binaries ignore additive fields.
This feature does not establish arbitrary Python safety or isolation.

## Human review and approval

The repository user approved this concrete A2 plan on October 10, 2026 and
requested implementation. Approval covers its four profiles, additive saved
drafts, restricted validation, shared turn budgets and deterministic/live
acceptance evidence. It does not approve A3/A4, arbitrary code execution, or
changes to A1's original model-quality gate. Independent review remains pending.

## Implementation outcome

Implementation started on source baseline `9ed94f0`, following the recorded
approval. A1 now has an installed artifact and verified counter, while its
conversation-quality acceptance remains failed. A2 retains its own real-model
snippet acceptance; no C7 closure, execution result or independent review is
claimed by starting implementation.
