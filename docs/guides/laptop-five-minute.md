# Five-minute laptop profile

**October 19 result:** implemented and pushed on `533a2ed`. The first actual-ID
inspection passes in 210.532 seconds, but a liveness-triggered gateway restart
breaks the next turn before its reply deadline. The full demo fails. The separate
dialogue gate passes eight cases before a Windows sleep interruption; the remaining
cases and snippets do not establish acceptance. See [retained evidence](../evidence/2026-10-19-laptop-five-minute/README.md)
and the [unapproved health follow-up](../plans/2026-10-19-laptop-deployment-health-plan.md).
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
