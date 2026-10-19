# Attribute and reduce laptop Qwen inference cost

- Status: approved for laptop resource profiling and request-local thread trials; implementation in progress
- Date: 2026-10-18
- Source baseline: `9e2dcaf` / `person-a/conversation-foundation` (application unchanged from `91b0aef`)
- Request: investigate CPU contention and prompt-processing cost and make the demo faster.
- Human reviewer/approval: Jacob, October 18, 2026: "run the laptop profiling and thread tirals test" approves steps 2-3 below.
- Independent review: not yet obtained; seek separate review of sampling, deadlines, rate arithmetic and any inference configuration before live trials.

## Proposed behavior and purpose

Identify where the presentation laptop spends inference time, then compare the
smallest reversible changes against the original workload. Retain semantic
checks, context/output capacity and application deadlines. A faster diagnostic
is useful evidence; usable demo latency still requires the original application
gates and a complete turn/tutorial on the actual laptop.

## Clarification and critique

The [single laptop diagnostic](../evidence/2026-10-18-laptop-qwen-diagnostic/README.md)
measured 88.330474 seconds processing 1,109 uncached prompt tokens and 10.946295
seconds generating 18 output tokens. Approximately 100% system CPU busy does not
attribute that work to Ollama or prove competing processes caused the delay.
Five HTTP-server threads in its log do not establish inference thread count.
Physical memory availability does not rule out paging.

This session is on the Ryzen 7 7800X3D / RX 9070 workstation, verified by actual
machine metadata. There is no established remote access to the Acer laptop. Do
offline request/token analysis here; stop live laptop trials if identity differs.
Do not substitute workstation timing for laptop acceptance. The existing
one-machine laptop arrangement remains the target; switching it requires review.

Before changing prompts, count the actual rendered input and isolate CPU users.
Preloading already removed loading from the measured inference almost entirely.
Output caps do not shorten an answer that stops after 18 tokens. Smaller context
capacity does not itself remove the 1,109 actual input tokens. Cached repetitions
can look fast without helping a new conversation. Prompt specialization for just
the first read can also destroy prefix reuse on the subsequent answer. Prefer a
stable compact policy across both inspection steps if compression is needed.

The parallel [deployment plan](2026-10-18-laptop-deployment-readiness-plan.md)
records Jacob's selected **300-second complete-reply target**, with correctness
taking priority. Its concrete timing-profile design still awaits review. The
existing 20-second call / 60-second turn settings are unchanged defaults, not a
new requirement to reject the five-minute target. This investigation complements
that deployment work. Final demo acceptance must use its approved named timing
profile and complete-reply criterion; the threshold below only identifies an
incremental optimization worth retaining.

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | Preserve original strict `get_experiment(exp-low)` first-step semantics and original dialogue/snippet requirements. | Unrepaired responses; original ten/seven gates and actual-ID tutorial before demo-ready claims |
| F2 | Functional | Attribute system CPU use rather than equating saturation with contention. | Timestamped runner and other-process CPU deltas, missing-access fields, system totals and observer overhead |
| N1 | Performance | Compare equivalent uncached requests on the same laptop; retain a candidate only with at least 20% lower median wall time and no semantic failures across three baseline/candidate pairs. | Individual observations, median/range, prompt/generation/load timings and cache counts; no significance claim from three pairs |
| N2 | Resources | Keep one inference at a time, context 8192, output cap 1024, unchanged artifact/runtime and 480-second diagnostic deadline; separate warmup at most 120 seconds. | Exact requests, model/residency identity, runner options, explicit failure and stop on timeout |
| N3 | Provenance | Separate offline measurements, estimates, live diagnostics and application acceptance. | Hashed scripts/inputs/results, revision/machine/packages, raw observations and stated gaps |

## Constraints and scope

No model pulls, runtime upgrades, paid APIs, weight changes, training-worker
concurrency changes, production deadline changes, public schema changes or tool
dispatch from diagnostic trials. Preserve token admission, strict validation,
permissions, evidence, idempotency, persistence and all original assertions.
Required separate course services remain part of the final demo. Do not stop
user applications, security software, arbitrary processes or queued work.

## Design

1. **Read-only investigation (current request).** Recompute the retained baseline,
   verify its exact 1,109-token count using the pinned local tokenizer and renderer,
   and count policy, tool catalog, host guidance, history marker and user input.
   Measure offline rendering/counting on the workstation separately from inference:
   three preparation observations, three unreported loop warmups and 30 saved
   count/render observations. Compare token counts after removing catalog/host
   text only as diagnostic ablations, never deploy those incomplete prompts.
   Save raw runs and derive constant-throughput estimates explicitly as estimates.
   Acceptance: original hashes/count agree, all 30 counts equal 1,109, no network
   requests or mutations. Keep total offline analysis under two minutes.
2. **Resource attribution (after review, actual laptop).** Extend the opt-in
   diagnostic observer with timestamped per-process cumulative CPU, working set,
   system CPU/memory, effective inference thread/batch flags, AC/power state,
   available clock/paging/disk counters and actual sample gaps/duration. Use a
   separate observer process with bounded queries and a two-second target cadence;
   record access failures and late samples. Save names/PIDs/counters and allowlisted
   runner flags, never full command lines/environments. Record idle, warmup and
   inference separately. Bound observer lifetime and stop it in cleanup.
3. **One-factor trials.** Start with unchanged runtime/workload and the required
   demo services. If attribution identifies a duplicate repository demo stack,
   first verify no active/queued work, record its exact running services and compare
   with only that duplicate stack stopped; restore its prior state in cleanup.
   Required services stay running. If no duplicate exists, omit this candidate
   explicitly. Next screen request-only `num_thread=2`, `3`, `4`, preserving
   observed automatic batch/context settings. No affinity, priority or power-plan
   changes. Verify the effective runner flags; unsupported/ignored settings are
   failed trials. Screen each candidate once against a fresh unchanged baseline;
   choose at most one for three paired baseline/candidate repetitions. Screen
   results alone are not a performance claim. Do not combine winning factors yet.
4. **Prompt follow-up, outside this experiment's approval.** If CPU trials do not
   suffice, propose a compact shared guided policy/catalog using the offline
   counts. Preserve all current messages, schema selection, host guards and
   requirements: current-request precedence, untrusted history, missing inputs,
   per-trial/total budgets, validation selection, citations/requested facts,
   refusal and separate human action/code review. Review an exact candidate and
   its requirement mapping before testing it. Compare complete two-step cost as
   well as first-read cost, keeping policy prefixes stable and recording cache
   reuse. Prompt/configuration deployment needs a concrete updated plan and
   renewed review; this plan authorizes no production instruction change.

For uncached trials, finish/confirm runner idle, unload only the diagnostic model
and verify it is absent, then warm the same artifact/options before each request.
Require zero cached tokens in the response/log; otherwise mark the comparison
ineligible and keep the observation. Count at most 16 measured requests across
screening and confirmation, and at most 60 minutes total including setup/warmup.
Enforce the total wall deadline across setup, observation and cleanup as well.
Before starting a trial, reserve its 600-second warmup/inference allowance plus
60 seconds for metadata/cleanup from that budget. Stop rather than exceed either
budget. Stop on timeout, invalid
semantics, model mismatch, unknown residual runner activity or cleanup failure;
retain the failure and do not automatically retry. This phase may finish with no
safe winner; record that outcome.

## Acceptance and verification

The baseline remains the synthetic original `read_guidance` fixture, not a
shorter substitute task. Compare the same machine, power state, required service
load, artifact, schema, output/context capacity and cache condition. Log warmup
separately. Preserve timeout failures and exclude them from successful latency
medians without hiding their count. Estimates assuming proportional token cost
are neither measurements nor acceptance results.

Before live trials, deterministic checks must exercise observer cleanup and late
sampling, missing process access, request option allowlists, identical noncandidate
payloads, zero-cache eligibility, unchanged semantic validation, one request/no
retry and exhausted run budgets. Run locked sync, Ruff lint/format, all fast tests
with coverage and `uv pip check` under [repository rules](../../AGENTS.md).
Sampling/rate/deadline changes require separate review; disclose if unavailable.
Service/persistence/worker logic is excluded; select affected real-service gates
if implementation reaches those paths. Run the unchanged original ten dialogue,
seven snippet and actual-ID tutorial gates only after choosing a final arrangement
and separately budgeting that acceptance run.

## Risks and rollback

The CPU laptop may not meet application deadlines even after meaningful savings.
Sampling can itself compete for CPU; disclose overhead, missing data and gaps.
Changing thread count can slow generation or alter exact output. Compression can
lose semantics or prefix reuse. Reset diagnostic request options and restore any
recorded duplicate-stack running state after trials. Leave application defaults,
weights, stored records and artifacts intact. If no candidate passes, report the
hardware/latency limit and request a separately reviewed demo arrangement.

## Human review and approval

Jacob approved steps 2-3 on October 18, 2026 with "run the laptop profiling and
thread tirals test". Scope is the bounded observer and request-local 2/3/4-thread
experiments described above, with unchanged application settings and prompts.
Step 4 and the separate deployment timing-profile plan remain outside this
approval. No production change is authorized by an experimental speedup alone.

The new session verifies the actual Acer Aspire A515-46 / Ryzen 3 3350U, four
cores/logical processors and 19,261,304,832 bytes RAM using local CIM. The earlier
workstation observation above is historical. Ollama reports 0.40.2; one existing
ten-service repository Compose stack is running, with no duplicate stack found.
Keep that stack running. Independent review is unavailable in this session;
record self-review and deterministic checks without calling them independent.

## Implementation outcome

Only step 1 is complete. [Retained analysis, source and raw observations](../evidence/2026-10-18-qwen-cost-investigation/README.md)
on `9e2dcaf` reproduce 1,109 tokens in all 30 offline observations. Catalog and
host-policy removal leaves 571 tokens; at unchanged laptop rates that projects
56.51 seconds, not a measured speedup. The verified current machine is the
Ryzen 7/RX 9070 workstation; no live inference or laptop CPU attribution ran.

Locked offline sync passes (114 resolved / 109 installed), Ruff lint and format
pass (186 files), all 611 fast tests pass (73 integration deselected, 44.93 seconds,
80% rounded coverage, no selected skips/warnings), and dependency compatibility
passes. Local links/anchors, the new PowerShell example, raw hashes/script syntax
and whitespace are validated before commit. Existing tests and assertions are
unchanged. No service, package or ownership behavior changed; ordinary/recovery
and original model acceptance gates were not selected. Source and arithmetic
were self-reviewed; independent review is outstanding. No implementation of
steps 2-3 and no production configuration/prompt change occurred.

The [durable finding](../memory/qwen-prompt-processing-cost.md) records token-cost
limits and missing process attribution. This plan and evidence are committed and
pushed together under the repository workflow; the final handoff supplies the
commit/push result. Human approval and actual laptop access remain required for
the live phase; none of its acceptance criteria are marked passed.

Incoming-change reconciliation: `9e2dcaf` added only the separate deployment plan
while this investigation was in progress. It is preserved in this branch's
history. Raw analysis correctly records that execution revision; the initial
summary's `91b0aef` label was the earlier application baseline and is corrected
here. Review of the incoming plan aligns final acceptance with the selected
five-minute reply target, without authorizing either pending implementation.
