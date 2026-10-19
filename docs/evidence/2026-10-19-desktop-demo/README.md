# October 19 desktop demo

Jacob requested a demo on this computer. The complete workflow passes on the
Ryzen 7 7800X3D / Radeon RX 9070 workstation at clean application revision
`bf07213ed2564cfc9c97efb35504c22f2d9cf9c7`. This is separate from the CPU-laptop
deployment failures; it does not close their acceptance gaps.

Started the installed Docker Desktop and Ollama 0.40.2, then rebuilt the existing
`mlpp-rx9070-walkthrough-20261014` Compose project with the base, domain,
monitoring and AI files. Existing volumes/records are preserved. Docker also
auto-started the old `mlpp-delivery-20261013-control-plane` node; it was stopped
without deletion before the demo to avoid duplicate application stacks.

The installed pinned 7B profile has digest
`abadc4bf8517d77dcc8db312ca98cd7cb43488243048c41f1b5746e031427779`.
Runtime logs identify Vulkan inference on the RX 9070. Warmup uses an empty
prompt and existing weights. No model download, source change, timeout change,
application assertion change, repaired model output or generated-code execution was used.
All 46 installed application module hashes match the checkout in each domain API.
Application call/turn budgets remain 20/60 seconds; the walkthrough uses its
original 90-second client wait.

| Check | Recorded result |
| --- | --- |
| Locked sync, lint, formatting, dependencies | Pass; 204 files already formatted, 109 installed packages compatible |
| Package build | Wheel and source distribution pass; neither contains the workspace uv cache |
| Fast tests | 647 passed, 73 integration deselected; 81% rounded coverage, 59.48 seconds |
| Local-model dialogue gate | All ten scenarios pass; aggregate pytest case 11.94 seconds |
| Local-model snippet gate | All seven scenarios pass; aggregate pytest case 14.70 seconds |
| Complete actual-ID walkthrough | Exit 0 in 21.953 seconds, excluding startup/build/warmup and gates |
| Training and tuning | Classifier succeeds, validation F1 1.0 on the small fixture; three initial tuning trials and two explicitly confirmed follow-up trials succeed |
| AI and history | Actual validation-fact inspection, comparison/history-guided bounded proposal, exact demo confirmation, saved history and identical proposal replay pass |
| Python draft | Restricted syntax/API validation and identical saved replay pass; human review required |
| Monitoring | 20 actual CPU inferences, five declared 150 ms delays, artifact hash/size and sample replay checks pass; cited local-model diagnosis returns `inspect_seeded_delay` |
| Visualization | Version-specific Prometheus issue value 1, matching alert firing, Grafana dashboard HTTP 200 with 15-second refresh |
| Final state | Ten containers running, all six configured healthchecks healthy, zero restart counts; model log ends idle |

The backend smoke also creates one explicitly synthetic 150 ms routing sample.
Diagnosis therefore sees 21 observations and six seeded samples. Its mean is
43.2428 ms and maximum 151.1272 ms. These are fixture observations with declared
delays, not production-performance or generalization measurements. The generated
diagnosis remains interpretation; in particular its suggestion of underlying
performance degradation is not an established cause.

The API docs and Grafana dashboard were opened in the browser. HTTP responses
and dashboard configuration were checked; no visual browser review is claimed.
Services and existing records remain available after this run.

## Reproduce and inspect

With the documented stack/runtime started and warmed, use the original commands
in the [guided acceptance guide](../../guides/guided-midterm-demo.md#reproduce-acceptance),
then run:

```powershell
& .venv/Scripts/python.exe examples/warm_local_model.py `
    --model 'mlpp-qwen2.5:7b-instruct-q4_K_M-json-tools-v1'
& .venv/Scripts/python.exe examples/midterm_walkthrough.py `
    --confirm-demo-proposal --output artifacts/desktop-demo-20261019/walkthrough
```

Use a fresh output directory for another execution. The confirmation flag
authorizes only this script's bounded proposal. Generated Python remains a draft.

[Results and provenance](results.json) summarize the saved assertions and timing.
The [raw archive](raw.zip) retains original gate reports/JUnit/logs, complete
backend/dialogue/workload results, source hashes, safe deployed settings, image
identity, hardware, runtime compute/idle lines and dashboard/metrics responses.
Its SHA-256 manifest validates every payload. It excludes weights, installers,
credentials, environment dumps, database snapshots and pytest temporary files.
The untracked capture runner is retained as execution provenance; the existing
application, gate and walkthrough scripts were unmodified.

The [draft](generated-draft.txt) and [dialogue/diagnosis examples](human-review.md)
are available for human review. No new human usefulness approval is claimed.
The full ordinary integration/recovery suites, Kubernetes deployment and remote
CI were not rerun for this demo. Earlier evidence retains its own scope/revision.

## Capture and verification limits

Initial sandbox checks could not access Git fetch state, Docker's user config,
hardware WMI or uv's default cache. Authorized execution used the existing tools
and a workspace uv cache. uv reported a cache-in-source warning and a transient
rename retry; the build succeeds and archive inspection confirms no cache entries.
PowerShell displays native stderr as error records even for successful uv exits;
the command exit codes and retained test reports establish the results above.

Two post-demo capture errors were corrected against source: the first query
used a nonexistent metric name, and the collector incorrectly assumed that every
container defines a healthcheck. The source-defined `mlpp_workload_latency_issue`
returns 1; all ten containers run and all six configured healthchecks pass. These
were collector errors, with no product change, inference rerun or changed test.
The raw snapshots and corrected verification record preserve the distinction.

[Documentation verification](verification.json) checks local links/anchors, JSON, archive hashes/CRC,
source hashes, the generated draft's identity, saved factual assertions, command
syntax and whitespace. Review is self-review; no independent review is claimed.
Commit/push outcome is reported in the session handoff.
