# Two completed laptop diagnostics without AI waiting limits

Both original full walkthroughs pass on the CPU laptop with the approved
[unbounded diagnostic design](../../plans/2026-10-19-laptop-unbounded-diagnostic-plan.md).
They take **789.906 seconds (13m 10s)** and **641.016 seconds (10m 41s)** overall.
The slowest complete replies are **276.594** and **273.719 seconds**. Waiting
allows these comparison/proposal turns to finish beyond the old 270-second shared
turn deadline. Neither run needs more than the existing 300-second client ceiling.

These are successful **direct-AI, probe-free diagnostic workflows**. AI requests
use verified model/monitoring API pods; backend operations, tools, decisions and
history still use the gateway. Both result files explicitly record
`bounded_profile_acceptance: false`. Full finite gateway acceptance remains open.
The normal five-minute profile is restored after idle, with data preserved.

See [derived results](results.json), [unaltered execution payloads](raw.zip),
[payload hashes and byte counts](manifest.json), and [archive verification](verification.json).
Read the exact new model outputs in [run 1](review-run-1.md) and
[run 2](review-run-2.md). Their human quality review remains pending; generated
Python is never executed. Interpretations in model prose are separate from the
measured timings and saved backend facts.

## Timing observations

| Original walkthrough step | Run 1 seconds | Run 2 seconds |
| --- | ---: | ---: |
| Inspection with verified validation fact | 201.047 | 125.672 |
| Comparison and bounded tuning proposal | 276.594 | 273.719 |
| Exact saved proposal replay | 0.125 | 0.156 |
| Validated Python draft | 126.719 | 56.063 |
| Exact saved draft replay | 0.297 | 0.157 |
| Monitoring diagnosis | 161.766 | 164.500 |
| Total AI HTTP waiting, including replays | 766.548 | 620.267 |
| Complete original walkthrough command | 789.906 | 641.016 |

Command time also includes backend training/tuning/version smoke, confirmation,
bounded job polling and twenty measured workload inferences with five declared
artificial delays. It excludes setup, explicit model loading and evidence collection.
The first run starts after a cold model load with an empty prompt (17.188 seconds,
no generated text); the second reuses the resident runtime after observed idle.
Two fresh projects and output directories preserve distinct record identities.

All original assertions pass: actual-ID facts, comparison, exact two-trial/40-second
proposal, explicit confirmation and successful serial tuning, validated draft,
both equal replays and the monitoring `inspect_seeded_delay` check. No generated
code is repaired or executed. The original ten/seven gates remain unchanged and
reject this timing profile; their prior [accepted cohort](../2026-10-19-laptop-awake-gates/README.md)
is separate evidence.

## Source and execution provenance

Jacob approves the written design with "go for it" on October 19, 2026.
The live measurement starts on clean
`1152aa858eca169d49e1d5d003bab2229e4cddf9`, on the Acer Aspire A515-46 /
Ryzen 3 3350U, Python 3.11.17, Ollama 0.40.2 and installed
`mlpp-qwen2.5:7b-instruct-q4_K_M-json-tools-v1`, digest
`abadc4bf8517d77dcc8db312ca98cd7cb43488243048c41f1b5746e031427779`.
Context remains 8192 with four inference threads. Model, prompts, weights,
token/call limits, CPU execution, resources and replicas are unchanged.

Image `ml-pipeline-pro:unbounded-b303c90` is built from the approved implementation
worktree before its commit. Imported site-package hashes match the later live
source in all four API pods. The host Docker manifest/load identity is
`sha256:6e67bb4d78a07404ffeeed7fd4437a138b2d6ef50f9d43afb330bc937ea858e5`;
individual pod CRI identities are retained separately in the installation reports.
Verification command metadata honestly records the earlier dirty worktree on
approval commit `b303c90`; those tests are not described as clean-commit executions.

The measurement journal records source and executed-helper hashes before warmup,
no AI/process cutoff, no automatic retries, running/completed status, child exit,
idle observations, power and owned cleanup. Only a correct first run followed by
observed idle permits run two. Windows stays on AC in the retained samples;
a temporary thread-scoped wake request is used and released without changing power
policy. Runtime logs are exact byte windows from before warmup through completion.

The diagnostic profile removes startup/readiness/liveness probes only on gateway,
model API, tuning API and monitoring API. Null waits and the explicit diagnostic
flag apply to the AI-serving model/monitoring APIs. Installed-specification
comparison verifies these are the only changes from the normal laptop profile;
all replicas/resources and unrelated specifications match. Datastore, worker,
scheduler and monitoring-infrastructure policies remain unchanged.

The initial probe-free rollout reports success before a model API accepts HTTP,
so its first explicit readiness check fails with connection refused. That failure
is retained in `validation/diagnostic-deploy.log`. A later explicit HTTP check,
module/settings verification and preserved-record comparison pass before inference;
this is setup continuation, not a model-generation retry.

## Verification and saved ownership

| Check | Result |
| --- | --- |
| Locked sync, Ruff lint/format, dependencies, package build | Pass |
| Full fast suite | 661 passed, 83 integration deselected; 151.69 seconds; 80% rounded coverage |
| Focused checks | 203 passed, then 14 diagnostic cases; tool-output provenance only |
| Ordinary real-service integration | 73 passed; both opt-in flags; 95.90 seconds; no selected skips |
| Serial isolated recovery | 10 passed; separate opt-in; 370.64 seconds; no selected skips |
| [Implementation CI](https://github.com/JacobHermsmeyer21/ML-Pipeline-Pro/actions/runs/39338348885) | All five jobs pass |
| Both original full diagnostic walkthroughs | Pass; exit zero; idle after each |
| All eleven container identities/restart counts during measurement | Unchanged |
| Finite-profile restoration | Verified 240-second model / 270-second turn, diagnostic flag false, original probes |

Each project has three saved diagnostic turns and two conversation parents with
matching `diagnostic_unbounded` modes and null deadlines; neither parent retains
an active turn after completion. Parent-write ownership fencing is retained.
Real MongoDB tests exercise owner replacement after a valid snapshot for answers
and proposals, malformed mode/deadline pairs and preservation of legacy finite
deadlines. None timer propagation is checked at actual asyncio/SDK boundaries.
These tests do not replace the outstanding real under-load finite-expiry exercise.

The preserved pre-existing dataset/model/version/experiment records, artifact
hashes/sizes and replay identity match across deployment and restoration. Compatible
readers remain deployed. Own port-forwards close, the wake request releases, and
the original kind cluster/data volumes remain. Private kubeconfig/certificates,
credentials, environment dumps, model files and test database/cache dumps are
excluded from the public archive. Earlier raw archives remain unchanged.

## Interpretation and limits

Both comparison replies exceed 270 seconds; API completion logs independently
record 276.637 and 273.679 seconds. This supports reviewing the shared turn budget
before increasing the client ceiling beyond five minutes. A new finite budget and
routing/probe policy need their own reviewed change and real delivery test.
No further timeout, resource or model optimization is implemented here.

Infrastructure readiness failures still occur in MongoDB, Redis, Prometheus and
Grafana during run two. The absence of a restart does not prove those stalls or a
resource cause fixed. Lightweight host counters do not establish worker/VM CPU,
paging or OOM attribution. Two observations do not establish a latency distribution
or an upper bound. Monitoring prose about "normal operation" or possible masking
of issues is a generated interpretation, not a measured conclusion.

Separate `timing_review` agent review checks nullable ownership, real transaction
interleavings, timer propagation, capture cleanup/journaling and both saved-run
timelines/semantics. Findings and resolutions are retained in `validation/review.json`.
This is same-vendor, read-only review; another vendor and independent runtime
reproduction are unavailable. Human review of these new outputs, finite gateway
acceptance, real finite-expiry evidence and resource attribution remain open.
