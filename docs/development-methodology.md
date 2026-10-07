# Development methodology

This repository adopts the working method requested by the user on October 6,
2026. Its source is Jacob Hermsmeyer, Christine Hwang, and Oscar Jaroker,
*AI-Assisted Software Engineering in a Research Project: A Working Method*,
July 31, 2026, supplied as `ai_paper.pdf`. The supplied PDF has SHA-256
`ae7bfdb05accf66e37347fc3d5d887b990cca2cf11a1f5339d2d3efb22cf2ba0`.

The adaptation below follows sections 3.3-3.4 (standing instructions and memory),
4 (the working loop), 5 (verification and review), and appendices A-B (checklist
and worked example). The paper's prompts and file-transfer commands describe
its original project; use this repository's contracts and commands here.

## The five-stage loop

1. **State the idea.** Identify the user problem and the smallest checkable change.
   Read the relevant source, [status](project-status.md), [roadmap](../PLAN.md),
   [course requirements](course-requirements.md), and [memory](memory/README.md)
   before proposing mechanisms. Map the idea and acceptance evidence to the
   supplied requirements; keep the course deliverable separate from later
   shared-production hardening.
2. **Clarify and challenge.** Surface every unresolved requirement: intended users,
   inputs, defaults, compatibility, failure behavior, access, resource limits, and
   success criteria. Answer source questions through inspection; ask the user about
   intent that source cannot establish. Present the case against the idea, existing
   mechanisms that might suffice, and simpler alternatives. Record decisions,
   rejected alternatives, and remaining questions. Narrow or abandon the idea when
   evidence warrants it.
3. **Write and commit a plan.** Use
   `docs/plans/YYYY-MM-DD-short-name-plan.md` and [the template](plans/template.md).
   State the proposed behavior in prose before its mechanism. Separate functional
   requirements from performance, reliability, and resource requirements. Specify
   interfaces, states, defaults, failure paths, constraints, acceptance evidence,
   and rollback. Commit and push the plan for review under the repository workflow.
4. **Obtain human review.** The user reviews whether these are the right
   requirements and whether the acceptance criteria prove the intended outcome.
   Revise the plan and record explicit approval, reviewer, date, and approved scope.
   A plausible plan or passing tests do not substitute for that review. Keep
   implementation pending until approval; work on investigation and reviewable
   artifacts can continue. The milestone roadmap does not approve individual designs.
5. **Implement and verify continuously.** Work in small steps and run the relevant
   tests while changing code. Keep the specified success criteria fixed; update and
   review the plan if requirements or design materially change. Review the final
   diff for concurrency, failure paths, resource cleanup, and changed tests. Record
   evidence, update durable findings, then commit and push the completed change.

Plans should normally fit in one to three pages. Maintain a status such as
`draft`, `awaiting review`, `approved`, `implemented`, `rejected`, or `superseded`.
Keep the original acceptance criteria and link outcome evidence rather than
rewriting them retrospectively to match the implementation.

## Scale the process to the work

| Activity | Required treatment |
| --- | --- |
| Feature or substantive design change | Full five-stage loop, with human plan review before implementation |
| Contract, default, ownership, or concurrency change | Full loop even when the diff is small |
| Local edit, documentation, mechanical refactor | State scope, implement, inspect diff, run relevant checks; a separate plan is usually unnecessary |
| Debugging | Enumerate hypotheses, establish the failure mechanism with evidence, then fix and verify the original precondition; use a plan if the fix changes design/contracts |
| Experiment or benchmark | Treat harnesses as software; define workload, baseline, budgets, and acceptance criteria before runs; retain raw evidence |
| Explanation or writing | Check structural explanations against source and every factual claim against a source or recorded execution |

Workflow adoption is a documentation change under the compressed loop. Future
feature work uses the full loop according to its scope.

## Verification and review

[AGENTS.md](../AGENTS.md#verification-commands) contains the shared commands and
pre-commit rules. The fast application gate covers Ruff lint/format, the local
unit/API/training/tuning suite, and installed dependency compatibility. Packaging
changes additionally require a successful build. Warnings require inspection;
record pre-existing warnings and distinguish them from newly introduced ones.

Use [ordinary integration checks](../README.md#run-checks) for real MongoDB/Redis,
API, and queued-worker behavior. Ownership changes need the transaction-boundary
regressions in [test_tuning_ownership.py](../tests/integration/test_tuning_ownership.py).
Worker/recovery changes need the [isolated recovery gate](recovery.md).
Unit fakes alone cannot establish transaction or process-loss correctness.

Select checks from the requirements before implementing. A skipped selected case,
missing service, or failed command is a verification gap and must be reported.
Inspect assertions to confirm the test reaches the intended behavior: an error
for an unrelated reason can make a negative test pass. Changes to tests need an
explicit explanation of the requirement and why the old assertion was wrong or
insufficient; do not relax tests to accommodate a defect.

For concurrency, state machines, and rate/size arithmetic, seek a separate
reviewer, preferably a different vendor's model, after the affected checks pass.
Record what was submitted, reviewer/tool identity, findings, fixes, and unresolved
issues in the plan or review record. If independent review is unavailable, disclose
the gap for human review; a second reading by the implementing assistant is
self-review. Tool availability does not establish that a review occurred.

Verification establishes that the implementation satisfies the plan. Human
validation establishes that the plan and outcome satisfy the user's actual goal.
Both belong in the record.

## Evidence and durable memory

Keep one evidence-linked finding per file under `docs/memory/`, with a short
[index](memory/README.md). Useful entries include confirmed failure mechanisms,
fixed environmental constraints, and measured approaches that did not help.
Distinguish an untested hypothesis from a verified finding. Include the date,
source or run reference, limits, and conditions that would justify revisiting it.
Update an entry when its supporting contract or environment changes.

Use plan outcome records to capture source revision, commands, environment and
dependency/model identifiers when known, test counts/skips/warnings, evidence
locations, reviewer findings, and the final commit/push result. Record unknown
tool metadata as unknown rather than guessing. Avoid archiving incidental secrets
or full conversations; preserve decisions and review evidence needed for handoff.

Measurements come only from recorded executions. Save raw results with revision,
dataset/configuration hashes, seeds, workload, hardware, versions, and timing/budget
conditions. Ignored `artifacts/` paths are local evidence locations; archive needed
results in CI or another retained location and reference them from the tracked
record. Generated prose is a description to check against that evidence.

Use repeated comparable runs for performance claims and retain failures, spread,
and costs. Follow [the measurement plan](../PLAN.md#measurement-and-reporting).
The paper reports no measured productivity multiplier, and adopting its method
does not establish a performance or productivity improvement in this repository.

## Completion record

Before calling a change complete, confirm that its reviewed scope and acceptance
criteria are met, the required checks passed, test changes were justified, defects
were attributed to a confirmed mechanism, review gaps were disclosed, and reported
facts trace to evidence. Update relevant plans, documentation, and memory. Commit
and push every major completed change; report whether the push reached `origin`.
