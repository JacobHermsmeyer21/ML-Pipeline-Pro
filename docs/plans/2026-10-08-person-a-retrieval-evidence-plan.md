# Person A: MongoDB retrieval evidence and AI onboarding (A4)

- Status: awaiting review; execution pending
- Date: 2026-10-08
- Source baseline: `2b9dfaf` / `person-a/conversation-foundation`, plus the A1 action/routes slice
- Request: complete the remaining Person A work
- Human reviewer/approval: pending for workload, budgets and evidence
- Independent review: Person B/human review requested; none performed

## Proposed behavior and purpose

Demonstrate retrieval of saved parameters, versions, tuning configurations and
metrics through the supported project-scoped REST routes. Retain MongoDB query
plans and measured latency from a defined synthetic workload. Write the history/
advanced optimization tutorial and verify the AI part of the final clean-checkout
demo with Person B. This supplies C4/C9 evidence without promising a speedup.

## Clarification and critique

Current repositories expose the required records/indexes; B1 will preserve the
public routes while extracting services. A standalone evidence harness avoids
changing repository/index ownership. Synthetic records prove retrieval and query
behavior; their metrics do not establish actual model quality. Small-fixture
unit tests alone do not establish representative query performance.

Proposed representative course scales: 1,000 and 10,000 experiments, ten model
definitions, 100/1,000 versions and 100/1,000 tuning jobs with ten trials each,
plus an equally sized foreign-project dataset. These are test workload choices,
not claims about production traffic. Review scales and target hardware before
runs. Run against a disposable database/API with no worker or queued tasks;
final routed-service evidence waits for B1's stable deployment.

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | Retrieve exact saved records and pagination in the correct project. | Expected IDs/fields/order match seeded manifests; foreign reads reject. |
| F2 | Functional | Record reproducible query plans and measured response latency. | Raw samples, explain output, source/config/seed/hardware and indexes retained. |
| F3 | Functional | Tutorial exercises actual history-guided workflows and AI features. | Clean-checkout run against completed A1-A3/B services with evidence links. |
| N1 | Reliability | Harness bounds runtime/resources and touches only its test data. | Unique database/project guard, timeout/failure record and safe cleanup tests. |

## Constraints and scope

No domain repository, index, worker, selection or recovery changes. Seed records
with canonical schemas in the isolated harness; no HTTP training submissions,
private production records, holdout-based optimization or concurrent training.
Access/record correctness is pass/fail; latency is an observation with no required
speed multiplier. Keep missing features and failed/aborted runs visible.

## Design

Add `benchmarks/retrieval_evidence.py` and deterministic harness-boundary tests.
The harness creates a unique database with prefix `mlpp_retrieval_` and launches
an API configured only for that database. Refuse an existing/non-prefixed
database. Create documented indexes through existing stores, seed with RNG seed
42 and fixed timestamp ordering, and write a manifest containing all fixture IDs
and input hashes. Synthetic quality values are labeled fixtures, never measured
training. Do not change shared service databases or publish queue messages.

Six query families: get experiment, filtered experiment page, model versions
page, get version, get tuning job and tuning-trials page. Use 50-item pages;
verify returned fields, identity, scope and ordering on every response. Include
parameters/configuration, metrics and version/artifact metadata without reading
artifact contents. Explain the matching repository queries with execution stats;
preserve index names and examined/returned counts, including any collection scan.
No optimizer changes or hindsight rewriting of the benchmark workload.

At each scale/family run ten warmup requests followed by 50 measured serial
requests. Record individual elapsed times with a monotonic clock and report
median and nearest-rank p95. One request timeout is two seconds; total measured
request cap is 600, total including warmup cap 720, and total harness deadline
180 seconds including setup. Reserve the next request's time allowance before
admission; timeout or exhausted budget fails the run without shrinking the
workload. Record OS/Python/MongoDB/package/image versions, CPU/memory identifiers,
cache state as warmed for measured reads, seeds/query/fixture hashes and all raw
samples. No forced cache clearing on shared infrastructure or baseline speed claim.

Tutorials extend existing workflows with registered inputs, validation-only
selection, inspecting prior trials and user-confirmed bounded suggestions.
AI onboarding includes model digest/counter setup, guided missing-input handling,
action confirmation, monitoring diagnosis and a reviewed generated snippet.
Person A executes B4's final combined tutorial from a clean checkout and records
actual output; missing B services/models remain open rather than replaced by mocks.

## Acceptance and verification

Review the workload before running it. Unit-test database guard, sample arithmetic,
timeouts/admission and manifest verification; use real-service tests for seeding,
record retrieval and cleanup. Run full fast/build gates and affected ordinary/
recovery gates. Seek independent review of rate/size arithmetic. Retain failed
samples, raw plans, JUnit and source/run identities in tracked evidence or CI.

Close retrieval correctness only if every family matches expected records at both
scales and project isolation passes. Preserve all query-plan/latency results;
do not claim a speedup without a separately reviewed comparable baseline. C9
waits for the full successful clean-checkout course workflow, not authored prose.

## Risks and rollback

Target hardware or storage may not fit the proposed workload/budget. Report an
aborted run and review changes before another run; do not lower scales silently.
Synthetic distributions limit representativeness. Stop only the harness's own
API and delete only its guarded disposable database; retain evidence. Revert the
harness/docs independently of domain-service code and keep application data intact.

## Human review and approval

Pending. Review scales, six query families, serial sampling, budgets, isolation,
reported statistics and onboarding completion evidence. Person B reviews stable
routing and schema/index reuse. No benchmark execution is authorized by this plan
until the human approves its defined workload under the development method.

## Implementation outcome

No harness/run or clean-checkout result yet. C4's current initial backend coverage
and C9's partial documentation remain as recorded in the course checklist.
