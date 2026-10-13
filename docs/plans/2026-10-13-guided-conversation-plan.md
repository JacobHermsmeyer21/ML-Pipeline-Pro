# Guided single-step local-model responses

- Status: approved midterm direction; implementation pending
- Date: 2026-10-13
- Source baseline: `2a6d56b` / `person-a/conversation-foundation`
- Request/approval: Jacob's October 13 approval of all scope-review recommendations and request to implement; [scope record](2026-10-13-midterm-delivery-plan.md#human-review-and-approval)
- Independent review: separate boundary review required after implementation; different-vendor availability unknown

## Proposed behavior and purpose

Offer an opt-in guided protocol for the existing inspection/training/tuning and
Python-draft workflows on one pinned Qwen profile. Each inference returns one
schema-constrained JSON step: a supported tool proposal/read or a final reply.
The host continues to own reads, validation, missing-input handling, grounding,
confirmation, call/time admission and durable replay. Eliminate model-native
multiple calls inside one response without relaxing their rejection in native mode.

## Clarification and critique

The fresh original gate passes 6/10 and still fails clarification, borrowing old
limits and hostile-record formatting. A larger model is not an established fix.
Schema constraints address response shape, not correct numbers/facts; original
semantic gates remain required. Current request and explicit missing inputs take
priority. Present prior conversation as historical data with recorded reads rather
than replay old user instructions/budgets into the current request.

Keep native mode as the default for compatibility. Guided mode is an explicit
demo selection, uses the existing verified tokenizer/artifact/runtime and has no
hidden retries, output repairs or new mutation permissions. Existing API schemas,
public tool catalog, stored turns, worker ownership and limits remain unchanged.

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | One closed JSON envelope with exactly one call or reply; drafts use their existing candidate shape. | Real SDK payload/grammar and strict malformed/both/unsupported output tests. |
| F2 | Functional | Current explicit inputs override historical instructions; real history remains available as evidence. | Original missing-input/budget/history/hostile-record scenarios unchanged. |
| F3 | Functional | Generate all four real Python profiles with existing validator/review behavior. | Full unchanged seven-case A2 live gate and configured HTTP workflow. |
| N1 | Reliability | Full schema/message byte admission, exact prompt count and output reservation remain bounded. | Format-field size/token limits and actual runtime usage match the selected counter. |

## Constraints and scope

No automatic execution, text/JSON extraction repairs, inferred missing budgets,
test relaxations, broad runtime support or new action routes. Keep native parser
rejections, SDK credential isolation, pinned token verification, project access,
grounding, exact confirmation and original turn deadlines. Current APIs/storage
and native default are preserved. Guided operation supports the existing bounded
classification tools and drafts; unsupported operations receive a refusal.

## Design

Add `MLPP_CHAT_PROTOCOL=native|guided`, default `native`, documented in `.env.example`.
Guided mode uses LangChain's Ollama `format` JSON-schema parameter with no native
tool bindings. Its closed envelope contains either `call` (name and arguments)
or `reply` (existing ModelReply); reject both/none/extra fields and unsupported names.
Supply typed tool guidance in the bounded prompt; host validates arguments against
the existing schemas, without rewriting them. Generated code uses SnippetCandidate's
schema and remains raw until the existing restricted validator decides acceptance.

Include the transmitted format schema in byte admission. The selected Qwen counter
still counts the actual SDK messages/template, reserving all output tokens;
verify schema-constrained runtime counts rather than assume equivalence. Public
provenance records the actual instruction/tool schema identity for the protocol.
For guided context, historical turns retain their status/read evidence/interpretation
as marked data; the newest user message remains the active request. Replay is still
returned before any inference. Retain native context behavior in native mode.

## Acceptance and verification

Run unchanged native adapter/host tests, new actual-SDK guided envelope/admission
cases, all fast gates and affected real-store HTTP replay tests. Run the original
ten-case conversation gate and seven-case snippet gate separately, one retained
run per evaluated revision/profile with fixed scenarios/budgets and no retries.
Retain every failure and actual SDK/runtime counts/source identity. Review the
envelope, byte/token arithmetic, history priority and failure boundaries separately.
Successful grammar alone does not close C3/C5/C7; human quality/usefulness and
clean-checkout evidence remain required.

## Risks and rollback

Ollama's grammar may reject schema constructs or the model may still produce wrong
arguments/facts. Fail closed and report the original gate failure. Revert to native
configuration without deleting stored history/actions/drafts. Schema changes alter
admission and require new runtime evidence. Different-vendor review may remain a gap.

## Human review and approval

Jacob approved the scope review's guided-workflow and schema-constrained response
recommendations and requested implementation on October 13. This records the
implementation detail within that direction, not a claim of separate human review
of this document. Preserve the original acceptance criteria and native defaults;
material deviations require renewed review.

## Implementation outcome

Pending. Baseline failure retained in the midterm service evidence; no AI row closed.
