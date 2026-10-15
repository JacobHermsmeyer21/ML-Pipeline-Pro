# CPU inference overran observed API timeout boundaries

October 14, 2026, source `3dd877b`: [post-reboot evidence](../evidence/2026-10-14-post-reboot-validation/README.md)
records the unchanged complete walkthrough against rebuilt local containers and
the explicitly warmed pinned 7B model. On this Ryzen 3/Vega 6 laptop, Ollama uses
CPU and reports 113.524 seconds of prompt evaluation plus 19.545 seconds generation.

The client times out waiting 90 seconds; the API eventually returns 504 after
140.929 seconds despite configured 20-second model/60-second turn deadlines.
The saved turn is interrupted with no tool reads; public history remains readable
and generation is not retried. All 63 local ordinary integration cases pass.

The elapsed overrun is measured, but its mechanism is unresolved. CPU/memory
pressure and synchronous setup/token counting are hypotheses, not established
causes. Do not describe this as proven timely timeout enforcement or as a new
fact-omission failure. Investigate scheduling, resource observations and the actual
blocking boundary before proposing a fix; changes to execution/concurrency require
review. Keep original deadlines and assertions. A faster earlier GPU run or cached
retry cannot substitute for acceptance on this laptop.

The [October 14 RX 9070 run](../evidence/2026-10-14-rx9070-walkthrough/README.md),
archived October 15, passes ten/seven original gates and the full walkthrough with
the same deadlines on a Ryzen 7 workstation. That is separate hardware/runtime
evidence; it does not diagnose or repair this CPU-laptop timeout-overrun mechanism.
