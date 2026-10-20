# Independent local-model review

October 20, 2026: separate local Qwen 2.5 14B Instruct Q4_K_M on Ollama 0.40.2
reviewed the complete alias registry, lifecycle admission and ownership helper,
plus all application diffs. The prompt specifically requested dataset request
hashes, canonical relationships, exact-action dispatch, deletion receipt replay
and column replay after parent deletion. Exact submitted scope, model identity,
options and unmodified response are retained under `review/` in `raw.zip`.

The reviewer did not execute tests and made several assertions unsupported by
the supplied source. These are recorded rather than presented as verified bugs
or a passing independent acceptance gate. Resolutions below are the implementing
assistant's source review supported by saved executions.

| Finding | Resolution |
| --- | --- |
| Simultaneous increments may allocate duplicate aliases | The counter uses MongoDB atomic `find_one_and_update` with `$inc` inside the publication transaction, plus unique mapping indexes. Twelve concurrent dataset inserts allocate twelve distinct dN values; injected write-conflict retry leaves one mapping and counter value one. No new lock is needed for this alleged race. |
| Interrupted migration may exhaust the counter; reset/extend it | Counter and mapping checkpoint commit together; interruption does not burn an uncommitted allocation. Existing exhaustion/final-slot tests and resumable migration pass. Resetting counters would violate permanent nonreuse and is rejected. |
| Deletion preview cannot replay an erased receipt | Preview and execution are different operations. `delete` checks its scoped key receipt and original path hash before resolving the target; repeated DELETE by d1 returns the same completion after erasure. The real deletion test confirms this boundary and rejects changing to UUID under the same key. A new preview of an erased record correctly returns missing. |
| Column preview cannot replay a save after parent deletion | `matching_selection` resolves d1 through the permanent registry and checks the saved child before loading the parent. The real-service test deletes the parent then replays POST columns with the same body, obtaining the identical child. A new preview still requires its source. |
| Lifecycle insertion can use stale frontend evidence | Canonical reference validation and record insertion still share the lifecycle gate transaction. Browser API generation fencing remains intact. Full deletion/ownership/recovery gates and canonical fact/action checks cover their declared cases; no stale-evidence defect was established by this generic finding. |

Review limits: this single local model's findings contain mistakes and do not
prove comprehensive independent correctness. The preserved source/tests provide
the stated evidence. Human usefulness acceptance of the finished feature remains
separate from this review.
