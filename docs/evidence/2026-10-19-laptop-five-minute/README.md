# Five-minute laptop implementation and rerun

Jacob approved the [five-minute plan](../../plans/2026-10-18-laptop-deployment-readiness-plan.md)
on October 19, 2026. Implementation `533a2ed0ef7cc70205c06ad218fabe2f9365dfb0`
is committed and pushed. The complete laptop walkthrough **fails**; the larger
window permits the first inspection, but does not establish presentation readiness.
[Results](results.json), [archive verification](verification.json), and the
[raw archive](raw.zip) retain successes, failures and execution provenance.

Later on October 19, Jacob reconnects AC and requests continuation. A
[fresh full standalone execution](../2026-10-19-laptop-awake-gates/README.md) passes
all ten dialogue and seven snippet scenarios. This supersedes the incomplete
model-gate status for that later run only; the failed deployed walkthrough and
the original interrupted raw evidence below remain unchanged.

## Arrangement and implementation

The actual Acer Aspire A515-46 uses a Ryzen 3 3350U / Vega 6 CPU arrangement,
Windows 10, Python 3.11.17 and the locked dependencies. Ollama 0.40.2 serves the
installed `mlpp-qwen2.5:7b-instruct-q4_K_M-json-tools-v1`, digest
`abadc4bf8517d77dcc8db312ca98cd7cb43488243048c41f1b5746e031427779`.
No model, prompt, thread setting or output repair changed during these runs.
The walkthrough starts and ends on AC power. The later dialogue gate has a
separate sleep/power interruption described below.

The explicit `laptop-five-minute` profile allows 240 seconds per model call
within one original 270-second turn deadline, 300 seconds for a complete client
reply and a 310-second gateway read wait. Defaults remain 20/60 seconds. Token,
call, proposal/confirmation, validation and ownership rules remain binding.
Payload-free logs measure preparation, token admission, inference, reservation,
completion and cancellation. A late successful reply still fails acceptance.

The rebuilt Compose deployment's installed modules match the checkout. After
ordinary integration, it was stopped with its volumes preserved. The new kind
cluster `mlpp-laptop-five-minute`, namespace `mlpp-demo`, uses the same verified
application image, installed tokenizer, two model API pods and one serial worker.
All four deployed domain API pods' module hashes match the committed sources;
model and monitoring APIs use the selected budgets. Kubeconfig, credentials,
weights, installers and recovery database snapshots are excluded from this archive.

## Actual walkthrough

One explicit warmup preceded one original walkthrough execution. Every failed
client attempt is retained. There was no generation retry or generated-code execution.

| Boundary | Measured result |
| --- | --- |
| Backend setup | Training, three-trial Bayesian tuning, model version and submission replay pass before AI. |
| First inspection | HTTP 200 after **210.532 s**; saved completed turn, one successful `get_experiment`, verified `metrics.validation_f1 = 1.0` for actual experiment `1bab1c33-2baf-4b68-8ac7-04a196641c57`. |
| Comparison/history proposal | Client `RemoteProtocolError` after **132.937 s**, with no HTTP response. No pending action or proposal was produced. |
| Whole walkthrough command | Exit 1 after **368.766 s**. Proposal confirmation, its tuning, Python draft/replay, measured monitoring producer and AI diagnosis were not reached. |
| Saved second turn | Server completes after **135.566 s**, with a `compare_experiments` transport failure and an honest unavailable-comparison reply. No facts, pending action or submission. |
| Runtime afterward | Filtered runtime logs end with `all slots are idle`; no inference cancellation was needed for these two completed server turns. |

The immediate delivery failure is confirmed by correlated evidence:

1. Kubernetes records `Killing` for the gateway at **16:29:56 UTC**, explicitly
   because its liveness probe failed. Another model API replica is also killed;
   that replica was not serving the second turn.
2. The gateway's previous container terminates at **16:30:47 UTC**, exit 137,
   reason `Error`. The port-forward stream closes at **16:30:47.681**. Its
   replacement starts at **16:30:50**. These records do not establish OOM.
3. The serving model API remains running and saves the second reply at
   **16:30:50.246 UTC**. Its internal API read failed through the gateway.

The gateway liveness path `/api/v1/health/live` proxies through the model API and
DNS. Logs show a DNS resolution timeout on that health path and broad health-check
delays during inference. The disconnect occurs before any selected reply window
expires. More timeout cannot prevent this restart. CPU starvation, memory/paging
and VM scheduling remain hypotheses: this run has no sufficient resource trace
to distinguish them. A gateway-local liveness fix alone may not resolve the wider
API/DNS delays. See the [follow-up plan](../../plans/2026-10-19-laptop-deployment-health-plan.md),
which awaits review.

The initial collector also loses its history GET during recovery. A subsequent
read-only reconnect retrieves conversation `c2eae9c1-23e1-4cc4-8baa-899788b8ef5d`
without generation or confirmation. Its projected deadline audit retains the
original 270-second expiry; no deadline was extended. The original helper and its
failure remain in the archive.

## Other checks and gaps

| Check | Outcome |
| --- | --- |
| Locked environment, lint, formatting, dependency compatibility | Pass. |
| Full fast suite | 644 passed, 73 integration deselected, 81% rounded coverage, 170.40 s. |
| Final focused checks | 23 passed, including two new regressions added after the full run; these are not 23 additional unique cases. |
| Package build | Pass; source archive has zero cache entries and wheel contains both new modules. uv's workspace-cache warning remains recorded. |
| Ordinary real-service integration | All 63 pass, no selected skips, 67.96 s. |
| Initial isolated recovery | Nine pass, one fails at the existing 90-second `docker compose start worker` command, before recovery assertions. Underlying stall unresolved. |
| Recovery after stopping old Compose deployment | Unchanged failing boundary passes alone (63.92 s); fresh complete isolated suite passes all ten (349.15 s). No assertion, command limit or code change between runs. |
| Initial Kubernetes rollout | Fails existing 180-second Mongo rollout wait during cold dependency pulls. An attempted installed-image import also fails on an unavailable multi-platform content digest. Neither failure is hidden. |
| Continued Kubernetes validation | Once dependencies become available, unchanged 180-second rollout checks, backend smoke and direct replay through both model API pods pass. The failed import is not credited with readiness. |
| Kubernetes node stop/start | Pass, 114.719 s: saved records identical, downloaded training artifacts match hash/size, same-key replay identity preserved. Transient recovery restarts retained. |
| Implementation remote CI | All five jobs [pass](https://github.com/JacobHermsmeyer21/ML-Pipeline-Pro/actions/runs/39283258489), including both Python checks and deployment jobs. |
| Separate original ten-case dialogue gate | **Failed/incomplete**: eight cases pass; `hostile_record` is interrupted and `evidence_status_accuracy` is unrun. |
| Original seven-case snippet gate | Unrun in this profile; no acceptance inferred. |

The direct dialogue gate uses synthetic API fixtures, not the Kubernetes gateway.
Its eight complete replies take 47.859, 112.250, 90.234, 23.234, 23.484, 29.406,
25.796 and 44.109 seconds. These include a valid history-guided proposal against
fixtures, which does not establish that the deployed proposal path passed.
Windows Power-Troubleshooter records sleep **16:45:40.146–18:05:28.288 UTC**
(reason Button or Lid; wake source Power Button). AC changes from connected to
disconnected. The ninth case records 4902.953 seconds without a result; the suite
raises `TimeoutError`, and its command finishes after 5313.765 seconds despite its
3450-second outer safety timer. These sleep-inclusive durations are not CPU-only
model benchmarks or successful timeout enforcement. The original raw JSON lacks
its final unrun list because cancellation bypassed normal failure bookkeeping;
`results.json` derives that list from the original scenario order and labels it.
Runner logs subsequently end idle. Remaining live gates require AC and an awake
laptop; this interrupted gate has not been retried.

Separate read-only review by the OpenAI `timing_review` agent found and confirmed
fixes for Kubernetes backend DNS qualification and automatic evaluation continuation
after failure. A different-vendor reviewer was unavailable. Follow-up evidence review
confirms the gateway restart sequence and the limits of resource attribution.
Human quality review of newly generated outputs, a complete laptop walkthrough,
all ten/seven model gates, original-record reproduction and a live under-load
deadline-expiry rehearsal remain outstanding. Prior workstation and monitoring
component passes remain separate historical evidence.

## Reproduction and archive

Use the [profile guide](../../guides/laptop-five-minute.md) for canonical commands.
The executed orchestrators and each recorded argv/source hash are retained under
`orchestration/` and `validation/*-execution.json` inside `raw.zip`. They were
untracked helpers during execution, not committed application code. In particular:

```powershell
uv run --locked --extra training python scripts/deploy_kind.py `
    --kind .tools/bin/kind.exe --name mlpp-laptop-five-minute `
    --timing-profile laptop-five-minute `
    --output artifacts/laptop-five-minute-kubernetes
kubectl --kubeconfig artifacts/laptop-five-minute-kubernetes/kubeconfig `
    --context kind-mlpp-laptop-five-minute -n mlpp-demo `
    port-forward service/gateway 18000:8000 --address 127.0.0.1
```

Run the following in a second terminal after readiness and explicit warmup:

```powershell
uv run --locked --extra training python examples/midterm_walkthrough.py `
    --origin http://127.0.0.1:18000 --timing-profile laptop-five-minute `
    --confirm-demo-proposal --output artifacts/laptop-five-minute-demo
```

The named cluster/PVCs and stopped Compose volumes remain intact. Do not repeat
cluster creation against that occupied name. Recovery tests used separate disposable
stacks. The archive's `manifest.json` records every payload's SHA-256 and byte size;
`verification.json` records CRC/manifest verification. Application and harness source,
public histories, projected deadlines, runtime timing/state rows, pod status/events,
test logs/JUnit and initial failed deployment/recovery attempts are included.
`results.json` records the archive hash. No readiness or speedup claim follows from
packaging these files.
