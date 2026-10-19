# Five-minute laptop profile

**October 19 result:** timing implemented on `533a2ed`, local gateway liveness on
`bf07213`, both pushed. After AC reconnection,
[fresh original gates](../evidence/2026-10-19-laptop-awake-gates/README.md) pass all
ten dialogue and seven snippet scenarios; the slowest complete replies are 184.875
and 229.219 seconds. The [latest deployed demo](../evidence/2026-10-19-laptop-gateway-health/README.md)
still fails at its first AI inspection after 144.094 seconds. Local nginx health
also stalls; Kubernetes restarts the gateway while the server finishes within
167.506 seconds. The [approved health change](../plans/2026-10-19-laptop-deployment-health-plan.md)
passes implementation checks but fails live acceptance. Resource attribution is
incomplete; a [bounded diagnosis](../plans/2026-10-19-laptop-resource-diagnosis-plan.md)
awaits review. Do not increase reply time or claim deployed readiness from the
standalone gate passes.
Keep AC connected and the laptop awake throughout live gates.

Jacob approved the [deployment plan](../plans/2026-10-18-laptop-deployment-readiness-plan.md)
on October 19. This explicit profile keeps the pinned 7B model, prompts, token/call
limits, exact confirmation and generated-code validation. Default timeouts remain
20 seconds per model call and 60 seconds per turn. Laptop settings allow 240 seconds
per call within one shared 270-second turn; the client waits up to 300 seconds and
the gateway read timeout is 310 seconds. Socket waits do not establish a hard wall
deadline: any successful complete reply exceeding 300 seconds fails acceptance.

Run locked fast checks and build before live inference. Connect the Acer laptop to
AC power, use one serial presenter, verify the pinned Ollama 0.40.2 artifact and
tokenizer from [local setup](local-model-setup.md), and explicitly warm the model.
Do not run duplicate Compose/host/kind application stacks during the AI gates.
Generated Python is saved for review and never executed.

## Compose

Render from the canonical gateway; rendering does not deploy or infer:

```powershell
uv run --locked --extra training python scripts/render_laptop_profile.py
docker compose --project-name mlpp-post-reboot-validation `
    -f compose.yaml -f compose.services.yaml -f compose.monitoring.yaml `
    -f compose.ai.yaml -f compose.laptop.yaml config --quiet
docker compose --project-name mlpp-post-reboot-validation `
    -f compose.yaml -f compose.services.yaml -f compose.monitoring.yaml `
    -f compose.ai.yaml -f compose.laptop.yaml up --build --wait --wait-timeout 300
```

Use the actual existing project's name to preserve its records and volumes. The
override mounts `artifacts/laptop-five-minute/gateway.conf`; render to that default
directory before Compose startup. Removing the override restores the base gateway
and settings. Let any long turn finish or expire before reverting/restarting.

## Kubernetes

Preserve existing Compose data with `docker compose --project-name YOUR_PROJECT stop`
using that project's original files. Do not delete its volumes. Create a fresh
explicitly named kind cluster; occupied names are rejected:

```powershell
docker build -t ml-pipeline-pro:midterm .
uv run --locked --extra training python scripts/deploy_kind.py `
    --name mlpp-laptop-five-minute --timing-profile laptop-five-minute `
    --output artifacts/laptop-five-minute-kubernetes
```

This reuses the canonical stack/local-AI patch, copies the installed tokenizer into
the new node, applies the rendered gateway/budgets, checks two model API replicas
and one serial worker, and runs backend smoke/direct-replica replay. No weights are
pulled. Open a gateway port-forward as described in [Kubernetes](kubernetes-demo.md),
using this cluster's explicit kubeconfig/context. Preserve that cluster's node/PVCs
for a controlled stop/start and verify saved records/artifacts afterward.

## Gates and walkthrough

Use the original [ten/seven semantic gates](guided-midterm-demo.md#reproduce-acceptance)
with `--timing-profile laptop-five-minute` on each pytest command. Their suite
budgets become 3300 and 2400 seconds, respectively. Request, token, output, scenario
and validation assertions are unchanged. Reports identify profile, effective call/
turn budgets and elapsed complete-reply times. Earlier default-profile failures
remain separate evidence. After any inference timeout, inspect cancellation and
actual runner-idle logs before sending another request; retain incomplete gates as
failures rather than retrying or omitting their scenarios.
The laptop harness stops after its first failed case, retaining its unused scenario
list and failure. Inspect runner idleness before any separate later suite or demo.

```powershell
uv run --locked --extra training python examples/warm_local_model.py `
    --model 'mlpp-qwen2.5:7b-instruct-q4_K_M-json-tools-v1'
uv run --locked --extra training python examples/midterm_walkthrough.py `
    --origin http://127.0.0.1:18000 --timing-profile laptop-five-minute `
    --confirm-demo-proposal --output artifacts/laptop-five-minute-demo
```

For Compose use origin `http://127.0.0.1:8000`. AI-only waits change; ordinary
backend/confirmed-action requests retain their existing bounds. The walkthrough
saves every AI attempt's status/public body/elapsed time, including failures, and
rejects a late success. Boundary logs identify construction, preparation, token
admission, inference/cancellation, reservation and persistence without logging
prompts, credentials or exception text. These logs measure boundaries; they do not
by themselves establish the cause of the historical timeout overruns.

## Gateway health

Jacob approved the health follow-up on October 19. The rendered laptop gateway
serves exact `GET /gateway-live` locally as `200 {"status":"alive"}`, preserving
the normal `X-Correlation-ID` response header. Its Kubernetes liveness probe uses
that path. Readiness/startup remain on the upstream API health paths with their
existing thresholds; local nginx health does not imply that an API is available.
Default deployments and the canonical gateway/manifest are unchanged.

The explicit real-nginx negative check requires Docker and the already installed
`nginx:1.28-alpine` image. It creates only its own test bridge, gateway and sleeping
backend, checks failed DNS and refused upstream TCP, then removes those containers
and network. It never runs a model or changes the presentation cluster:

```powershell
uv run --locked --extra training python scripts/check_laptop_gateway.py `
    --output artifacts/laptop-gateway-check
```

Require local liveness 200 while upstream health/readiness and the non-exact
`/gateway-live/` path return the existing correlated 503. Retain the actual nginx
DNS/refused-connection logs. Before claiming laptop readiness, rebuild/redeploy,
verify effective probe paths/source hashes, collect lightweight host/VM/probe/DNS
resource evidence and repeat the original complete walkthrough. Wider API stalls
or restarts require retained failure evidence and further review.

## Unbounded timing diagnostic

Jacob approved the [separate diagnostic design](../plans/2026-10-19-laptop-unbounded-diagnostic-plan.md)
on October 19. This experiment measures one complete walkthrough, then one more
fresh run only if the first completes correctly and the runner is idle. It is
separate from finite-profile acceptance and from the original ten/seven gates,
which continue rejecting unbounded timing. No live result is established by setup.

Render with `--timing-profile laptop-unbounded-diagnostic`. Only this manifest
omits startup/readiness/liveness probes on gateway/model/tuning/monitoring. Datastore,
worker, monitoring infrastructure, replica/resource settings and canonical files
remain unchanged. Before inference, query actual API readiness/dependencies and
verify installed source/settings; Kubernetes Ready alone is insufficient here.
Rendering alone does not change running pods. Build/load the current image and
apply the rendered manifest using the [Kubernetes deployment procedure](kubernetes-demo.md),
preserving the existing named cluster and its volumes. Wait for rollout, then run
the explicit HTTP preflight before starting the commands below.

The profile sets `MLPP_CHAT_UNBOUNDED_DIAGNOSTIC=true` and both
`MLPP_CHAT_TIMEOUT_SECONDS=none` / `MLPP_CHAT_MODEL_TIMEOUT_SECONDS=none`.
These nulls are accepted together only in explicit non-production diagnostic mode.
They disable host asyncio and Ollama/LangChain waiting timers. Keep call/token/
byte/schema assertions and existing tool, action and training/tuning failure bounds.

Forward one verified model API pod to 18001 and monitoring API pod to 18002,
alongside the backend gateway at 18000. Supply both direct origins explicitly:

```powershell
uv run --locked --extra training python scripts/render_laptop_profile.py `
    --timing-profile laptop-unbounded-diagnostic --output artifacts/laptop-unbounded-profile
uv run --locked --extra training python examples/midterm_walkthrough.py `
    --origin http://127.0.0.1:18000 --project laptop-unbounded-demo `
    --timing-profile laptop-unbounded-diagnostic `
    --diagnostic-model-api-origin http://127.0.0.1:18001 `
    --diagnostic-monitoring-api-origin http://127.0.0.1:18002 `
    --confirm-demo-proposal --output artifacts/laptop-unbounded-demo-1
```

Use fresh output/record identities. No hidden wall-time process kill or generation
retry is part of this measurement. A semantic/transport failure ends the run and
is retained. Generated Python is never executed. Client output records actual AI
targets and each reply's elapsed time as observations, with bounded acceptance false.
This direct AI delivery path does not prove unlimited reliability through nginx.

Only new diagnostic reservations receive matching `diagnostic_unbounded` markers
and null deadlines on parent/turn. Saved finite deadlines and legacy bounded rows
keep their original expiry. Completion still fences parent ownership transactionally.
After a crash, public history retains `running`; uncertainty is external evidence,
not a new status or automatic takeover. Keep compatible readers for these records.

After completion or an explicit user stop, retain evidence/idle state, release own
wake request and port-forwards, then restore the normal five-minute manifest and
verify its probes and 240/270-second server settings. Preserve PVCs, records and
artifacts. No older application rollback over diagnostic rows is implied.
