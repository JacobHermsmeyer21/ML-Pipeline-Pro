# Laptop Qwen prompt processing dominates the first read

October 18, 2026, baseline `91b0aef`: [offline investigation](../evidence/2026-10-18-qwen-cost-investigation/README.md)
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
alone has no demonstrated path to the unchanged 20-second limit.

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
