# Minimal live monitoring

Start the three independent APIs with visualization:

```powershell
docker compose -f compose.yaml -f compose.services.yaml -f compose.monitoring.yaml `
    up --build --wait --wait-timeout 300
```

Open [the workload dashboard](http://127.0.0.1:3000/d/mlpp-midterm) and
[Prometheus](http://127.0.0.1:9090). Both ports bind loopback. Prometheus scrapes the
authenticated monitoring API for project `demo`; Grafana provisions one read-only
dashboard. Configured project keys require a private scrape header configuration:
use `http_headers.X-API-Key.files` and a separately mounted credential file per the
[official configuration](https://prometheus.io/docs/prometheus/latest/configuration/configuration/).
Keep credential files outside Git. The checked-in demo is unkeyed; wrong configured
keys fail access checks and the scrape shows `up=0`.

The [local dashboard](dashboard.md#monitoring-data-and-history) embeds these same
Grafana panels when `compose.dashboard.yaml` enables iframe embedding. Training
alone produces no inference observations. For uploaded datasets, run the producer
inside the worker with its shared read-only uploads mount, using the dashboard
guide's command. Permanent dataset/model deletion removes associated MongoDB
observations; previously scraped Prometheus history remains visible in older
graph ranges. This demo Viewer configuration is not multi-user authorization.

## Measured workload and meaning

Create a completed, test-evaluated model version using the
[classification workflow](workflows.md#classification-experiment-walkthrough),
then pass its real IDs:

```powershell
uv run --locked --extra training python examples/monitor_workload.py `
    --model-id 'YOUR_MODEL_ID' --version-id 'YOUR_VERSION_ID'
```

The producer verifies downloaded checkpoint hash/size and the registered CSV hash.
It loads PyTorch with `weights_only=True`, uses saved training-fitted mean/std,
warms up once, then measures 20 serial CPU inferences on the validation fixture.
Five include an explicitly declared 150 ms delay. Each sample saves timestamp,
version, latency, outcome, nullable correctness and a fixed safe fault category.
Every sample replay must equal its first response. Monitoring performs no model
selection, retraining, artifact writes or generated-code execution.

This is fixture replay after model finalization, not production traffic or evidence
of generalization. The dashboard/summary cover the newest 100 samples in five
minutes. `partial=true` means older observations were omitted; unknown accuracy is
omitted rather than shown as zero. Empty/stale windows show missing data/unknown
issue, not healthy inference. A maximum over 100 ms sets the demo issue and
Prometheus `MLPPWorkloadLatencyHigh` rule; there are no notification destinations.
Declared injected delays must be checked before claiming a real regression.

Scrape/rule evaluation and dashboard refresh are each 15 seconds. The target is
observed visibility within 30 seconds on the declared workload. The retained run
showed the issue after **4.1 seconds** from the final accepted measured sample;
this is a local observation, not a latency guarantee for arbitrary load/clocks.

## Local-model explanation

Complete [the evaluated 7B setup](guided-midterm-demo.md) before enabling AI:

```powershell
docker compose -f compose.yaml -f compose.services.yaml -f compose.monitoring.yaml `
    -f compose.ai.yaml up --build --wait --wait-timeout 300
```

The optional overlay mounts only the verified tokenizer, uses the explicitly
installed local model through `host.docker.internal`, and makes no model download.
This runtime connection was exercised with Windows/Docker Desktop. The canonical
factories use explicit `MLPP_CHAT_TOKENIZER_PATH`; native/generic defaults remain
unchanged. Other host networking/runtime profiles require their own evidence.

Send `POST /api/v1/monitoring/model-versions/YOUR_VERSION_ID/diagnosis` with your
project headers. The response includes measured summary, separate generated
interpretation, one to three observation citations, proposed human checks and
request-specific model provenance. One bounded LangChain call, no native tools,
no automatic changes. No data gives 409; unconfigured/unavailable model gives 503;
invalid output/citations are rejected. A cold first call timed out in one retained
attempt; it was not converted to a pass or retried inside the application.

Jacob reviewed the retained summary and proposed seed-delay check on October 13
as clear/useful for the class demo. Review future outputs against their measurements.
The [delivery plan](../plans/2026-10-13-monitoring-deployment-plan.md) records design,
boundary review and execution limits; wider drift/alert-state machinery is deferred.
