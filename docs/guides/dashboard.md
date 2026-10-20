# Local ML workspace

The dashboard runs on the existing model API at
`http://127.0.0.1:8000/dashboard/`. It supports raw tabular CSV classification,
training/results/artifacts, local-agent conversations and real Grafana panels.
The dataset and trained classifier are separate from the pre-trained local agent.

October 19 delivered raw CSV preparation, saved column-subset versions and
permanent dataset/classifier deletion. The latest
[column browser/service run](../evidence/2026-10-19-dataset-columns/README.md)
records 740 fast, 104 ordinary and ten recovery passes plus five real worker runs;
[deletion evidence](../evidence/2026-10-19-permanent-deletion/README.md) covers
reviewed cascades, native locks and uncertain cleanup recovery. Jacob accepted
the visual direction; independent boundary review and human usefulness review
of the completed dataset controls remain open. These desktop/browser results
do not close the bounded CPU-laptop AI deployment gap.

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

1. Open **Datasets**, choose the original CSV, enter a name/version and select the
   prediction target. Click **Preview encoding**. Review each feature, category
   encoding, missing-value fill, target class ID and split count. Change any
   choices, refresh the preview, then click **Save reviewed dataset**. The normal
   path automatically creates stratified 70/15/15 splits with seed 42.
2. Select **Use for training**, select or create a named MLP or logistic regression model, and review
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

### Compare algorithms

Create two named models using **Create model → Algorithm**: MLP and Logistic
regression. Use the same saved dataset version for both. Model menus and run
details show the algorithm. Each experiment trains fresh weights. MLP settings
include hidden units; logistic settings replace that field with **L2 strength**
(0 through 1, default 0). Common defaults are 30 epochs, batch size 16, learning
rate 0.01, seed 42 and a 60-second runtime limit. Review the applicable settings
before **Start training**. An unresolved submission retains its original model,
settings and key even if you change the selected model or reconnect.

Logistic regression uses a PyTorch linear layer, binary/multiclass logits,
cross-entropy and minibatch Adam. L2 adds half the strength times squared weights
to the loss, excluding bias. It is gradient training without a convergence
guarantee. Both algorithms standardize using training rows only and select the
checkpoint using validation results before evaluating the test split.

After both runs succeed, open one and choose **Compare validation results**.
The comparison uses validation F1 on that same dataset version. Download each
checkpoint/manifest for hash/size verification; register a completed run through
**Register version**. Registration alone does not create monitoring observations.
Read/compare agent tools support both algorithms; AI training proposals, AI tuning,
and generated logistic snippets are deferred. Use the manual form for logistic
training. Logistic tuning and AI mutation requests fail explicitly. Deploy the API,
worker and dashboard together; old workers cannot run logistic jobs.

For automated acceptance, start a disposable upload-enabled stack using
`compose.yaml` plus `tests/integration/compose.validation.yaml` with a unique
Compose project name. That overlay uses API port 18000 and separate volumes.
With Chrome installed, run:

```powershell
uv run --locked --extra training --with playwright==1.64.0 python `
    scripts/verify_logistic_dashboard.py --origin http://127.0.0.1:18000 `
    --output artifacts/logistic-validation/browser
```

The script creates an isolated project, two prepared synthetic datasets and three
real serial worker runs. It verifies model switching, settings/review, lost-response
retry across reload, checkpoint hashes/predictions/metrics, comparison and version
registration. It retains screenshots and `result.json`; records stay in that
disposable project for inspection. It does not invoke a live AI model or establish
human usefulness review.

Supported original CSVs use UTF-8 with distinct nonempty headers, numeric or
categorical features and 2-64 nonempty target classes. The app converts categories
and string class names into numeric inputs, retaining readable mappings. Source
headers/cells have a 128 UTF-8 byte bound. Every split must contain every class;
very small classes require more rows or adjusted ratios. Missing targets fail.
Uploads are limited to the smaller of 10,000,000 bytes and
`MLPP_DATASET_MAX_BYTES`, plus row/class/value and encoded expansion limits in the
[API reference](../reference/api.md#raw-csv-preparation). Text/image training and
LLM fine-tuning remain outside this classifier. New versions get immutable source,
prepared CSV and recipe references; changing content or preparation settings
under the same name/version returns 409. Matching upload replay returns its saved
record rather than creating another version.

<a id="column-mapping-and-an-unprepared-csv"></a>

### Review and change encoding

The review shows training-derived vocabularies, source names and generated output
columns. Each feature offers automatic treatment, numeric, one-hot, an explicit
custom numeric category mapping, or exclusion. Prefer one-hot for unordered
categories; a custom numeric mapping imposes distances. You may also change the
target class IDs while keeping them distinct and contiguous. Unseen one-hot
categories become zeros; custom mappings use the reviewed fallback. Any edit
disables saving until **Preview encoding** refreshes the exact recipe.

Under **Preparation settings**, adjust ratios/seed, opt into training-fitted
numeric median / categorical mode filling, or select an existing split column.
Random splitting assumes independent rows. Repeated people or time-dependent
data need suitable existing splits; group/time splitting is a follow-up.
**Upload an already prepared numeric CSV** retains the original numeric feature,
integer target and explicit split contract. The downloadable 120-row fixture
uses 80/20/20 existing rows; select its `split` column to preserve those counts.

For the current demo, select **the original Downloads `drug200.csv`**, target
`Drug`, and preview. Default treatment yields two numeric features and one-hot
`Sex`, `BP`, `Cholesterol`, nine encoded features in total, with 140 training,
30 validation and 30 test rows. Review or edit those encodings in the app, save,
then train. No prepared-copy upload or external editing is required. The
[earlier drug200 run](../evidence/2026-10-19-drug200-demo/README.md) retains its
historical prepared-copy evidence; it does not prove this newer raw importer.

After an uncertain save, **Check / retry same save** retains the original file and
exact settings in this tab. The server replays the same dataset version. Reset
only to intentionally start a different import; reloading requires selecting the
original file again. Existing saved versions stay immutable; use a new version
for revised encoding.

### Drop input columns

Select a CSV and its target, then uncheck unwanted inputs under **Choose input
columns** before **Preview encoding**. This also lets you exclude missing-value
or high-cardinality inputs that would otherwise prevent encoding. Target and
selected existing-split columns are protected. Keep at least one input.

For a saved dataset, choose **Edit columns**, enter a new version such as `v2`,
and uncheck inputs. **Preview column changes** shows what will be dropped, the
remaining feature count and unchanged split counts. Choose **Review & save**,
then **Save as new version**. Cancel leaves the original dataset unchanged.
For categorical inputs, original names represent complete encoded groups:
dropping `BP` removes all its one-hot features. Retained values, fitted mappings,
class IDs, row order and split assignments stay the same. Existing runs retain
their original dataset; train a new run to use the edited version.

Changing the selection or destination version requires a new preview. A lost
save response offers **Check / retry same column save**. That exact request is
remembered per project in this browser session; after reloading, verify the same
project is selected and use the recovery button. Existing exact saves replay even
if the original dataset version was subsequently deleted. Column edits need
uploads enabled and work for both raw-prepared and numeric datasets.

This removes features from the new training-ready CSV. Original/raw-source files
remain for reproducibility; dropping a column does not permanently erase it.
To restore an omitted input, start from the original dataset version. Row/value
editing, renaming and filtering are outside this first column-editing feature.

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

## Delete a dataset or model

Open **Datasets → Delete dataset**, or **Runs → Manage models → Delete model**.
Review the named item and exact counts, then choose **Permanently delete**.
**Back** leaves the item unchanged. Related queued/running/cancelling jobs must
finish first; deletion does not cancel them. Refresh and review again if the
dependency preview changes before confirmation.

Deleting a dataset version erases its training/tuning history, derived registered
versions, observations and checkpoints. Deleting a model erases the definition
and those records across its datasets, keeping dataset inputs. Exclusively used
uploaded dataset files are removed with dataset deletion. Files still needed by
other datasets and operator-owned files outside the uploads area are kept and
reported in the preview. The original file in Downloads is an operator original.
Completed deletion frees the name for a new record with a new ID.

Agent conversations and Python drafts are kept. They may contain copied facts
about records that no longer exist, so recheck sources before using them. Exports,
backups, retained evidence and previously scraped Prometheus history also remain.
Deleting a classifier does not uninstall the local conversation model.

If the response is lost or cleanup fails, use **Check / resume same deletion**.
Refresh preserves that operation in this browser tab. It reuses the original
request/key; do not start a replacement operation to work around partial cleanup.
The tab remembers its selected project; API keys still need re-entry after reload.
New project changes may be blocked until cleanup completes. The dashboard reports
success only after a saved completion receipt. The API has corresponding
[preview, deletion and status routes](../reference/api.md#permanent-dataset-and-model-deletion).

Upgrade the model/tuning/monitoring APIs, worker and scheduler together after
active work drains. Their shared artifact volume holds stable native coordination
locks; the worker still reads uploaded inputs through its read-only mount.

## Stop and preserve data

Use the same Compose files and project name with `stop` to stop services. Do not
delete the uploads volume while dataset records reference it. Rolling back the
dashboard must preserve the uploads mount in the API/worker and the files themselves;
otherwise those records cannot train. Rejected/interrupted staging files are
removed. Published files are retained after uncertain metadata writes; automated
orphan cleanup is deferred. Existing named dataset/artifact volumes and models
are preserved.
