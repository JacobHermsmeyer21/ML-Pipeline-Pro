# Laptop Qwen prompt processing dominates the first read

October 18, 2026, execution revision `9e2dcaf` (application baseline `91b0aef`):
[offline investigation](../evidence/2026-10-18-qwen-cost-investigation/README.md)
reproduces all 1,109 input tokens of the retained CPU-laptop diagnostic with the
pinned tokenizer/renderer. Prompt evaluation is 88.330474 of 99.3578565 runtime
seconds (88.90%); generation is 10.946295 seconds, with only 0.0493319 seconds
loading during the measured request. More preloading or lowering an already
unreached output cap does not address the dominant measured cost.

The catalog is 367 standalone tokens, separate host policy 160 and guided policy
including the catalog introduction 535. Independently tokenized segments are not
additive. Whole-request removal of catalog/introduction and host text leaves 571
tokens. At unchanged laptop rates that projects 56.51 seconds; it is an incomplete
policy ablation, never a measured or supported optimization. Safe compression
alone has no demonstrated path to the unchanged default 20-second limit. This
does not rule out Jacob's selected five-minute complete-reply target in the
parallel [deployment plan](../plans/2026-10-18-laptop-deployment-readiness-plan.md),
whose timing-profile implementation still awaits review.

System CPU saturation does not establish competing CPU load. Saved laptop samples
lack per-process CPU, effective inference-thread count, clocks/AC and disk paging.
The log's five HTTP-server threads are not inference-thread evidence. The current
session is verified as the RX 9070 workstation; its offline token-count timing
cannot establish laptop latency. No live trials or measured speedup resulted.

The [follow-up plan](../plans/2026-10-18-qwen-cpu-prompt-cost-plan.md) awaits review
and actual laptop access. Compare CPU factors individually with uncached repeats,
and preserve prompt prefixes across read and answer when evaluating compression.
Revisit after attributed laptop CPU observations or a reviewed prompt/runtime
experiment. API timeout-overrun and full laptop acceptance remain separate issues.

October 19: Jacob's request to run profiling/thread trials approves plan steps 2-3.
[Actual laptop evidence](../evidence/2026-10-19-laptop-cpu-trials/README.md) records
twelve uncached, semantically valid first-step requests. Two threads take 228.359
seconds versus a fresh 99.328 baseline; three take 143.718 versus 97.515. Explicit
four threads match the automatic effective setting; three new confirmation pairs
have medians 111.281 versus 108.469 seconds (candidate 2.592% slower). No candidate
meets the fixed 20% improvement gate; retain the unchanged automatic setting.

The observer captures process CPU/working sets and PDH paging/disk/clock counters,
but under-load gaps reach 94.133 seconds and one collection takes 92.063 seconds.
Protected process counters are unavailable. Do not treat naive per-phase CPU
residuals as measured competing load or infer a contention cause. On-battery charge
falls 67% to 18%; AC status stays zero, and battery/thermal effects are not isolated.
The required ten-service stack stays running; no duplicate candidate exists.
Strict first-step success does not establish full-turn/ten-dialogue/seven-snippet
acceptance or resolve application timeout enforcement. No prompt/default change
results; a future AC comparison or lower-overhead observer needs its own scope.
