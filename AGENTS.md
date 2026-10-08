# Repository workflow

The user requests a commit and push after every major change. Run the relevant
checks, commit the completed change, and push the working branch to `origin`.
Report any push failure so the user knows whether the commit reached the remote.

## Course scope

Read [the supplied course requirements](docs/course-requirements.md) before
planning feature work. They are the acceptance checklist for this class project.
The target uses LangChain with locally served pre-trained language models;
paid external model APIs and training a code language model are not required.
Separate model-management, tuning, and monitoring services, AI-generated Python
snippets, Docker, Kubernetes, and CI/CD are required course work. Keep missing
features marked outstanding; service separation is not conditional on commercial
scale, and templates alone do not establish AI code generation. Implementation
still follows reviewed plans and the contracts below.

## Development method

Follow [the development method](docs/development-methodology.md), adapted from
the user-supplied *AI-Assisted Software Engineering in a Research Project:
A Working Method*. Read [the project memory index](docs/memory/README.md) at
session start and the relevant linked findings before changing a subsystem.

- For substantive design changes: clarify requirements, challenge the idea,
  commit a written plan, obtain human review, then implement with continuous checks.
- Resolve questions answerable from source yourself. Surface all remaining
  ambiguities about intent, constraints, failure behavior, and acceptance criteria
  before finalizing a plan. Explain objections and simpler alternatives.
- Store plans as `docs/plans/YYYY-MM-DD-short-name-plan.md`, using
  [the template](docs/plans/template.md). Record explicit human approval and its
  scope before implementation; the roadmap alone is not approval of a design.
  Material deviations require an updated plan and renewed review.
- Local edits, documentation, and mechanical refactors use the compressed loop:
  state the scope, make the change, inspect the diff, run relevant checks.
  Changes to public contracts, defaults, ownership, or concurrency require a plan
  regardless of line count.
- Diagnose bugs with source/logs or instrumentation that confirms the mechanism.
  Verify the fix at the failing boundary or scale before calling it fixed.
- Never weaken assertions, add skips, or lower gates merely to obtain a pass.
  Explain each changed test against the requirement it checks.
- Seek independent review for concurrency, state machines, and rate/size arithmetic,
  preferably from a different vendor. Record reviewer, submitted scope, findings,
  and resolutions. Disclose unavailable review; do not label self-review independent.
- Keep measured results separate from generated explanations. Record execution
  provenance and raw evidence; verify factual claims against source or saved runs.
- Update short, evidence-linked memory files when a durable finding or rejected
  approach would otherwise be rediscovered. Keep these instructions current.

## Orientation and contracts

`src/ml_pipeline_pro/` is the canonical application. `tests/` holds unit/API
checks and `tests/integration/` holds real-service and isolated recovery checks.
`PLAN.md` is the milestone roadmap; `docs/project-status.md` records historical
audits and validation. Preserve the distinction between planned and verified work.

- Preserve `/api/v1` schemas, project scoping of referenced records, consistent
  errors/correlation IDs, and submission idempotency unless a reviewed plan changes them.
- Select checkpoints and tuning winners with validation metrics. Fit preprocessing
  on training rows; evaluate test data only after selection.
- Tuning child writes must fence parent ownership in the same MongoDB transaction.
  Preserve reserved configurations/IDs and original tuning deadlines during recovery.
- Keep serial CPU execution until concurrent-load/partition evidence supports a change.
- Verify artifact hash/size and preserve training artifacts during final evaluation.
- New routes/configuration require corresponding README endpoint documentation or
  `.env.example` updates. Update schemas, repository contracts, fixtures, and
  integration coverage when changing persistence or ownership semantics.
- Preserve locked dependencies, secret redaction, and the opt-in live-service gates.

## Verification commands

From the repository root, with `uv` installed:

```powershell
uv sync --locked --extra training
uv run --locked --extra training ruff check .
uv run --locked --extra training ruff format --check .
uv run --locked --extra training pytest -m "not integration" --cov
uv pip check
```

Run relevant tests after each meaningful implementation step. All fast checks
above must pass before committing application changes. For documentation-only
changes, validate local links/anchors, example syntax, factual sources, and
`git diff --check`. Build package changes with `uv build`.

Changes involving MongoDB, queues, workers, tuning ownership, or recovery also
require the affected real-service gates: follow [ordinary integration setup](docs/verification.md#ordinary-integration)
and [isolated recovery setup](docs/verification.md#run-the-suite). Ordinary integration
requires both `MLPP_RUN_INTEGRATION=1` and `MLPP_RUN_WORKER_INTEGRATION=1`;
recovery uses `MLPP_RUN_RECOVERY_INTEGRATION=1` separately and runs serially.
Record missing services or selected-case skips as verification gaps, not passes.
