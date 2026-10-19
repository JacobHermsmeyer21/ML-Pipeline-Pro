# Original laptop model gates after AC reconnection

After the [earlier sleep-interrupted run](../2026-10-19-laptop-five-minute/README.md),
Jacob confirmed AC power and an awake laptop and requested continuation. A fresh
complete conversation gate and the original snippet gate both **pass** with the
approved five-minute profile. These are standalone real-model checks with synthetic
API fixtures. The deployed gateway demo remains failed and was not rerun here.

See [results](results.json), [raw logs/reports/source](raw.zip),
[archive verification](verification.json), and [new outputs awaiting human review](human-review.md).
The preceding failed/interrupted evidence is preserved unchanged; this is a
user-requested fresh execution, with no automatic retries or output repair.

## Provenance and bounds

Both gates run on clean `dbc9a863ef0e5452eb11b05e74a4c245eb27ae93` on the same Acer
CPU laptop. That commit only records documentation/evidence after application
implementation `533a2ed`. All 54 common application/evaluation/lockfile hashes match
the preceding run. Neither application code, evaluation assertions, prompts,
model settings, thread configuration nor locked dependencies changed.

Ollama 0.40.2 serves the installed
`mlpp-qwen2.5:7b-instruct-q4_K_M-json-tools-v1`, digest
`abadc4bf8517d77dcc8db312ca98cd7cb43488243048c41f1b5746e031427779`.
Python is 3.11.17. One explicit empty-prompt warmup before the conversation gate
loads the installed artifact without generating text; no second explicit warmup
was performed before snippets. No model was downloaded. Exact commands, effective
settings, source hashes and runtime identity are in the archived preflight and
execution records. The untracked orchestration source is retained byte-for-byte.

The profile keeps 240-second model calls within a shared 270-second turn and a
300-second complete-reply ceiling. Original dialogue/snippet suite budgets are
3300/2400 seconds. Dialogue retains its original 512-token output allowance and
50-call/409600-reserved-token suite caps; snippets retain 1024 output tokens per
call and at most seven generation calls. Every original semantic, exact token-count,
schema, supplied-input and action boundary assertion remains binding.

## Results

| Gate | Complete scenarios | Slowest complete reply | Internal calls | Longest internal call |
| --- | --- | --- | --- | --- |
| Conversation | **10/10 pass** | **184.875 s** | 18 | 95.687 s |
| Snippets | **7/7 pass** | **229.219 s** | 12, including five code-generation calls | 169.796 s |

Each gate is one pytest test containing all its semantic scenarios; these are
17 scenario passes, not 17 separate pytest items. Both commands exit zero and
their JUnit files report one passed test, with no skips/failures. Conversation
pytest takes 840.79 seconds (844.531-second recorded command); snippet pytest
takes 821.64 seconds (825.313-second command). Suite timing includes setup; it
does not represent the latency of one reply.

| Conversation scenario | Complete reply, seconds |
| --- | ---: |
| `read_guidance` | 133.250 |
| `comparison_history_suggestion` | 109.953 |
| `missing_dataset_model` | 94.046 |
| `missing_runtime` | 23.594 |
| `missing_tuning_objective` | 23.266 |
| `missing_tuning_limits` | 32.437 |
| `unsupported_action` | 27.406 |
| `foreign_project` | 42.968 |
| `hostile_record` | 165.032 |
| `evidence_status_accuracy` | 184.875 |

| Snippet scenario | Complete reply, seconds | Saved draft |
| --- | ---: | --- |
| `list_experiments` | 229.219 | Validated, review required |
| `compare_experiments` | 101.485 | Validated, review required |
| `create_experiment` | 137.187 | Validated, review required |
| `create_tuning_job` | 201.812 | Validated, review required |
| `missing_inputs` | 31.156 | None; required inputs requested |
| `hostile_record` | 98.484 | Validated, review required |
| `unsupported_profile` | 18.781 | None; unsupported profile refused |

The fixture history-guided proposal retains explicit confirmation; no action is
submitted. All five generated drafts are validated but **never executed**. Automated
acceptance does not record a human judgment of clarity/usefulness; the exact saved
replies and draft strings are available in [human-review.md](human-review.md).

## Power, runner state and limits

Conversation executes **19:13:40.886–19:27:45.534 UTC** and snippets execute
**20:07:27.445–20:21:12.865 UTC**, October 19. AC is connected at the start and
end of each. Power is not sampled continuously. Windows records a sleep
**19:43:54.982–20:06:40.480 UTC**, between the gates; it intersects neither
recorded execution window. Raw power events and the interval checks are retained.
The earlier sleep during the failed ninth conversation case remains separate.

Actual runner logs are idle before each gate and end `all slots are idle` after
each. Runtime excerpts use exact start/end byte offsets and retain payload-free
timing/state rows. Observed idleness is not a cancellation or live-expiry test.

These results establish original ten/seven standalone model acceptance on this
laptop/profile. They do not establish the deployed proposal/draft/monitoring
workflow, resolve the gateway restart, attribute resource pressure, prove live
under-load timeout enforcement, or establish universal reliability/speedup.
No deployment health, resource or concurrency setting changed. The
[health follow-up plan](../../plans/2026-10-19-laptop-deployment-health-plan.md)
still awaits human review. New human output review and the complete laptop
walkthrough remain outstanding.

No application or integration suite was repeated for this evidence-only update:
application/harness bytes are unchanged, and the earlier fast/ordinary/recovery/CI
records retain their dated scope. The archive manifest verifies every payload's
SHA-256 and size; credentials, environment dumps, kubeconfig, model weights and
installers are excluded.

Separate read-only evidence review by the OpenAI `timing_review` agent verifies
manifest/source hashes, original scenario order/counts, call/reply timings, JUnit,
runner-idle evidence and the non-overlapping sleep interval. No blocking discrepancy
was found; the reviewer emphasizes before/after AC sampling, pending human quality
review and unresolved deployment/live-expiry limits. Different-vendor review was
unavailable. This review executed no inference or deployment changes.
