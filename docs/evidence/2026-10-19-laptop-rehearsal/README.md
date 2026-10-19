# Plugged-in laptop demo rehearsal

Jacob requested the complete workflow rehearsal on October 19, 2026. It ran on
the Acer Aspire A515-46 / Ryzen 3 3350U presentation laptop, connected to AC power
throughout. **The complete AI walkthrough fails.** Backend and independent
measured-monitoring steps pass; they do not establish full laptop readiness.

Execution uses clean revision `e605e24` on `person-a/conversation-foundation`.
The existing `mlpp-post-reboot-validation` Compose project has ten running
services. All installed application-module hashes in the model, tuning and
monitoring APIs match the checkout. No rebuild, duplicate stack, model download,
application/configuration change, timeout increase, assertion change or repaired
model output was used. The separate [five-minute design](../../plans/2026-10-18-laptop-deployment-readiness-plan.md)
remains awaiting review and implementation.

## Measured outcome

| Step | Result |
| --- | --- |
| Prerequisites | API ready; MongoDB/Redis up; Grafana and Prometheus reachable; AC connected |
| Explicit installed-model load | Pass, 16.375 seconds including helper startup; empty prompt, no generated text |
| Real backend workflow | Pass: dataset/model registration, training, three-trial tuning, version registration, ten submission replays, changed-payload 409 and foreign-project rejection |
| First AI inspection | Fails: API HTTP 504 after 87.88469 seconds; complete walkthrough exits 1 after 90.454 seconds including preceding backend work |
| Saved inspection | Public history returns the interrupted turn, `chat_interrupted`, no tool results, facts or pending action |
| Independent monitoring workload | Pass in 11.359 seconds including process startup: 20 CPU inferences, five declared 150 ms delays, checkpoint hash/size verification and identical observation replay |
| Independent AI diagnosis | Fails: HTTP 503 / `chat_timeout` after 30.188 seconds |
| Independent Python draft | Fails: client `ReadTimeout` after 90.187 seconds; eventual server HTTP 409 after 92.73605 seconds; public history is interrupted with no saved snippet |
| Metrics/dashboard | Version-specific Prometheus issue samples retained, matching alert firing, Grafana dashboard HTTP 200 and configured refresh 15 seconds |
| Final state | API ready, ten services still running, filtered runner log ends with all slots idle; records/volumes retained |

The pinned model remains
`mlpp-qwen2.5:7b-instruct-q4_K_M-json-tools-v1`, artifact digest
`abadc4bf8517d77dcc8db312ca98cd7cb43488243048c41f1b5746e031427779`,
served by Ollama 0.40.2. Deployed settings remain 20 seconds per model call,
60 seconds per complete turn, five model calls and 1,024 output tokens. The
existing walkthrough uses a 90-second HTTP wait. The measured late responses
do not establish timely deadline enforcement or its underlying failure mechanism.

The inspection request used 1,145 uncached prompt tokens. The runner log shows
cancellation before prompt completion. The independent draft's first internal
call completes in 18.762 seconds at the HTTP runtime boundary using a cached
prefix; its next generation call is cancelled. These are internal steps, not a
completed reply or validated Python. No failed generation was retried, and no
generated Python was executed.

The backend smoke saves a separately labelled synthetic 150 ms observation.
Prometheus first records the issue from that fixture before the independent
20-inference producer runs. At final capture the API's five-minute window contains
only the 20 measured samples and five declared delays: mean 38.1243 ms, maximum
151.2376 ms, zero inference errors. These fixture measurements do not establish
production performance or a monitoring detection-time guarantee. Grafana's API
and dashboard configuration were checked; no browser visual review is claimed.

Comparison/history-guided proposals, exact proposal confirmation and resulting
tuning, validated draft/replay, and diagnosis were not reached by the complete
walkthrough. The independent component attempts above are recorded separately.
No full ten-dialogue/seven-snippet acceptance gate, ordinary integration suite,
recovery suite or Kubernetes rollout was rerun. Their earlier evidence retains
its original revision and limitations.

## Commands and evidence

The existing commands were executed once, in order, through the local gateway:

```powershell
& .venv/Scripts/python.exe examples/warm_local_model.py `
    --model 'mlpp-qwen2.5:7b-instruct-q4_K_M-json-tools-v1'
& .venv/Scripts/python.exe examples/midterm_walkthrough.py `
    --confirm-demo-proposal `
    --output artifacts/laptop-rehearsal-20261019/walkthrough
```

After the full workflow stopped, the existing monitoring producer ran once with
the resulting finalized classifier. Diagnosis and the walkthrough's Python-listing
request were each attempted once independently. Cancellation/idle logs were
inspected before ending the rehearsal. All commands and their original outputs
are retained in [the raw archive](raw.zip); [results and provenance](results.json)
identify timings, source/model/image identity, saved states and checks.

The archive includes the final untracked orchestration helper, extended between
phases, rather than claiming it was committed before execution. The actual
walkthrough/producer and application sources match the clean committed revision;
their hashes are retained. An initial read-only database inspection helper needed
a `SecretStr` conversion correction; it caused no inference rerun or application
change. The archive excludes credentials, environment dumps, private ownership
fields, weights, installers and broad process telemetry. Its internal manifest
checks the exact bytes of all 22 payload files, including the offline validator.

Documentation validation passes for five changed Markdown files and 98 local
links/anchors; all 57 execution-source hashes still match. JSON, archive
CRC/manifest hashes, retained Python syntax, saved factual claims, one PowerShell
example's syntax and whitespace pass. [Verification](verification.json) retains
the offline check results; the validator is in the raw archive. Application tests
are not rerun for this documentation/evidence-only update. Review is self-review;
independent boundary review remains outstanding. Commit/push outcome is reported
in the session handoff.

For tomorrow, the rehearsed live portion is registration, training/tuning,
versions/artifacts and measured monitoring. The full local AI demonstration
remains blocked. The [workstation success](../2026-10-14-rx9070-walkthrough/README.md)
is separate evidence; it does not turn this laptop rehearsal into a pass.
