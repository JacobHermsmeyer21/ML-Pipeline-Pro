# Full AI walkthrough on the RX 9070 workstation

Executed October 14, 2026, on clean revision
`add6862dad3e0a3e15747896126191dd13529ac5`; archived October 15 after Jacob's
restart. This is a new run on the Ryzen 7 7800X3D / Radeon RX 9070 workstation,
with about 31.1 GiB host RAM. The earlier Ryzen 3 CPU-laptop failures remain
separate evidence and are not resolved by this workstation result.

## Environment and scope

Started the installed Docker Desktop/Linux engine and Ollama 0.40.2 explicitly,
then built all ten services from the current checkout in the isolated Compose
project `mlpp-rx9070-walkthrough-20261014`. Used the base, domain-service,
monitoring and AI overlays with fresh project volumes. The running API's
inspection-guard module hash matches the source. Python is 3.11.5; repository-local
uv 0.12.23 synchronized the locked training environment.

The installed model is `mlpp-qwen2.5:7b-instruct-q4_K_M-json-tools-v1`, digest
`abadc4bf8517d77dcc8db312ca98cd7cb43488243048c41f1b5746e031427779`.
The pinned tokenizer checksum matches. Ollama's compute log identifies the RX 9070
through Vulkan; its loaded-model response records 5,119,263,374 bytes resident in
VRAM and context 8,192. Explicit empty-prompt warmup loads the existing artifact;
no weights were downloaded and no generated text was used to warm the requests.

Application model/turn limits remain 20/60 seconds, with five model calls per
turn. The API uses the existing 1,024-output-token setting. The dialogue gate
retains its 512-output-token, 50-request and 600-second suite budgets; snippets
retain seven generation calls, 1,024 output tokens and a 120-second suite budget.
No source, assertion, deadline or model output was changed to obtain these results.

## Measured results

| Check | Saved result |
| --- | --- |
| Original real-model dialogue gate | All ten scenarios pass; one aggregate pytest case passes in 11.93 seconds |
| Original real-model snippet gate | All seven scenarios pass; one aggregate pytest case passes in 14.83 seconds |
| Complete actual-ID AI walkthrough | Exit 0 in 20.3547332 seconds, excluding startup, build, warmup and preceding gates |
| Backend | Training and three-trial tuning succeed; version registration, artifact verification, submission replay/conflict and project checks pass |
| Inspection | Completed reply returns the requested `metrics.validation_f1` fact, grounded as 1.0 in the actual training record |
| History-guided proposal | Comparison succeeds; proposal uses the actual dataset/model, validation objective, ten seconds per trial, two trials and 40 seconds total |
| Explicit bounded demo decision | Exact proposal approved by the requested full-walkthrough flag; confirmed serial tuning succeeds |
| Proposal and draft replay | Saved responses compare equal; a validated Python draft requires human review |
| Measured monitoring producer | 20 one-thread CPU classifier inferences, warmup excluded, five declared 150 ms delays; checkpoint hash/size and sample replay verified |
| Local-model monitoring diagnosis | Returns current observation citations and `inspect_seeded_delay`, `profile_inference`, `check_resources`; no automatic changes |
| Visualization | Saved Prometheus query returns issue value 1 and the alert rule is firing; Grafana serves `mlpp-midterm` with 15-second refresh |

The backend smoke also saves one explicitly synthetic seeded telemetry sample.
Consequently the diagnosis window contains **21 observations and six seeded
samples**, including the 20 actual inferences and five injected delays above.
Its measured maximum is 151.1261000050581 ms and mean is 43.18649047622568 ms.
The generated explanation's counts/citations match that mixed window; its prose
remains interpretation. This run checks visibility, not scrape-delay guarantees
or generalization/performance on real production data.

The [saved generated draft](generated-draft.txt) lists experiments using environment
configuration and never executes during the walkthrough. Human usefulness review
of this run's new output is not claimed. Validation and source checks are performed
by the implementing assistant; separate boundary review remains outstanding.

## Retained evidence and limits

[Results and provenance](results.json) identify source/model/image hashes and
asserted outcomes. The [raw archive](raw.zip) contains both original gate reports,
JUnit/logs, the complete walkthrough's backend/results/workload files, startup and
warmup output, public model/service provenance, dashboard/query/rule responses,
selected compute log lines and the exact generated draft. It excludes weights,
installers, runtime environment dumps and private MongoDB snapshots.

Before archiving, all 51 recorded application/example/evaluation/tokenizer/lockfile
hashes still match. The interrupted turn did not abort the run: its saved exit
code is zero and its completed results include diagnosis and both replay checks.
No acceptance rerun or extra inference was needed after the user's restart.

This demonstrates the requested-fact correction against a fresh actual record
through rebuilt services and completes the local tutorial on this workstation.
It does not replay the original failed record, resolve CPU-laptop timeout
enforcement, constitute independent review, or establish universal reliability.
The full ordinary/recovery suites and Kubernetes deployment were not rerun for
this execution; their prior evidence retains its source identity. The immediately
preceding [reconciliation](../2026-10-14-branch-sync/README.md) passed 598 fast cases;
the tested `add6862` source also has [successful remote CI](https://github.com/JacobHermsmeyer21/ML-Pipeline-Pro/actions/runs/38665644851),
checked October 15. This follow-up changes documentation/evidence only. Documentation links, saved
Python syntax, result consistency, archive integrity and whitespace are checked
before commit. Push and remote CI state are reported in the task handoff.
