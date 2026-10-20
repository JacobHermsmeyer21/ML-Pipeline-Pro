# Restore MongoDB startup on hosted CI runners

- Status: awaiting review; implementation pending
- Date: 2026-10-19 (America/New_York)
- Source baseline: `96c652c` / `main`
- Request: repair the GitHub Actions `compose-smoke` startup failure
- Human reviewer/approval: Jacob; pending for the specific design below
- Independent review: not required for this runner configuration change; no concurrency,
  ownership, state-machine, or rate/size arithmetic changes

## Proposed behavior and purpose

Run the three CI jobs that start MongoDB on `ubuntu-22.04`, whose currently
published runner image uses Linux 6.8. Keep the Python-only `checks` matrix on
`ubuntu-latest`. Record `uname -r` in each MongoDB-dependent job before startup.
This restores the existing service and test gates on a compatible host kernel.

## Clarification and critique

The [retained failure](../evidence/2026-10-19-ci-mongodb-kernel/README.md) establishes
that MongoDB exits with its kernel incompatibility diagnostic before readiness,
ordinary integration, or recovery tests run. The failing job used Ubuntu 24.04
image `20261018.339.1`; a passing domain job in the same run used the preceding
`20261012.334.1` image. The image rollout explains why the shared configuration
can pass in another job. No application-test failure is established by that exit.

The [published Ubuntu 22.04 runner](https://github.com/actions/runner-images/blob/ubuntu22/20261012.322/images/ubuntu/Ubuntu2204-Readme.md)
uses kernel `6.8.0-1064-azure`. Pinning only `ubuntu-24.04` would retain the failing
kernel series. MongoDB's [Ubuntu version-detection issue](https://jira.mongodb.org/browse/SERVER-136848)
affects 8.0.32; upgrading a floating image without demonstrated compatibility is
insufficient. Downgrading MongoDB would introduce a database-version change when
the current 8.0 deployment and data already work on compatible kernels. Disabling
the compatibility check, spoofing the kernel, or relaxing health/tests would hide
the precondition rather than fix it.

The runner pin is temporary: Ubuntu 22.04 is already on GitHub's announced
[deprecation path](https://github.com/actions/runner-images/issues/14254).
Revisit before its April 2027 retirement, or once a supported
MongoDB/kernel combination passes all existing gates. No unresolved product intent
is needed beyond human review of this CI host choice.

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | Start the existing MongoDB replica set on a compatible hosted kernel. | Fresh Actions logs show the pinned runner, actual kernel, healthy startup and successful readiness. |
| F2 | Functional | Preserve ordinary, worker, recovery, domain and Kubernetes validation. | All five CI jobs succeed; ordinary/recovery JUnit reports contain no failures or selected-case skips. |
| N1 | Reliability | Apply the host fix to every job that starts MongoDB. | Workflow review covers `compose-smoke`, `domain-compose-smoke` and `kubernetes-deploy`. |
| N2 | Compatibility | Keep existing database images, application behavior, health assertions and test gates. | Diff review confirms only runner selection, kernel diagnostics and supporting documentation change. |

## Constraints and scope

This addresses course requirement C8's exercised CI/deployment path. Public API
contracts, MongoDB persistence/transactions, ownership, idempotency, training
selection, artifacts, serial worker execution and all opt-in service flags retain
their existing behavior. No local containers, volumes or saved demo records need
modification. The application and Compose/Kubernetes MongoDB image remain unchanged.

## Design

In [the workflow](../../.github/workflows/ci.yml), set `runs-on: ubuntu-22.04` for
`compose-smoke`, `domain-compose-smoke` and `kubernetes-deploy`. Add a short comment
linking the MongoDB issue, and a named `uname -r` step in each affected job. Preserve
checkout credential isolation, dependency locks, permissions, commands, deadlines,
failure diagnostics, artifact uploads and cleanup. Document the temporary CI host
constraint in [the verification guide](../guides/verification.md) and keep the
[durable finding](../memory/ci-mongodb-kernel.md) linked to retained evidence.

## Acceptance and verification

Before implementation, validate this plan's local links, factual sources and
`git diff --check`, then commit/push it for review. Record explicit approval below
before changing the workflow.

After approval, validate workflow YAML and review the exact job/step changes. Run
the repository fast gate with `.tools/uv/bin/uv.exe` version 0.12.23:
`uv sync --locked --extra training`, Ruff lint/format, non-integration pytest with
coverage, and `uv pip check`. Validate both Compose smoke configurations.

The required failing-boundary acceptance is a fresh pushed Actions run on the
specified hosted runner. Inspect actual kernel/startup logs, readiness, domain route
and deployment smoke results, ordinary integration with both existing flags, and
the separate serial recovery gate. Retain run/job links and JUnit counts; a local
Windows/WSL run cannot establish the hosted kernel fix. A missing or skipped gate
remains a verification gap. No tests or assertions should change.

Fetch/compare upstream and `origin/main` before the implementation change and before
each push; integrate applicable incoming history and rerun affected checks.

## Risks and rollback

An OS label pins a release family rather than an immutable VM/kernel. Record the
actual kernel on each run and revisit if its image changes incompatibly. The older
runner has a finite support horizon. Reverting the workflow-only commit restores
the previous runner selection and may restore the startup failure; stored data and
local deployment configuration are unaffected.

## Human review and approval

Pending. Jacob approved read-only GitHub credential use to inspect CI logs on
October 19; that access approval is not approval of this runner design.

## Implementation outcome

Implementation pending human review. The diagnosis and retained evidence are
documentation-only; no repaired CI run or new application gate is claimed.
The plan/evidence/memory links were checked (36 local links/anchors), external
kernel/issue/retirement facts were checked against their primary sources, and
`git diff --check` passed before the documentation commit.
