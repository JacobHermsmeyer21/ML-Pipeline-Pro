# OpenAI provider implementation and acceptance

October 20, 2026 (America/New_York). Implements the
[approved design](../../plans/2026-10-20-openai-agent-provider-plan.md). Runs used
Windows, Python 3.11.5, locked `langchain-core==1.6.9`, `langchain-openai==1.7.0`,
`openai==2.54.0`, and the serial classification worker in an isolated Docker stack.
Requested model: `gpt-5.4-mini`, Responses API, reasoning `none`, standard tier.
Retained provider metadata identifies `gpt-5.4-mini-2026-03-17` where captured.

Execution started from `1af066b` plus the implementation worktree. Raw reports
retain their revision/worktree flag and content hashes where available; they do
not claim that the implementation was already committed when executed. The
accompanying implementation commit and subsequent evidence commit retain the
final source. No local-model acceptance or deployed Kubernetes OpenAI rollout is
claimed by these hosted results.

## Results and limits

| Gate | Result | Raw evidence |
| --- | --- | --- |
| Final fast suite | 778 passed; 114 integration cases deselected; no selected-case skips. | `fast-reviewed.xml` in the archive. |
| Ordinary + worker integration | 104 passed; no selected-case skips. | `ordinary-fixed.xml`; both ordinary flags enabled. |
| Serial isolated recovery | Ten passed; no selected-case skips. | `recovery.xml`; separate recovery opt-in. |
| Original conversation semantics | Final rerun ten/ten; earlier nine/ten retained. | `live-conversation-01.json`, `live-conversation-02.json`. |
| Original Python-draft semantics | Seven/seven in both runs; no Python executed. | `live-snippets-01.json`, `live-snippets-02.json`. |
| Hosted monitoring semantics | Two/two normal/partial fixtures. | `live-monitoring-01.json`; these values are synthetic fixtures. |
| Real-ID HTTP walkthrough | Final pass: actual worker training and MongoDB persistence, saved/replayed draft, scoped reads, exact confirmation and monitoring. | `http-walkthrough-03.json`; earlier failed runs retained. |
| Static/packaging | Locked sync, Ruff lint/format, package compatibility (121 installed packages), wheel/sdist build, local links/examples, JSON and Compose configuration checks passed. | Commands below; archive manifests and source hashes. |

The real-ID walkthrough uses the application HTTP routes through ASGI transport,
real MongoDB at port 37017, Redis at 16379, and domain HTTP/worker at 18000 in
`mlpp-openai-validation-20261020`. It creates uniquely scoped classification
fixtures, reads a saved validation metric, proposes and confirms exactly bounded
training, then compares actual experiment IDs before proposing tuning. Tuning
is not dispatched by that suggestion; drafts never submit work or execute Python.
Saved turn, decision and history replay leave the reservation ledger unchanged.
Foreign conversation reads return 404. A separate monitoring app reads actual
stored observations and generates advice; the declared 150ms observations are
synthetic seeded telemetry, not measured inference latency. An empty version
returns 409 with no inference reservation. This is HTTP route/service acceptance,
not browser usefulness review, a new model benchmark or public deployment proof.

The test ledger reserves **$1.686037** across all live attempts, including failures
and reruns. This is the approved conservative estimate, not a provider-reconciled
bill. Counting is estimated at the full input rate using request bytes plus a
framing allowance; its dedicated tariff is unconfirmed. Admission stops at $1.90
under the unchanged $2 authorization. No additional paid runs are needed. Preserve
the local `artifacts/openai-provider/live-budget.json` across any later attempts;
the archived copy is evidence, not permission to reset the active ledger.

## Retained failures and corrections

- The first hosted conversation gate correctly fetched a foreign model as 404,
  but the model then classified the supplied ID as missing. The final-reply
  instructions now distinguish unavailable records from omitted inputs. The
  unchanged ten-case gate passes after this clarification; no host result repair
  or assertion relaxation was used.
- The first ordinary integration run passed 95 and failed nine diagnostic-store
  cases because their fixture inherited the new OpenAI default while selecting
  unbounded mode. Explicitly selecting Ollama preserves the local diagnostic
  requirement and produces 104 passes. The failing XML is retained.
- Walkthrough 01 checked a tuning limits object without its canonical
  `concurrency=1` default. Its corrected assertion checks the complete object,
  including serial execution. Walkthrough 02 incorrectly routed monitoring to
  the compatibility app, which has no monitoring routes. Walkthrough 03 uses the
  separate monitoring service factory. Those were harness defects; application
  route separation and persistence assertions were preserved.
- A preliminary three-domain smoke command targeted the compatibility stack and
  stopped at `/tuning/openapi.json` 404 before creating any fixture. It was not
  counted as a service failure or acceptance pass; the dedicated HTTP walkthrough
  exercises the actual supported topology.
- Package build warned that the uv cache directory might enter the source
  distribution. Archive inspection confirms cache/private `.env` exclusion and
  intentional public `.env.example` inclusion. Sandbox-denied package downloads
  were rerun with network access; final sync/build/checks pass.

## Independent review

Reviewer: separate same-model agent `/root/provider_review`; no different-vendor
review was available. Submitted scope: provider/client lifecycle, normalized
count/send requests, token/byte arithmetic, isolation, budget persistence/locking,
controlled runner, observer evidence and exact training confirmation in the real
HTTP walkthrough. Review was read-only and made no paid calls.

Confirmed findings and resolutions:

1. The installed SDK inherits `OPENAI_CUSTOM_HEADERS`, overriding explicit auth.
   Clear inherited custom headers and rebuild only approved wire headers, retaining
   HTTP Host/framing and LangChain's raw-response control. Actual SDK regressions
   cover this boundary.
2. Malformed envelope shapes such as null usage/output entries were reported as
   unavailable. Raw validation now returns the fixed invalid-response error.
3. Observer usage metadata could retain unknown nested secrets. Evidence now
   allowlists nonnegative integer token counters; the nested-secret regression
   passes through the actual SDK transport.
4. Counting pricing/framing was an unproved spending bound. Jacob explicitly
   approved conservative estimated reservations after reviewing that limitation;
   evidence makes no account-billing guarantee.

Final re-review identified no remaining concrete blocker in the submitted scope.
Self-review is not counted as independent review. Human usefulness review of the
new hosted guidance, Python drafts and diagnosis remains pending; the original
local-model human review does not transfer automatically. Review the saved sample
turns/code/advice in `http-walkthrough-03.json` before broader use.

## Reproduction and provenance

Offline commands are the repository fast gates plus `uv build`. Ordinary gates
follow [the isolated setup](../../guides/verification.md#repeat-the-full-suite)
with both ordinary/worker flags; recovery follows
[its serial setup](../../guides/verification.md#run-the-suite).
Package archives include the provider and exclude private configuration.

The hosted commands were `python -m evaluations.openai_runner --suite monitoring`,
`--suite conversation`, `--suite snippets`, and
`python -m evaluations.openai_http_walkthrough`, each behind
`MLPP_RUN_OPENAI_EVAL=1` and the same held ledger. Defaults preserve existing
20-second calls, 60-second turns and original suite budgets. No API key or paid
gate is placed in CI. Compose configuration was checked with `config --quiet`;
Kubernetes secret-reference JSON was parsed, without applying or publishing a
populated Secret.

[Raw evidence archive](raw.zip) contains sanitized JSON runs, JUnit reports,
the testing ledger snapshot and a SHA-256 manifest. Reports keep failures and
generated explanations separate from actual training/telemetry data. The live
runner now records separate successful counting/generation durations and returned
model identities; earlier files without that instrumentation retain that limit.
