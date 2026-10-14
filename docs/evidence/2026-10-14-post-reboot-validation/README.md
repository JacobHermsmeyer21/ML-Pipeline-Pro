# Post-reboot local validation

October 14, 2026, source `3dd877b`: resumed the approved inspection-fact plan after
Jacob restarted Windows. No application code, schemas, defaults, test assertions,
deadlines or evaluation budgets changed during this validation.

WSL 2 and hardware virtualization are active. Docker Engine 29.8.2 starts its Linux
backend with four CPUs and 9,341,325,312 bytes available to the VM. Initial Docker
distribution provisioning took several minutes; it completed without reinstalling
or resetting storage. The pinned host Ollama 0.40.2 server is reachable from the
rebuilt API container. Its installed requested-fact module hash exactly matches
the committed source.

The dedicated `mlpp-post-reboot-validation` project uses `compose.yaml`,
`compose.services.yaml`, `compose.monitoring.yaml` and `compose.ai.yaml`.
`docker compose ... up --build --wait --wait-timeout 300` succeeds; all ten services
start. Images were built from the clean application source, with local weights and
tokenizer supplied through the reviewed setup rather than packaged into the image.

Ordinary integration runs with both `MLPP_RUN_INTEGRATION=1` and
`MLPP_RUN_WORKER_INTEGRATION=1`. The first attempt passes 60 cases and encounters
three fixture errors accessing an old Windows pytest temp directory. The retained
tracebacks establish `PermissionError` before those cases execute. Rerunning with
a fresh `--basetemp` under ignored workspace artifacts produces **63 passed, zero
failures/errors/skips**, 603 deselected, in **75.20 seconds**. Cache/temp locations
changed; assertions and service budgets did not. This includes the nine affected
conversation-service/snippet cases. Isolated recovery was not rerun locally;
the prior implementation CI retains its separate passing recovery evidence.

Explicit empty-prompt model warmup succeeds. The unchanged complete walkthrough
passes its real training/tuning/model-version/replay backend smoke, then fails at
the first AI inspection with a client `ReadTimeout` (90-second client timeout).
The model reports 113.524 seconds processing 1,147 prompt tokens and 19.545 seconds
generating 51 tokens. The API eventually returns 504 after 140.929 seconds; its
saved turn is `interrupted` / `chat_interrupted`, with no completed tool reads.
Read-only inspection of the public history returns 200 without regenerating.
The original fact-omission boundary is therefore not reached by this attempt.

Slow CPU inference is measured. Why the server's 20-second model/60-second turn
timeouts did not yield a timely response is **not established**. This run does not
prove timeout enforcement under these resource conditions; investigation of that
mechanism remains separate from the narrow requested-fact correction. No retry,
extra warm prompt, timeout increase or repaired output is used to claim a pass.
The model is explicitly unloaded afterward to release memory; its weights remain.

The independent measured-monitoring producer subsequently succeeds using the
backend's finalized model version: 20 serial CPU inferences, warmup excluded,
five declared 150 ms delays, hash/size-verified artifact and identical sample replay.
Prometheus exposes the seeded issue, Grafana serves the `mlpp-midterm` dashboard
with 15-second refresh, and API readiness returns 200. Visibility is checked, but
no scrape-latency guarantee is measured in this run. Backend smoke telemetry is
synthetic and remains separate from this actual inference workload.

[Provenance and summary](results.json) and [raw evidence](raw.zip) retain both
integration attempts, build/startup log, backend/workload records, failed
walkthrough log, public saved turn/history, model timings and service observations.
No runtime environment dump, private MongoDB ownership fields, credentials, model
weights or installer payloads are archived. Generated Python is never executed.

The existing validation containers and records are retained for inspection. Full
AI walkthrough, original failed-record reproduction, passing laptop model gates
and separate boundary review remain open. The original failed demo is absent from
this checkout. The preceding 2/10 dialogue and 0/7 snippet attempts remain the latest
full local-model gates; they were not rerun after reboot. Historical GPU or remote
scripted-model passes do not close these gaps.
