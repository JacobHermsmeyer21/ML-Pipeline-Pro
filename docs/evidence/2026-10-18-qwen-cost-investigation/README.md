# October 18 Qwen CPU and prompt-cost investigation

Read-only investigation from `9e2dcaf` on October 18, 2026 America/New_York
(raw timestamps are October 19 UTC). No live inference, runtime configuration,
model, application, service or prompt behavior changed. There is **no measured
speedup** from this investigation. The [follow-up plan](../../plans/2026-10-18-qwen-cpu-prompt-cost-plan.md)
awaits human review and actual laptop access.

`9e2dcaf` added the parallel [laptop deployment plan](../../plans/2026-10-18-laptop-deployment-readiness-plan.md)
during investigation; application source remains unchanged from `91b0aef`. That
plan records Jacob's five-minute complete-reply target and pending review of its
timing profile. The 20-second calculations below describe current default-profile
constraints; they do not replace that selected target. Final demo readiness must
be checked under the separately approved deployment profile. Raw analysis already
records `9e2dcaf`; this summary corrects its initial application-baseline label.

## What the evidence establishes

The [retained laptop request](../2026-10-18-laptop-qwen-diagnostic/README.md)
spends **88.330474 of 99.3578565 runtime seconds (88.90%)** processing its
1,109 uncached input tokens. Generation takes 10.946295 seconds for 18 tokens;
model loading during the measured request takes only 0.0493319 seconds.
Preloading already removed nearly all load cost from the measured request.
Lowering an output cap cannot reduce tokens that already stopped at 18.

The exact [offline analysis](offline-analysis.json) checks the original request,
response and result hashes against their retained manifest, verifies the pinned
tokenizer, and confirms current guided/host instructions match the saved input.
All 30 render/count observations reproduce the runtime's **1,109 tokens**.

| Prompt segment | Standalone tokenizer count |
| --- | ---: |
| Guided policy including the tool-catalog introduction | 535 |
| Twelve-tool catalog | 367 |
| Separate host policy | 160 |
| History marker | 17 |
| User request | 19 |

Standalone counts are not an additive decomposition: template tokens, separators
and tokenization boundaries also contribute. Exact whole-request ablations below
use the counter again. Removing the catalog also removes its introduction. They
are **incomplete diagnostic prompts**, never sent to a model and never proposed
as deployable policies.

| Offline token-count ablation | Full input tokens | Estimated runtime at unchanged laptop rates |
| --- | ---: | ---: |
| Original | 1,109 | 99.36 s |
| Remove catalog and its introduction | 731 | 69.25 s |
| Remove separate host policy | 949 | 86.61 s |
| Remove both | 571 | 56.51 s |

These times are projections, not inference measurements. The calculation holds
generation and other time fixed and scales prompt time by token count:
`estimated_seconds = 10.946295 + 0.0810875 + tokens / 12.5551233881`.
Nonlinear prompt cost, cache reuse and changed answers can invalidate it. Even
halving input length projects 55.19 seconds. At the same rates, approximately
113 input tokens would exhaust the existing 20-second call budget; fitting within
it would require at most 112 whole tokens. Removing required policy is therefore
unlikely to be a sufficient safe fix by itself. This is an inference from the
baseline, not a demonstrated lower bound for other settings.

The request's `format` JSON schema is a grammar constraint, rather than text
included by this pinned renderer. Its JSON byte length must not be counted as
additional input tokens. Grammar processing overhead was not measured separately.
Context capacity 8192 is distinct from the actual 1,109 input tokens; reducing
capacity would not remove these instructions.

## CPU attribution and machine boundary

The [current CIM snapshot](current-machine.json) verifies a **Ryzen 7 7800X3D,
RX 9070, approximately 31.1 GiB RAM workstation**, not the Acer Ryzen 3 laptop.
There was no Ollama/llama-server process in that snapshot. The loopback 11434
port check was false. No remote laptop access is established. A workstation
process sample was recognized as irrelevant to laptop contention and was not
used for that claim. No service, user application or security process was stopped.

Saved laptop CPU observations cover all system work, with approximately 99.99%
busy CPU and sample gaps up to 32.219 seconds. They contain **no per-process CPU
samples, effective inference thread count, clock/AC observations, or paging/disk
activity counters**. They cannot distinguish inference saturation from external
contention, confirm thermal throttling, exclude paging, or establish why the
sampler was delayed. The runner's `using 5 threads for HTTP server` line is not
an inference-thread measurement. Neither the CPU-contention mechanism nor the
earlier API timeout-overrun mechanism is resolved by this analysis.

On this workstation only, three counter preparations take 0.2342-0.2687 seconds;
30 warmed render/count calls take 1.417-2.629 milliseconds (mean 1.674 ms).
These observations separate host token counting from model prompt evaluation on
this machine. They do not characterize laptop setup/tokenizer latency or prove
timely application timeout enforcement there. Individual observations and source/
package identities are retained in [the raw result](offline-analysis.json).

## What to compare next

The [reviewable plan](../../plans/2026-10-18-qwen-cpu-prompt-cost-plan.md) first
attributes runner versus background CPU and records paging, clocks and observer
overhead on the actual laptop. It then screens request-local thread counts 2/3/4,
holding artifact, context, output, schema and required demo services fixed. Only
an identified idle duplicate repository stack is eligible for a separate stop/
restore comparison. Three uncached baseline/candidate pairs are required before
retaining an incremental speedup. Deadlines and original gates remain unchanged.

Prompt compression needs an exact policy review and complete-turn test. Changing
only the first-read prompt can invalidate prefix reuse on the subsequent answer;
a faster first step alone could misrepresent the whole turn. Preserve required
guidance and evidence checks and compare both calls together.

Compatibility was checked against the pinned official
[Ollama 0.40.2 option definitions](https://github.com/ollama/ollama/blob/v0.40.2/api/types.go):
`num_thread` and `num_batch` are runner options; effective automatic selection
still needs observation rather than inference from declared defaults. Official
[chat API timing definitions](https://docs.ollama.com/api/chat) distinguish prompt,
cached-prompt, generation and load fields. Current docs do not by themselves
establish every option's behavior on the installed runner.

## Reproduction and verification

The offline protocol was written in the plan before the run: unchanged retained
request, three counter preparations, three loop warmups, 30 saved observations,
exact count/hash checks, no inference, and a two-minute total analysis budget.
The run completed within that budget. Execute from the repository root with the
locked environment and explicitly installed checksum-pinned local tokenizer;
no download or server is needed:

```powershell
uv run --locked --extra training python `
    docs/evidence/2026-10-18-qwen-cost-investigation/analyze_prompt.py `
    --output artifacts/laptop-qwen-cost-investigation/offline-analysis.json
```

The [executed source](analyze_prompt.py) is retained beside its result.
[Manifest](manifest.json) records hashes and sizes. Machine fields exclude serial
numbers, usernames, host names and full command lines/environments. Incidental
workstation process samples remain only in ignored artifacts.

Checks on this working-tree addition to `9e2dcaf` used repository-local uv with
`--cache-dir .uv-cache`; sync and runs used `--offline` with the unchanged lock:

- [Locked sync](sync.log): 114 resolved, 109 installed packages checked.
- [Ruff lint](ruff-check.log) and [format](ruff-format.log): pass; 186 files formatted.
- [Fast suite](fast-tests.log): **611 passed, 73 integration cases deselected**,
  44.93 seconds, 80% rounded host coverage, no selected skips or warnings.
- [Dependency compatibility](pip-check.log): all 109 installed packages compatible.
  PowerShell wraps uv's native stderr in `NativeCommandError`; both sync and
  compatibility exited zero, as did Ruff and pytest.
- Local Markdown links/anchors, new PowerShell example syntax, evidence hashes,
  script syntax and `git diff --check` are checked before commit.

Existing tests/assertions are unchanged. No new model gate ran and no domain,
service or worker implementation changed. Ordinary/recovery integration was not
selected. Arithmetic/source claims were self-reviewed; independent review has
not occurred. The plan leaves it pending before sampling/deadline/rate
implementation and live trials. Application acceptance and a faster laptop demo
remain outstanding.
