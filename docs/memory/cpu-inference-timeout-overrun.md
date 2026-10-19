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

October 18 follow-up: the [approved direct diagnostic](../evidence/2026-10-18-laptop-qwen-diagnostic/README.md)
on clean `0f6ed20` receives the correct first `get_experiment(exp-low)` step in
99.359 seconds, after 24.281 seconds separate warmup. Prompt processing takes
88.330474 seconds for 1,109 uncached tokens; generation takes 10.946295 seconds
for 18 tokens. CPU residency is confirmed. This proves eventual first-step
response within the diagnostic's eight-minute budget, not a complete turn or
application-gate pass; the 20-second call limit is unchanged.

Eight raw Windows API snapshots show approximately 99.99% system CPU busy and
3.64-3.86 GiB available physical memory. Intended five-second sampling produces
actual gaps up to 32.219 seconds. Scheduling delay and blocking inspection remain
hypotheses; no cause is confirmed. Memory/commit availability does not measure
disk paging. Live deadline expiry was not triggered, so these data do not close
the API timeout-overrun or under-load cancellation gaps. Test one separately
reviewed inference/workload change at a time after reviewing this baseline.

The [same-day offline cost audit](qwen-prompt-processing-cost.md) reproduces the
1,109-token input and quantifies prompt contributors. It finds no process-level
evidence to attribute contention and reports no measured inference improvement.
Its new trial plan awaits review and actual laptop access; the current session
is verified as the RX 9070 workstation.

October 19 [laptop profiling/thread trials](../evidence/2026-10-19-laptop-cpu-trials/README.md)
complete twelve correct uncached first steps, with no retained latency improvement.
The observer now records per-process CPU but suffers gaps up to 94.133 seconds and
missing protected-process access. These observations do not resolve the sampling
delay or API timeout-overrun mechanism. This actual-laptop run supersedes the
preceding session's workstation/access limitation only; application acceptance and
the separate deployment timing design remain outstanding.

October 19 [plugged-in complete-workflow rehearsal](../evidence/2026-10-19-laptop-rehearsal/README.md)
uses the unchanged application through its existing Compose gateway on clean
`e605e24`. With AC connected, the first inspection still returns 504 after
87.885 seconds and saves an interrupted turn with no tool reads. Independent
diagnosis returns 503 / `chat_timeout` after 30.188 seconds; a Python draft times
out at its 90-second client, with an eventual 409 after 92.736 seconds and no
saved snippet. Cancellation and a final idle runner are retained in filtered
logs. These show the failure also occurs while plugged in; they do not isolate
power effects or establish the blocking/timeout-overrun mechanism. Backend,
measured inference/observation replay and dashboard/alert checks pass separately.
The five-minute profile remains unimplemented; full laptop acceptance remains open.
