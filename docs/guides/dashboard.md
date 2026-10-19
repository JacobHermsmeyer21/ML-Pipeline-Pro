# Local ML workspace

The dashboard runs on the existing model API at
`http://127.0.0.1:8000/dashboard/`. It supports numeric CSV classification,
training/results/artifacts, local-agent conversations and real Grafana panels.
The dataset and trained classifier are separate from the pre-trained local agent.

## Start on this desktop

Start Docker Desktop and the installed Ollama runtime as described in
[local model setup](local-model-setup.md#install-and-start-the-standalone-runtime).
Use the existing desktop Compose project to preserve its records and artifacts:

```powershell
Set-Location C:\Users\jacob\Desktop\ML-Pipeline-Pro
$dashboardCompose = @(
    'compose', '--project-name', 'mlpp-rx9070-walkthrough-20261014',
    '-f', 'compose.yaml', '-f', 'compose.services.yaml',
    '-f', 'compose.monitoring.yaml', '-f', 'compose.ai.yaml',
    '-f', 'compose.dashboard.yaml'
)
& docker @dashboardCompose build model-api
if ($LASTEXITCODE -ne 0) { throw 'Dashboard image did not build.' }
& docker @dashboardCompose up --no-build --wait --wait-timeout 300
if ($LASTEXITCODE -ne 0) { throw 'Dashboard stack did not become ready.' }
& .venv/Scripts/python.exe examples/warm_local_model.py `
    --model 'mlpp-qwen2.5:7b-instruct-q4_K_M-json-tools-v1'
if ($LASTEXITCODE -ne 0) { throw 'Installed model did not warm up.' }
Start-Process 'http://127.0.0.1:8000/dashboard/'
```

The overlay enables `MLPP_DATASET_UPLOAD_ENABLED` only in the model API and mounts
the same named uploads volume there and read-only in the worker. Grafana permits
iframe embedding in this overlay, retaining its existing local anonymous Viewer.
Ports remain loopback. The base stack and model/turn budgets retain their defaults.
Keep other heavy verification/inference work quiescent during an agent demo.

## Browser walkthrough

1. Open **Datasets**, choose a CSV, enter a name/version and review feature, target
   and split columns. The downloadable example matches the checked-in 120-row
   fixture: 80 training, 20 validation and 20 test rows. Click **Validate & add
   dataset**. Server validation is authoritative and returns the hash/split counts.
2. Select **Use for training**, select or create a named MLP model, and review
   training settings. Click **Review training**, then **Start training**. The run
   list polls active work; it displays actual states and saved validation metrics.
3. Open a run to inspect results, ask the agent about its validation F1, download
   hash/size-verified artifacts or register an eligible completed model version.
   Comparison uses validation F1 and the same dataset version.
4. Use the agent's visible prompt starters or write a request with real IDs and
   explicit budgets. Review the complete proposed arguments before **Approve
   action** or **Reject**. A Python draft is displayed for review/copy/download;
   it is never executed by the workspace.
5. Open **Monitoring**, select a registered version and a time range. Grafana
   panels show inference latency, labeled accuracy, errors and declared artificial
   delays. **Explain observations** requests evidence-linked local-model advice
   when the latest five-minute window contains observations.

Supported CSVs use UTF-8, distinct named numeric feature columns, contiguous
integer training classes beginning at zero, and explicit nonempty `train`,
`validation`, `test` splits. Validation/test classes must appear in training.
Uploads are limited to the smaller of 10,000,000 bytes and
`MLPP_DATASET_MAX_BYTES`, plus the existing row/class/value limits. Automatic
splitting, categorical encoding, text/image training and LLM fine-tuning are not
provided. New dataset versions get immutable file references; changing content
under the same name/version returns 409. Matching upload replay returns its saved
record rather than creating another version.

## Monitoring data and history

Training alone creates no inference observations. A newly registered version can
therefore show no data. To rehearse graphs with actual measurements, run the
existing [monitoring producer](monitoring-demo.md#measured-workload-and-meaning)
against a finalized model/version. Its validation-fixture replay deliberately
injects five delays; label them as artificial. The complete
[backend demo](midterm-walkthrough.md) also creates one synthetic routing sample.
These plots are not training-loss curves or proof of production performance.

For a version trained from an uploaded file, run the producer inside the worker
container so it reads that same shared CSV volume. With the same Compose files
and project as startup, reuse the PowerShell variable above:

```powershell
& docker @dashboardCompose exec -T worker python examples/monitor_workload.py `
    --origin http://api:8000 --model-id YOUR_MODEL_ID --version-id YOUR_VERSION_ID `
    --output artifacts/dashboard-workload.json
```

Replace the two IDs with the finalized model/version IDs. Run this after
training/tuning finishes. The host producer does not automatically
mount Docker's named uploads volume.

Graphs and the visible monitoring summary refresh every 15 seconds. The Grafana
dashboard explicitly allows that interval; summary reads preserve the existing
chart frames and pause when the page is hidden. The exporter covers the latest 100 project
observations in five minutes; the chosen graph range can show older scrapes.
Keep this bounded-window limit and the displayed partial/unknown state in mind.
Prometheus is configured for project `demo`; the workspace does not embed those
graphs for another project. This local Viewer configuration is not multi-user
Grafana authorization.

Saved conversation IDs and unresolved request identities are remembered in this
browser session, keyed by project. The actual history is stored by the API. API
keys remain in memory and must be re-entered after a page reload when configured.
There is no cross-browser conversation discovery screen. After a timeout, use
**Check saved turn**, **Check saved state**, or **Check / retry same submission**;
these preserve the saved request/action identity. A transport error does not prove
that a training job was rejected. Changing projects clears displayed records and
prevents late responses from populating the next project.

## Stop and preserve data

Use the same Compose files and project name with `stop` to stop services. Do not
delete the uploads volume while dataset records reference it. Rolling back the
dashboard must preserve the uploads mount in the API/worker and the files themselves;
otherwise those records cannot train. Rejected/interrupted staging files are
removed. Published files are retained after uncertain metadata writes; automated
orphan cleanup is deferred. Existing named dataset/artifact volumes and models
are preserved.
