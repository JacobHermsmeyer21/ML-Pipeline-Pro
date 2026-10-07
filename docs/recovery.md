# Worker and dependency recovery validation

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

## Run the suite

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

The [recovery Compose override](../tests/integration/compose.recovery.yaml) uses the
separate `ml-pipeline-pro:recovery` image, discards
the local `.env`, uses a dedicated database and volumes, and sets a ten-second
lease with a two-attempt limit. Production defaults remain a thirty-second lease
and three attempts. The suite never invokes recovery tasks directly, edits leases,
or publishes replacement tasks. Recovery uses the existing fifteen-second Beat
schedule, so these tests take several minutes.

## Controlled boundaries and evidence

Only this stack mounts the [test worker entrypoint](../tests/integration/recovery_worker.py).
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
[the project audit](project-status.md#ownership-fix-validation). It does not
increase worker/trial concurrency. Concurrent load, arbitrary network partitions,
shared deployment, and backup/restore exercises remain further work. Container
worker/scheduler execution is evidenced by logs and state assertions; it is not
included in host-process coverage percentages.
