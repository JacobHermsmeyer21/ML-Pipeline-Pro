# Local Kubernetes deployment

Use Docker, kubectl and verified [kind v0.33.0](https://kind.sigs.k8s.io/docs/user/quick-start/).
The checked-in [manifest](../../deploy/kubernetes/stack.json) runs three independent
domain APIs, gateway, singleton MongoDB replica set/Redis/worker/scheduler, and
Prometheus/Grafana. It uses local persistent claims, resources and health probes.
Two model APIs share durable records; the worker stays one replica/concurrency one.
The MongoDB headless Service publishes startup addresses so the replica set can
identify its own node before readiness. Ordinary readiness still checks only
MongoDB/Redis, not every domain or worker progress.

MongoDB's startup probe initializes an empty replica set or checks the saved set's
writable primary. Twelve failed five-second checks restart its process, preserving
the PVC and configuration. This recovers the observed invalid membership when
cluster DNS is unavailable during initial startup; it is not a recovery-time SLA.
The [diagnosed fix](../plans/2026-10-13-kubernetes-mongo-startup-plan.md) records its test.

The eleven application pods reserve 600m CPU total (50m for ten lightweight pods,
100m for the serial worker), in addition to Kubernetes system reservations. CPU
limits remain 500m per lightweight pod and one CPU for the worker. Reservations
allow scheduling/sharing; they do not establish measured concurrent capacity. See
[resource semantics](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
and the [measured CI scheduling fix](../plans/2026-10-13-kubernetes-cpu-budget-plan.md).

From the repository root:

```powershell
docker build -t ml-pipeline-pro:midterm .
if ($LASTEXITCODE -ne 0) { throw 'Image build failed.' }
uv run --locked --extra training python scripts/deploy_kind.py `
    --name mlpp-class-demo --output artifacts/kubernetes-class-demo
if ($LASTEXITCODE -ne 0) { throw 'Deployment or smoke failed; inspect retained logs.' }
```

The script creates a new explicitly named test cluster, uses its own kubeconfig,
loads the image, applies/awaits all deployments and runs actual training, three-trial
tuning, version registration, monitoring and replay checks. It rejects an occupied
cluster name rather than deleting it. Its temporary gateway port-forward closes
after verification. Open the APIs/dashboard from dedicated terminals:

```powershell
kubectl --kubeconfig artifacts/kubernetes-class-demo/kubeconfig --context kind-mlpp-class-demo `
    -n mlpp-demo port-forward service/gateway 18000:8000 --address 127.0.0.1
```

```powershell
kubectl --kubeconfig artifacts/kubernetes-class-demo/kubeconfig --context kind-mlpp-class-demo `
    -n mlpp-demo port-forward service/grafana 13000:3000 --address 127.0.0.1
```

The smoke's monitoring sample is a declared synthetic routing fixture. Run
[the measured producer](monitoring-demo.md) with `--origin http://127.0.0.1:18000`
and IDs in its saved `smoke.json` for actual inference observations. This deployment
uses single-node local storage; multi-node shared storage, public hosting and
concurrent training remain deferred. Empty project-key Secret is local demo
configuration; actual credentials must be supplied privately, including scraping.

## Optional evaluated local AI

For the CPU presentation laptop, use the approved
[five-minute profile](laptop-five-minute.md#kubernetes), which renders the canonical
stack and AI patch with matching gateway/API budgets. Default deployment below
keeps its original timing settings.

The default Kubernetes smoke needs no weights or external model credentials.
To enable the already installed Windows/Docker Desktop runtime, mount/copy the
verified tokenizer into the explicitly named test node. Weights stay with Ollama:

```powershell
docker exec mlpp-class-demo-control-plane mkdir -p /mlpp-local
docker cp .tools/local-model-setup/tokenizer.json mlpp-class-demo-control-plane:/mlpp-local/tokenizer.json
kubectl --kubeconfig artifacts/kubernetes-class-demo/kubeconfig --context kind-mlpp-class-demo `
    apply -f deploy/kubernetes/ollama-local.json
foreach ($domainName in @('model-api', 'monitoring-api')) {
    $patchText = (Get-Content deploy/kubernetes/local-ai-patch.json -Raw).Replace('DOMAIN_NAME', $domainName)
    $patchPath = Join-Path (Get-Location) "artifacts/kubernetes-class-demo/$domainName-ai.json"
    [System.IO.File]::WriteAllText($patchPath, $patchText)
    kubectl --kubeconfig artifacts/kubernetes-class-demo/kubeconfig --context kind-mlpp-class-demo `
        -n mlpp-demo patch deployment $domainName --type strategic --patch-file $patchPath
    if ($LASTEXITCODE -ne 0) { throw 'Local AI patch failed.' }
    kubectl --kubeconfig artifacts/kubernetes-class-demo/kubeconfig --context kind-mlpp-class-demo `
        -n mlpp-demo rollout status "deployment/$domainName" --timeout=180s
}
```

Run the [complete walkthrough](midterm-walkthrough.md) on the forwarded origin.
The pinned counter fails safely if runtime/tokenizer identity or networking differs;
never infer success from pod readiness alone. Other local-network profiles need
verification. Recopy/verify the tokenizer when recreating a node.

## CI/CD and cleanup

[GitHub Actions](../../.github/workflows/ci.yml) checks the locked environment first,
then builds/loads/applies the actual image into an ephemeral kind cluster and runs
the same rollout/smoke. The deployment job retains JSON/logs and deletes only the
cluster it created. It never uploads kubeconfig credentials. Ordinary Compose and
isolated recovery jobs remain; live local-model evaluation is separately opt-in.

To remove only this explicitly named classroom test cluster after its demo:

```powershell
kind delete cluster --name mlpp-class-demo
```

This removes its local test data/volumes. It does not remove the repository's
default Compose volumes. Do not use another cluster's name or default kubeconfig.
