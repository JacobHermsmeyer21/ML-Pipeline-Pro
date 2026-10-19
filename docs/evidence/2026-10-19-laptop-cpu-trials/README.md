# October 19 laptop CPU profiling and thread trials

Jacob approved [resource profiling and request-local thread trials](../../plans/2026-10-18-qwen-cpu-prompt-cost-plan.md#human-review-and-approval)
on October 18. The actual Acer Aspire A515-46 / Ryzen 3 3350U ran twelve serial
inference requests from 00:59:43 to 01:27:56 EDT on October 19, 2026. All twelve
passed the original strict first-read and zero-cache checks. **No candidate met
the fixed 20% median improvement criterion.** Application settings are unchanged.

## Measured results

Screening observations are individual pairs, not confirmed performance claims.
Automatic threads selected four inference and four batch threads throughout.

| Screen | Fresh automatic baseline | Candidate | Semantic/cache checks |
| --- | ---: | ---: | --- |
| 2 threads | 99.328 s | 228.359 s | Pass |
| 3 threads | 97.515 s | 143.718 s | Pass |
| 4 threads | 103.891 s | 103.485 s | Pass |

The best relative screen, explicit four threads, received three new pairs:

| Pair | Automatic threads | Explicit four threads |
| --- | ---: | ---: |
| 1 | 104.484 s | 103.313 s |
| 2 | 108.469 s | 111.281 s |
| 3 | 111.157 s | 112.438 s |
| Median | **108.469 s** | **111.281 s** |

The candidate median is 2.592% slower. Both arrangements have the same effective
four-thread configuration; no inference setting is retained or deployed. Three
pairs establish descriptive evidence only, with no statistical significance or
claim about other power conditions. [Raw results](result.json) and the
[reproducible analysis](analysis.json) retain individual observations and ranges.
Each trial directory retains exact request/warmup/response/result JSON and filtered
runner logs; for example [the two-thread response](screen-2-candidate/response.json).

Every response uses 1,109 prompt tokens and the exact unrepaired
`get_experiment(experiment_id="exp-low")` first step. Both runtime response and
runner log establish zero cached prompt tokens. Context 8192, output cap 1024,
batch/micro-batch 1024, CPU residency and pinned artifact/runtime are unchanged.
Warmups are separate (12.594-77.328 seconds); total experiment time is 1693.265
seconds, within the 60-minute/16-measured-request budgets. The normal path used
twelve requests with no failures/retries. Cleanup unloaded the model and reaped
the observer normally (exit 0, no forced stop).

## Profiling observations and limits

The observer captured **328 snapshots** with process CPU/working set, system CPU,
power state and raw/formatted PDH memory, paging, disk and processor counters.
[Compressed raw snapshots](samples.jsonl.gz), [unfiltered derived intervals](resource-summary.json.gz)
and [analysis source](analyze.py) preserve the measurements and calculations.

- The median inference sample gap is 2.022 seconds, but the maximum is **94.133
  seconds**. Median inference sampling duration is 0.064 seconds, with a maximum
  of **92.063 seconds**. Thus the two-second target was not sustained under load.
- The observer records 11.672 cumulative CPU seconds including startup/all phases.
  This is process CPU consumption, not proof of negligible observer perturbation.
  The [four-sample smoke test](observer-smoke/samples.jsonl) achieved 2.006-2.049
  second gaps before inference; it does not describe under-load behavior.
- There are 51,810 process-access error observations across snapshots, rather than
  that many distinct inaccessible processes. Protected/system process counters
  are missing. No top-level observer errors are recorded. Long, non-atomic
  collections and missing access make per-phase CPU totals incomplete; the
  analysis labels its residuals as diagnostic estimates, **not measured competing
  CPU**. CPU contention and the cause of scheduling delays remain unresolved.
- The laptop stayed on battery (`ac_line_status=0`) with the Balanced power plan;
  reported charge fell from **67% to 18%**. This is not an AC-powered comparison.
  Battery/thermal effects were not isolated. No power-plan/affinity/priority change
  or arbitrary process termination occurred.
- Observed available physical memory is 4,086,779,904-5,235,908,608 bytes. Windows
  reports page input up to 9519.824 pages/s and disk traffic up to 39,221,867.556
  bytes/s in inference-labelled samples. These observations do not establish a
  paging cause or identify which workload generated I/O.

The one required Compose stack, `mlpp-post-reboot-validation`, reports ten running
services both in the initial preflight and the approved post-run status check.
No duplicate stack was found, so its service-stop candidate was omitted. No
container/service management operation was issued. An intermediate sandbox-only
Docker check was denied; the final approved check resolved that status gap.

## Provenance and verification

Execution revision is `8829d31` plus the uncommitted harness described in
`result.json.working_tree`. Two pre-run commit/push attempts could not execute
because automatic approval review was at capacity. This was a review-service
failure, not an unsafe-action verdict. The run therefore records exact script
hashes in [sources.json](sources.json), with byte-identical copies under
[source/](source/), instead of claiming a clean committed execution. The canonical
application/fixtures were unchanged from that revision. Approval review recovered
after execution; fetch found no incoming branch commits and `origin/main` remained
an ancestor (42 commits behind HEAD at that fetch).

Automatic review then rejected exporting this broad local telemetry bundle.
After reviewing the payload categories and the confirmed destination
`https://github.com/JacobHermsmeyer21/ML-Pipeline-Pro`, Jacob explicitly approved
**"Publish the complete evidence bundle"** on October 19. This covers process
names/PIDs/resource counters, hardware/battery readings, package versions and
synthetic model requests/responses. No process command lines, credentials or real
conversation bodies are included.

[Machine metadata](machine.json) identifies four cores/logical processors,
19,261,304,832 bytes physical RAM and Vega 6. CPU/manufacturer/model were freshly
rechecked through the Windows hardware registry because CIM access was restricted;
core/GPU values came from the session's earlier approved local CIM check, and
native memory observation reconfirmed the physical total. The registry snapshot
is an operator check, not hardware attestation. [Model/counter provenance](provenance.json),
[runtime metadata](metadata.json), [package/lock identity](environment.json) and
the final SHA-256 manifest retain the execution inputs. Raw timestamps remain UTC.

Locked sync, Ruff lint/format, dependency compatibility and the complete fast gate
pass: **629 passed, 73 integration deselected, 80% rounded coverage**, no selected
skips/warnings. [Test output](final-fast-tests.log) and [JUnit](final-fast-junit.xml)
are retained. The suite reports 6254.15 seconds including a long session stall;
this is not a suite-speed measurement. Existing assertions are unchanged.
PowerShell syntax, local documentation links/anchors, JSON/gzip/source hashes and
whitespace are checked before commit. The new analysis is rerun against the
compressed retained copy. Independent review is unavailable; source, FFI and
arithmetic review was self-review.

Ordinary/recovery gates were not selected: no service, persistence or worker logic
changed. This first-step diagnostic does not rerun the original ten dialogue/seven
snippet gates, a complete reply, timeout cancellation under application load or
the actual-ID tutorial. Laptop demo readiness and the separate five-minute
deployment design remain outstanding. Sampling delays are observed; their cause
is not established by this experiment.

```powershell
uv run --offline --locked --extra training python -m evaluations.laptop_cpu_trials `
    --run-laptop-thread-trials `
    --machine-info artifacts/laptop-cpu-trials/machine.json `
    --output artifacts/laptop-cpu-trials/run-01

python docs/evidence/2026-10-19-laptop-cpu-trials/analyze.py `
    docs/evidence/2026-10-19-laptop-cpu-trials `
    --output artifacts/laptop-cpu-trials/reproduced-analysis.json
```

Use a fresh output directory for a future authorized live run. The first command
documents this execution, not an instruction to retry automatically. Analysis of
the retained copy is offline and sends no inference request.
