# Person A: grounded monitoring diagnosis (A3)

- Status: awaiting review; joint contract pending with Person B
- Date: 2026-10-08
- Source baseline: `2b9dfaf` / `person-a/conversation-foundation`, plus the A1 action/routes slice
- Request: complete the remaining Person A work
- Human reviewer/approval: pending for this design and B2's evidence contract
- Independent review: Person B/human review requested; none performed

## Proposed behavior and purpose

An engineer asks why a monitored workload raised an alert. Person A reads a
bounded metric/log window from Person B's monitoring REST service, then the local
LangChain model summarizes observed facts and proposes evidence-linked checks
and possible fixes. The response separates observations from uncertain causal
interpretation. B2 owns collection, dashboards and measured update/alert timing.

## Clarification and critique

There is no monitoring service or evidence schema in this checkout. B owns those
contracts; an A-only fabricated endpoint cannot establish a service integration.
Agree on the following proposed schema/limits before either side implements it.
Metrics and logs alone seldom establish cause. A deterministic metric table is
simpler and remains available if the model fails; the model adds interpretation
only when citations resolve to supplied current-window evidence.

Review must settle B's route name, observed metric names, window availability,
label semantics, retention, refresh/alert interval, log redaction and fixture.
Proposed A behavior: ask for an alert/window identity, report missing/stale/failed
evidence explicitly, make one bounded evidence read and no automatic remediation.
Do not silently choose a different window or infer current quality without labels.

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | Only current project-scoped window records establish observations. | Valid foreign-project rejection; missing/stale/failed evidence cases. |
| F2 | Functional | Local-model diagnosis cites actual supplied observations and separates causes as hypotheses. | Seeded B2 issue produces a cited summary/checks; fabricated IDs/values reject. |
| F3 | Functional | Proposed fixes never execute or alter worker/model limits. | Hostile log and remediation prompts dispatch zero mutations. |
| N1 | Reliability | Bounded/redacted inference preserves evidence and safe failure behavior. | Byte/token/time, unavailable-model, audit/replay and redaction boundaries. |

## Constraints and scope

Preserve project headers, configured trusted routing, correlations, A1 ownership,
record replay and validation-only model selection. No log paths/URLs selected by
the model, source file access, automatic restart, scaling, configuration changes
or performance guarantees. C6 closes only with B2's measured producer/dashboard
timing and a real local-model summary from its seeded issue.

## Design

Proposed B-owned read response: `schema_version`, `project_id`, immutable
`window_id`, `alert_id`, `observed_at`, `window_start`, `window_end`,
`producer_status`, explicit label availability, and bounded observation/log
reference arrays. Each observation has a stable identity, metric, unit, timestamp
and supplied value. Logs expose only safe event identity/time/severity/text;
avoid embedded secrets, arbitrary paths or raw request bodies. B supplies fixture
and staleness/refresh rules in its reviewed B2 plan. Route/origin is configured by
the host, never supplied as an inference URL.

After joint approval, add typed read schemas and a model-facing adapter under A
ownership, plus `monitoring_diagnosis.py`. Admit one monitoring read under A1's
existing tool-call/deadline budget and 128 KiB tool-response limit. Select safe
observations for the existing 64 KiB/context-token limit and reject unfit windows
explicitly rather than shorten evidence without disclosure. Generation uses the
existing local-model adapter/counter and remaining turn budget.

Model output supplies observation IDs/field references; the host renders actual
values, analogous to A1's supplied-fact ledger. Checks/fixes carry citations and
are labeled proposals. Store safe snapshots and model/window provenance in the
turn with additive optional fields. Missing evidence produces clarification or
a recorded unavailable result; it is never rewritten as a measured zero.
Model failure retains inspectable observation facts without invented diagnosis.

## Acceptance and verification

Use B-approved fixtures for deterministic tests: seeded resource issue, absent
labels, stale/incomplete window, safe logs, malicious instructions, fabricated
citations and values, foreign projects, oversized responses and failed reads.
Run full fast/build gates and affected real-service/recovery checks.

Once B2 is running, retain its source/producer/window/alert identifiers and
measured dashboard timestamps. Run three explicit local-model cases (seeded
issue, missing labels and hostile log), at most 15 model calls total and four
read calls per case under existing per-turn limits and a 240-second suite deadline. Reserve
output budgets; no hidden retries. Preserve raw evidence and distinguish actual
measurements from generated explanations. Human reviews factual grounding and
usefulness; B establishes timing, not A's fixture or a YAML dashboard alone.

## Risks and rollback

Schema disagreements or absent B2 block real acceptance, not fixture development
after contract approval. False causal certainty is a rejection case. Disable the
diagnosis tool/revert additive model output while retaining observations and
history. Preserve direct domain APIs and B's observation producer.

## Human review and approval

Pending. Person B must review the evidence proposal alongside B2; the repository
user must approve behavior, bounds and acceptance before implementation. This
plan does not approve service extraction, monitoring instrumentation or deployment.

## Implementation outcome

Not implemented; B2's service/fixture and A1's real model remain dependencies.
No C6 closure or independent review is claimed.
