# October 18 laptop Qwen diagnostic

Jacob approved the [bounded plan](../../plans/2026-10-18-laptop-qwen-diagnostic-plan.md)
on October 18, 2026. One live request ran on the actual presentation laptop from
22:13:57 to 22:16:03 America/New_York (the raw UTC timestamps fall on October 19).
The source was clean commit `0f6ed208ab983db050cb4e441075b15cb688f632`, already
pushed to `origin/person-a/conversation-foundation`. The diagnostic passed its
eventual first-step response criterion. Application/demo acceptance was not run.

## Measured result

| Observation | Result | Raw source |
| --- | --- | --- |
| Machine | Acer Aspire A515-46, Ryzen 3 3350U, four logical processors, Vega 6, 19,261,304,832 bytes RAM, Balanced power plan | [CIM snapshot](machine.json), [run](result.json) |
| Runtime/model | Ollama 0.40.2, pinned Qwen 2.5 7B Q4_K_M JSON-tools profile, context 8192/output cap 1024 | [Provenance and residency](result.json) |
| Residency | Empty before warmup; one matching artifact afterward, `size_vram=0`; CPU model buffers in runner log | [Run](result.json), [runner excerpt](runner-excerpt.log) |
| Warmup | 24.281 seconds, empty generation/load only, separate from the measured request | [Run](result.json), [warmup](warmup.json) |
| Measured HTTP request | Exactly one `/api/chat`; 99.359 seconds wall time, 480-second budget; no retry | [Run](result.json), [console](run-01-console.log) |
| Runtime request total/load | 99.3578565 seconds total; 0.0493319 seconds load | [Response](response.json) |
| Prompt processing | 88.330474 seconds, 1,109 tokens; counter and runtime agree; zero cached prompt tokens | [Response](response.json), [run](result.json) |
| Generation | 10.946295 seconds, 18 API-reported output tokens | [Response](response.json) |
| Strict semantic result | `get_experiment` with exactly `{"experiment_id":"exp-low"}`; `done_reason=stop`; no output repair, read dispatch or domain write | [Response](response.json), [validated step](result.json) |
| Application acceptance | Original ten/seven gates, complete turn and actual-ID tutorial not rerun; deadlines unchanged | [Approved scope](../../plans/2026-10-18-laptop-qwen-diagnostic-plan.md) |

Most measured inference time is prompt processing. The complete first read takes
longer than the unchanged 20-second per-model-call limit. Eventual completion
does not establish interactive readiness, a complete answer, correctness after
tool evidence, snippets, or a fix to the earlier API timeout overrun. This is one
request, not a repeated performance comparison with the different October 14
prompt/runtime workload. No model/runtime/prompt change was tested.

## Resource observations and limits

[Eight raw Windows API snapshots](result.json) span 97.937 seconds during the
request. [Derived observations](derived-observations.json) use cumulative system
CPU times: idle delta 312,500 and kernel-plus-user delta 3,913,125,000, both in
100 ns units. Since kernel includes idle, busy fraction is
`1 - 312500 / 3913125000 = 0.9999201406`, approximately **99.99% system CPU busy**.
This covers all system work; it does not attribute every cycle to Qwen.

Available physical memory ranges from 3,912,450,048 to 4,141,330,432 bytes
(approximately 3.64-3.86 GiB); available commit ranges from 3,579,437,056 to
3,648,045,056 bytes. No sample shows exhausted available memory. These snapshots
do not establish actual disk paging activity or exclude transient memory pressure.
No background workload was stopped or power setting changed for this baseline.
Repository tests finished before the model request.

The sampling task requests a five-second sleep, but actual intervals range from
5.547 to 32.219 seconds. The reason for these gaps is unknown. Scheduling delay or
blocking resource inspection are hypotheses, not a confirmed mechanism. The
sampling observations do not prove timely deadline enforcement under load.
Transport cancellation passed deterministic stalled-body tests; the real request
completed well before 480 seconds, so live deadline expiry was not exercised.
The retained runner excerpt ends with `all slots are idle`; cancellation/retry was
not needed. Residency alone would not establish an idle runner after a timeout.

The runtime was nonresident before explicit warmup. No inspection prompt primed
the cache; the response reports `prompt_eval_cached_count=0` and the runner reports
zero cached tokens at task start. No weights were pulled and no cloud endpoint,
tool action or generated code was executed. The request uses only synthetic
evaluation input. Full headers, credentials and process environments were excluded.

## Verification and provenance

The harness revision was tested as a working-tree addition to `0f5812c`, then
committed unchanged as `0f6ed20`. Python is 3.11.17; LangChain core 1.6.9,
LangChain Ollama 1.1.0 and Ollama SDK 0.6.3 are in the run provenance. The counter
checks the installed artifact/runtime/template and local tokenizer checksum;
dependencies are from the unchanged lockfile.

Commands used the repository-local `artifacts/tooling/uv/uv.exe`, with
`UV_CACHE_DIR=artifacts/tooling/uv-cache`:

```powershell
uv sync --locked --extra training
uv run --locked --extra training ruff check .
uv run --locked --extra training ruff format --check .
uv run --locked --extra training pytest -m 'not integration' --cov `
    --basetemp artifacts/laptop-qwen-diagnostic/pytest-full `
    --junitxml artifacts/laptop-qwen-diagnostic/fast-junit.xml
uv pip check
uv run --locked --extra training python -m evaluations.laptop_qwen_diagnostic `
    --run-laptop-diagnostic `
    --machine-info artifacts/laptop-qwen-diagnostic/machine.json `
    --output artifacts/laptop-qwen-diagnostic/run-01
```

- Locked sync resolved 114 packages with 109 installed.
- [Ruff lint](ruff-check.log) and [format](ruff-format.log) pass; 182 files formatted.
- [Fast tests](fast-tests.log): **611 passed**, 73 integration/recovery deselected,
  no selected skips or warnings, 80% rounded host coverage, 221.18 seconds.
  Thirteen cases exercise the new diagnostic's actual safety/acceptance boundaries.
- [Compatibility](pip-check.log): all 109 installed packages compatible. The
  PowerShell log wraps native stderr in `NativeCommandError`; the command exits
  zero and reports compatible packages.
- Local Markdown links/anchors, PowerShell example syntax and whitespace checks
  pass. No service/ownership implementation changed; ordinary/recovery integration
  was not selected. The original model gates were not relabelled as passes.

Separate same-vendor Codex review examined cancellation, request/token/body bounds,
exact SDK bytes, retry/tool isolation, strict validation, provenance and failures.
Four findings were corrected and re-reviewed before inference; the
[plan record](../../plans/2026-10-18-laptop-qwen-diagnostic-plan.md#implementation-outcome)
names the reviewer and resolutions. External-vendor review was unavailable.
The same separate reviewer recomputed all derived observations from the saved
raw run after inference and confirmed the arithmetic. The guide was corrected
to describe five seconds as the sampling target, rather than observed cadence.

[Request bytes](request.json) have SHA-256
`f19f7fb9507375f344ae5ca627780837405cc08afe8c0d1747112b11a780635f`.
The run records the harness SHA-256 and complete model identities.
[Manifest](manifest.json) supplies hashes/sizes of the copied raw evidence and
derived observations. The evidence directory's `.gitattributes` entry preserves
recorded bytes through Git rather than converting CRLF. The filtered runner
excerpt normalizes trailing whitespace; the original log remains local.
Generated descriptions in this README are separate from
those observations. JUnit and initial machine/log-offset records remain locally
under ignored `artifacts/laptop-qwen-diagnostic/`; needed safe results are retained
here. Initial harness checks caught missing request revision, disabled fixture
chat and SDK exception-wrapping mistakes; these were corrected before all 13
harness cases and all 611 fast cases passed. No live request was retried.
