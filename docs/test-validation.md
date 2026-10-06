# Ten-iteration validation: October 6, 2026

This is a historical validation report for `3bf71af`; its counts and environment
are preserved below. The later [project audit](project-status.md) against
`0e37e6e` reran the current suites and identified tuning ownership gaps outside
these cases. Repeated passing runs demonstrate the tested behavior, not complete
process-loss recovery, concurrency safety, or production readiness.

All ten consecutive full-suite iterations passed against commit
`3bf71af9513a1fbf371771dd9fde2c21923a00d9`: **1,350 passed, zero failures,
zero errors, and zero skipped tests**. Each iteration ran the same 135 cases:
126 unit/API/training/tuning cases and nine real-service integration cases.
No iterations were retried.

## Results

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

## Environment and scope

The Windows host used Python 3.11.5, pytest 9.1.1, CPU PyTorch 2.14.1,
Optuna 5.0.0, and NumPy 2.4.6. Docker Engine 29.8.2 ran the API, Celery worker,
recovery scheduler, MongoDB 8.0.32, and Redis 7.4.11. The worker retained its
one-CPU, 1 GiB, one-concurrent-job limits.

Each round launched a fresh pytest process against one dedicated Compose project,
`mlpp-ten-iteration-validation`, kept running across the ten rounds. Its independent
volumes and ports (API 18000, MongoDB 37017, Redis 16379) isolated its records from
the normal development stack. Tests generated new project IDs and recovery
databases for each case. The checked-in
[Compose override](../tests/integration/compose.validation.yaml) matches the one used.

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

## Coverage and evidence

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

## Repeat the full suite

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
$env:MLPP_TEST_MONGODB_URI = 'mongodb://127.0.0.1:37017'
$env:MLPP_TEST_REDIS_URL = 'redis://127.0.0.1:16379/0'
$resultDirectory = Join-Path (Get-Location) ('artifacts/test-validation/' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $resultDirectory | Out-Null
try {
    foreach ($iteration in 1..10) {
        $testArguments = @('-q', '--durations=10', "--junitxml=$resultDirectory/iteration-$iteration.xml")
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
