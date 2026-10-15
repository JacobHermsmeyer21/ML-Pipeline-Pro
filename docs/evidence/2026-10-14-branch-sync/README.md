# Branch reconciliation and current handoff

October 14, 2026. Starting branch: `person-a/conversation-foundation` at
`b39599d`, three commits behind its upstream, with six locally modified files.
Fetched `origin`, inspected both upstream and `origin/main`, and fast-forwarded
through `f13d5c3`, `3dd877b` and `377f64b`. `origin/main` at `f0ec2ad` is an
ancestor, with no additional incoming main commits; the integrated branch is
33 commits ahead of it before this reconciliation commit. Published history was
preserved without rebasing or force-pushing.

## Resolution decisions

Preserved the original local edits in a named Git stash and an ignored patch at
`artifacts/branch-sync-2026-10-14/local-before-sync.patch` before integration.
Reapplying them exposed four content conflicts:

| File | Resolution |
| --- | --- |
| `conversation_guidance.py` | Keep the published `requested_facts` implementation, matching actual host tool-message names and checking project, kind and record evidence. The alternate local implementation expected `tool_name` inside the result body. |
| `conversation_ollama.py` | Keep the published adapter, schema keyword and decoded-reference rejection. |
| `test_conversation_guidance.py` | Keep published SDK and host/replay coverage; retain local coverage for absent initial reads, latest lookup missing a metric, omitted/wrong-record references, no retry and unchanged native behavior. |
| `midterm_walkthrough.py` | Retain the local diagnostic with saved status/error/result path and the original assertion condition. |

Both local evaluation-observer edits are adapted to the published `required_facts`
schema keyword. An actual scripted SDK request established another mismatch:
the transmitted tool message contains only `role` and `content`, so recomputing
required references from it loses the tool name and rejects the correct schema.
Observers now obtain required references from original host context before SDK
projection, while still comparing the complete transmitted schema and counting
the actual request. Model scenarios, assertions, timeouts and budgets stay fixed.
No application module differs from `377f64b`.

The new evaluation regression exercises that exact SDK boundary and verifies
that deleting the required-reference constraint is rejected before token counting.
The expanded negative cases check omitted references and references to the wrong
record; their one-request assertion prevents a hidden retry. Existing tests are
retained. An initial new fixture mismatched its declared prompt count (42) with
its counter (100); the counter fixture now also reports 42, preserving the strict
runtime-count equality assertion.

## New verification

Using repository-local uv 0.12.23, Python 3.11.5 and workspace cache/temp paths:

| Check | Result |
| --- | --- |
| Locked sync with training extra | Pass, 109 installed packages checked |
| Ruff lint / formatting | Pass, 173 Python files formatted |
| Dependency compatibility | Pass, 109 installed packages compatible |
| Focused guidance/evaluation tests | 75 passed |
| Full non-integration suite with coverage | 598 passed, 73 integration cases deselected, 44.37 seconds; reported host coverage 80% |
| Both evaluation wrappers against actual scripted SDK requests | Pass; no live model invoked |

The [raw archive](raw.zip) retains full/focused JUnit, the full test log, final
check output and the scripted two-observer probe. [Results/provenance](results.json)
records source hashes. Documentation links/anchors, changed Python syntax,
conflict markers and whitespace are checked before commit.

Docker CLI is installed, but its Linux engine pipe is unavailable in this session,
including outside the sandbox. Ordinary integration, serial recovery, live-model
gates and the complete walkthrough were not rerun. The 73 deselected integration
cases are not passes. The latest published commit's [complete CI run](https://github.com/JacobHermsmeyer21/ML-Pipeline-Pro/actions/runs/38607154597)
was directly checked as successful; it predates this reconciliation. The new
commit's push and CI state are reported in the task handoff. No package/build,
dependency, persistence, ownership or production execution change is introduced.
Review here is implementing-assistant self-review; the original separate boundary
review remains outstanding.

## Where the project stands

The bounded classification backend, serial Bayesian tuning/history, separate
model/tuning/monitoring APIs, guided LangChain/Ollama conversations, validated
generated drafts, Prometheus/Grafana, Docker, Kubernetes and deployment CI exist.
The [October 13 delivery](../2026-10-13-midterm-delivery/README.md) retains acceptance
evidence for all nine minimal course requirements on its recorded environment.

That success does not establish a reliable presentation on the CPU laptop. Its
[latest full local-model gates](../2026-10-14-prerequisite-setup/README.md) pass
2/10 dialogue and 0/7 snippet cases. After reboot, [all 63 local ordinary service
cases and the backend/monitoring workload pass](../2026-10-14-post-reboot-validation/README.md),
but the AI walkthrough times out before its first tool read. Prompt evaluation
takes 113.524 seconds; the API returns 504 after 140.929 seconds despite configured
20-second model and 60-second turn deadlines. Slow inference is measured; the
timeout-overrun mechanism is unresolved. The requested-fact correction still
needs successful real-model walkthrough acceptance and separate boundary review.

The next priority is to diagnose the blocking timeout boundary and establish a
passing presentation setup with the existing acceptance limits. Any execution or
concurrency redesign needs its own reviewed plan. Shared-production security,
immutable data/retention/backup/restore, concurrent-load/partition evidence and
larger research measurements remain deferred rather than delivered.
