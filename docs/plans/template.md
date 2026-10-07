# <Change name>

Copy to `docs/plans/YYYY-MM-DD-short-name-plan.md`. Replace placeholders before
review. Keep the plan concise and record acceptance criteria before implementation.

- Status: draft
- Date: <YYYY-MM-DD>
- Source baseline: <commit/branch>
- Request: <user goal or issue reference>
- Human reviewer/approval: pending
- Independent review: <planned reviewer, or availability unknown>

## Proposed behavior and purpose

<Explain the smallest intended change and the user outcome in prose.>

## Clarification and critique

<List every unresolved ambiguity and the decisions that resolve it. Identify
questions requiring human intent separately from facts established from source.>

<Present the case against the idea, existing mechanisms, simpler alternatives,
and why the chosen approach survives those objections.>

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | <observable behavior> | <test or scenario> |
| N1 | Non-functional | <reliability/resource/performance condition> | <measurement or failure exercise> |

## Constraints and scope

<State interfaces, project access, idempotency, data-selection, ownership,
artifact, and recovery invariants affected by this work. Identify behavior that
must remain stable and excluded work.>

## Design

<Specify modules, schemas, states/transitions, defaults, configuration names,
failure behavior, compatibility, migrations, and cleanup as applicable. Link
source. Identify coupled updates to docs, fixtures, and configuration.>

## Acceptance and verification

<Map each requirement to observable evidence. Name exact commands and any
service/flag setup. Define workload, baseline, budget, and success thresholds
before performance runs. Ensure negative tests reach the intended precondition.>

<Include fast gates and affected real-service/recovery checks. Identify targeted
diff review and independent review needs. Explain expected coverage limits.>

## Risks and rollback

<Describe boundary cases, risks, rollback procedure, and how rollback affects
stored records/artifact references and mixed versions.>

## Human review and approval

<Record reviewer, date, decision, approval reference, approved scope, and requested
revisions. Leave approval pending until explicitly given. Record renewed review
for material deviations.>

## Implementation outcome

Fill this section after implementation without weakening the criteria above.

- Source revision and changed scope: <reference>
- Commands, environment, dependency/tool/model identifiers: <known values or unknown>
- Results: <passes, failures, skips, warnings, and acceptance mapping>
- Raw evidence and retained location: <paths/CI links with provenance>
- Test changes and justification: <requirement-based explanation or none>
- Review: <reviewer, submitted scope, findings, resolutions, remaining gaps>
- Deviations and human review: <references or none>
- Durable findings: <memory links or none>
- Completion commit and push: <commit and remote outcome>
