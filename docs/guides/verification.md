# Verification

This is the canonical guide for fast checks, ordinary real-service integration,
isolated worker recovery, and repeating the historical validation workload.
Run from the repository root. Missing services and selected-case skips are gaps.
Current commands do not turn historical results into new verification evidence.

## Fast checks

```powershell
uv sync --locked --extra training
uv run --locked --extra training ruff check .
uv run --locked --extra training ruff format --check .
uv run --locked --extra training pytest -m "not integration" --cov
uv pip check
```

Package changes also require `uv build`. Documentation-only changes require local
link/anchor checks, example syntax and factual source checks, and `git diff --check`.
See [AGENTS.md](../../AGENTS.md#verification-commands) for the standing gate policy.

## Ordinary integration

With Docker Compose 2.24 or later installed:

```powershell
docker compose -f compose.yaml -f tests/integration/compose.uploads.yaml `
    up --build --wait --wait-timeout 300
if ($LASTEXITCODE -ne 0) { throw 'Integration stack failed to start.' }
uv sync --locked --extra training
$env:MLPP_RUN_INTEGRATION = '1'
$env:MLPP_RUN_WORKER_INTEGRATION = '1'
try {
    uv run --locked --extra training pytest -m "integration and not recovery"
} finally {
    Remove-Item Env:MLPP_RUN_INTEGRATION
    Remove-Item Env:MLPP_RUN_WORKER_INTEGRATION
}
```

On macOS/Linux use
`MLPP_RUN_INTEGRATION=1 MLPP_RUN_WORKER_INTEGRATION=1 uv run --locked --extra training pytest -m "integration and not recovery"`.
Both flags are required; omitting the worker flag skips three queued workflow
cases and the uploaded-CSV worker case. The upload test overlay enables the new
route and shares durable CSV storage with a read-only worker mount. A domain stack
using `compose.dashboard.yaml` already provides that capability. Upload boundary
cases require it; a disabled route is a verification failure, not a skipped pass.
The training extra is required for real training and direct tuning recovery.
Tests delete their generated metadata; queued artifacts remain in the shared volume.
For independent services/ports, use the [isolated repeat setup](#repeat-the-full-suite)
and its `MLPP_TEST_API_BASE_URL`, `MLPP_TEST_MONGODB_URI`, and
`MLPP_TEST_REDIS_URL` overrides. The [CI workflow](../../.github/workflows/ci.yml)
defines the automated checks; [project status](../project/project-status.md#validation-evidence)
retains results by source revision.

## Worker and dependency recovery validation

The recovery suite runs ten controlled failure cases in its own five-service
Compose project. It exercises the production API, Redis/Celery transport, Beat
scheduler, MongoDB repositories and transactions, and CPU PyTorch adapter.

| Failure | Checked behavior |
| --- | --- |
| Worker killed during standalone training | Beat redispatches after natural lease expiry; the second attempt succeeds and downloads pass hash verification |
| Worker killed during tuning training | The reserved configuration and experiment ID survive; the same trial is reclaimed without duplicate records |
| Worker killed during final evaluation or before its commit | Completed training is reused; original manifests remain readable; exactly one winner receives test metrics |
| Worker killed twice, for standalone training and tuning | The two-attempt test limit produces terminal failure; pending tuning children close without allocating another trial |
| MongoDB stopped during tuning ownership checks or final persistence | An actual driver error is observed; expired work is recovered after MongoDB restarts |
| Redis stopped during experiment or tuning submission | The API returns `503` while retaining one queued record; Beat dispatches it after Redis restarts, without a client resubmission |

Recovered tuning jobs retain both their original search and overall deadlines.
Trials keep validation-only metrics. The suite downloads checkpoints and manifests
and verifies their recorded hashes after recovery.

### Run the suite

Install Docker with Compose 2.24 or later and synchronize the training extra.
The fixture builds a dedicated application image from the current checkout:

```powershell
uv sync --locked --extra training
$env:MLPP_RUN_RECOVERY_INTEGRATION = '1'
try {
    uv run --locked --extra training pytest -m recovery `
        --junitxml=artifacts/recovery-validation/junit.xml
} finally {
    Remove-Item Env:MLPP_RUN_RECOVERY_INTEGRATION
}
```

On macOS/Linux, use
`MLPP_RUN_RECOVERY_INTEGRATION=1 uv run --locked --extra training pytest -m recovery`.
This flag is separate from the ordinary integration flags. Run these cases serially;
the stack uses API port 28000, MongoDB port 47017, and Redis port 26379. Keep these
ports available. The fixture creates an independently named `mlpp-recovery-*`
project and removes its containers and volumes on completion, including assertion
failures. An interrupted test process may require manual cleanup of its named
project using the same Compose files.

The [recovery Compose override](../../tests/integration/compose.recovery.yaml) uses the
separate `ml-pipeline-pro:recovery` image, discards
the local `.env`, uses a dedicated database and volumes, and sets a ten-second
lease with a two-attempt limit. Production defaults remain a thirty-second lease
and three attempts. The suite never invokes recovery tasks directly, edits leases,
or publishes replacement tasks. Recovery uses the existing fifteen-second Beat
schedule, so these tests take several minutes.

### Controlled boundaries and evidence

Only this stack mounts the [test worker entrypoint](../../tests/integration/recovery_worker.py).
It pauses after an optimizer step, after loading the selected checkpoint for
evaluation, or after writing the evaluated manifest but before committing its
references. Real execution, heartbeat tasks, repository writes, and transport
continue through the production code. The pauses make failure placement repeatable;
they do not model arbitrary timing or concurrent worker throughput.

Each run saves before/after MongoDB snapshots and full service logs under
`artifacts/recovery-validation/mlpp-recovery-*/`. These ignored artifacts contain
the owning tokens, attempts, reservations, deadlines, metrics, and artifact
references needed to inspect the assertions. JUnit output is saved at the path
given on the command line. CI runs the ordinary integration suite and this
separate recovery gate, then uploads the recovery evidence even on failure.

This suite complements the real-MongoDB transaction takeover regressions in
[the project audit](../project/project-status.md#ownership-fix-validation). It does not
increase worker/trial concurrency. Concurrent load, arbitrary network partitions,
shared deployment, and backup/restore exercises remain further work. Container
worker/scheduler execution is evidenced by logs and state assertions; it is not
included in host-process coverage percentages.

## Ten-iteration validation: October 6, 2026

This is a historical validation report for `3bf71af`; its counts and environment
are preserved below. The later [project audit](../project/project-status.md) against
`0e37e6e` reran the then-existing suites and identified tuning ownership gaps outside
these cases. Repeated passing runs demonstrate the tested behavior, not complete
process-loss recovery, concurrency safety, or production readiness.

All ten consecutive full-suite iterations passed against commit
`3bf71af9513a1fbf371771dd9fde2c21923a00d9`: **1,350 passed, zero failures,
zero errors, and zero skipped tests**. Each iteration ran the same 135 cases:
126 unit/API/training/tuning cases and nine real-service integration cases.
No iterations were retried.

### Results

| Iteration | Passed | Real-service cases included | Failed / errors / skipped | Wall time |
| --- | --- | --- | --- | --- |
| 1 | 135 | 9 | 0 / 0 / 0 | 24.437 s |
| 2 | 135 | 9 | 0 / 0 / 0 | 18.407 s |
| 3 | 135 | 9 | 0 / 0 / 0 | 17.187 s |
| 4 | 135 | 9 | 0 / 0 / 0 | 18.343 s |
| 5 | 135 | 9 | 0 / 0 / 0 | 17.766 s |
| 6 | 135 | 9 | 0 / 0 / 0 | 18.656 s |
| 7 | 135 | 9 | 0 / 0 / 0 | 17.859 s |
| 8 | 135 | 9 | 0 / 0 / 0 | 17.828 s |
| 9 | 135 | 9 | 0 / 0 / 0 | 18.234 s |
| 10 | 135 | 9 | 0 / 0 / 0 | 29.079 s |

Total test-process wall time was **197.890 seconds**, excluding stack build and
startup; median iteration time was **18.288 seconds**. The first run included a
cold worker import, and the tenth included coverage collection and report output.
Timing describes this functional workload rather than production throughput.

### Environment and scope

The Windows host used Python 3.11.5, pytest 9.1.1, CPU PyTorch 2.14.1,
Optuna 5.0.0, and NumPy 2.4.6. Docker Engine 29.8.2 ran the API, Celery worker,
recovery scheduler, MongoDB 8.0.32, and Redis 7.4.11. The worker retained its
one-CPU, 1 GiB, one-concurrent-job limits.

Each round launched a fresh pytest process against one dedicated Compose project,
`mlpp-ten-iteration-validation`, kept running across the ten rounds. Its independent
volumes and ports (API 18000, MongoDB 37017, Redis 16379) isolated its records from
the normal development stack. Tests generated new project IDs and recovery
databases for each case. The checked-in
[Compose override](../../tests/integration/compose.validation.yaml) matches the one used.

The suite exercised:

- CSV validation, content hashes, split preservation, and training-only preprocessing.
- Project access, isolation, pagination, idempotency, and safe error/log responses.
- Reproducible PyTorch metrics/checkpoints and validation-based checkpoint selection.
- Real MongoDB indexes, atomic worker claims, lease recovery, and stale-owner rejection.
- Bounded Optuna searches, retained trial failures, reservation replay, deadlines,
  cancellation, and final test evaluation of only the selected checkpoint.
- Queued Redis/Celery execution, verified artifact downloads, and model version registration.

Worker logs confirm ten completed queued training jobs, ten completed three-trial
tuning jobs, and ten actively cancelled tuning jobs. The other tests additionally
exercise training and tuning directly, including simulated failures and recovery.

After all rounds, both APIs reported ready. All five validation containers were
running with zero restarts and no memory-limit kills. The validation database had
zero remaining documents in all seven test collections, no temporary tuning test
databases remained, and both task queues and unacknowledged deliveries were empty.
The temporary stack and its volumes were then removed. Ruff linting/formatting
and compatibility checks for all 86 installed host packages also passed.

### Coverage and evidence

The tenth iteration measured **84.93% combined statement/branch coverage**:
1,281 of 1,472 statements (87.02%) and 212 of 286 branches (74.13%). This measures
the host pytest process. Container worker/scheduler code is exercised through
integration assertions but its execution is not included in these coverage counts.
The runs use synthetic classification data and sequential repetition; they are
functional reliability checks, with no concurrent-load or generalization benchmark.

Every iteration emitted one existing Starlette deprecation warning about the
HTTPX TestClient adapter. It did not fail any test.

Local evidence is retained under `artifacts/test-validation/20261006T223302Z/`:
`summary.json`, `statistics.json`, ten pytest logs, ten JUnit XML reports,
`coverage.json`, `coverage-html/index.html`, `compose.log`, the exact Compose
override, and before/after container and final service snapshots. Raw artifacts
are ignored by Git; this report preserves the results in the repository.

### Repeat the full suite

With Docker running and dependencies installed using `uv sync --locked --extra training`,
run from the repository root in PowerShell. The loop creates a log and JUnit report
for each iteration and stops on a pytest failure. Inspect the reports to ensure
all expected cases ran without skips.

```powershell
$composeArguments = @(
    '--project-name', 'mlpp-ten-iteration-validation',
    '--file', 'compose.yaml',
    '--file', 'tests/integration/compose.validation.yaml'
)
docker compose @composeArguments up --build --wait --wait-timeout 300
if ($LASTEXITCODE -ne 0) { throw 'Validation stack failed to start.' }

$env:MLPP_RUN_INTEGRATION = '1'
$env:MLPP_RUN_WORKER_INTEGRATION = '1'
$env:MLPP_TEST_API_BASE_URL = 'http://127.0.0.1:18000/api/v1'
$env:MLPP_TEST_MONGODB_URI = 'mongodb://127.0.0.1:37017/?directConnection=true'
$env:MLPP_TEST_REDIS_URL = 'redis://127.0.0.1:16379/0'
$resultDirectory = Join-Path (Get-Location) ('artifacts/test-validation/' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $resultDirectory | Out-Null
try {
    foreach ($iteration in 1..10) {
        $testArguments = @('-q', '-m', 'not recovery', '--durations=10', "--junitxml=$resultDirectory/iteration-$iteration.xml")
        if ($iteration -eq 10) {
            $testArguments += @('--cov=ml_pipeline_pro', "--cov-report=html:$resultDirectory/coverage-html")
        }
        & ./.venv/Scripts/python.exe -m pytest @testArguments 2>&1 |
            Tee-Object -FilePath "$resultDirectory/iteration-$iteration.log"
        if ($LASTEXITCODE -ne 0) { throw "Iteration $iteration failed; inspect its log." }
    }
} finally {
    docker compose @composeArguments down --volumes
    @('MLPP_RUN_INTEGRATION', 'MLPP_RUN_WORKER_INTEGRATION',
      'MLPP_TEST_API_BASE_URL', 'MLPP_TEST_MONGODB_URI', 'MLPP_TEST_REDIS_URL') |
        ForEach-Object { Remove-Item "Env:$_" -ErrorAction SilentlyContinue }
}
```
