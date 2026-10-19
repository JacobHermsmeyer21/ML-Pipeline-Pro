import { $, state, activeRuns, el, button, api, number, date, badge, modelName, datasetName,
  selectedDataset, selectedModel, fillSelect, store, notify, report, describe, setPending,
  showView, openReview, download, abortReads, restoreSession } from "./core.js";

function updateContext() {
  const dataset = selectedDataset(), model = selectedModel();
  $("chat-context").textContent = dataset ? `${dataset.name}${model ? ` / ${model.name}` : ""}` : "Choose a dataset to get started";
  store("selection", { dataset: state.selectedDataset, model: state.selectedModel });
}
export function renderWorkspace() {
  $("stat-datasets").textContent = state.datasets.length; $("nav-dataset-count").textContent = state.datasets.length;
  $("stat-runs").textContent = state.experiments.length;
  const completed = state.experiments.filter((item) => item.status === "succeeded" && Number.isFinite(item.metrics.validation_f1));
  $("stat-f1").textContent = completed.length ? number(Math.max(...completed.map((item) => item.metrics.validation_f1))) : "—";
  $("stat-active").textContent = state.experiments.filter((item) => activeRuns.has(item.status)).length;
  fillSelect($("training-dataset"), state.datasets, state.selectedDataset, "Choose a dataset", (item) => `${item.name} · ${item.version}`);
  fillSelect($("training-model"), state.models, state.selectedModel, "Choose a model", (item) => item.name);
  $("run-count").textContent = state.experiments.length; $("runs-empty").hidden = state.experiments.length > 0;
  $("runs-body").replaceChildren();
  for (const run of state.experiments) {
    const row = el("tr"), identity = el("td"), status = el("td"), actions = el("td");
    identity.append(el("strong", "", modelName(run.model_id)), el("small", "", `${datasetName(run.dataset_id)} · ${run.id.slice(0, 8)}`));
    status.append(badge(run.status));
    actions.append(button("View →", "text-button", () => showRun(run.id).catch(report)));
    row.append(identity, status, el("td", "teal-text", number(run.metrics.validation_f1)), el("td", "", date(run.created_at)), actions); $("runs-body").append(row);
  }
  $("datasets-list").replaceChildren();
  if (!state.datasets.length) $("datasets-list").append(el("div", "empty-state", "Your first dataset will appear here."));
  for (const dataset of state.datasets) {
    const card = el("article", "record-card"); card.append(el("h3", "", `${dataset.name} / ${dataset.version}`));
    card.append(el("p", "record-meta", `${dataset.feature_columns.length} features · ${dataset.num_classes} classes · ${dataset.row_counts.train} train / ${dataset.row_counts.validation} validation / ${dataset.row_counts.test} test`), el("div", "hash-text", `SHA-256 ${dataset.sha256}`));
    const actions = el("div", "record-actions"); actions.append(button("Use for training →", "text-button", () => {
      state.selectedDataset = dataset.id; renderWorkspace(); showView("runs"); $("training-model").focus();
    })); card.append(actions); $("datasets-list").append(card);
  }
  $("tuning-panel").hidden = !state.tuning.length; $("tuning-list").replaceChildren();
  for (const job of state.tuning.slice(0, 10)) {
    const card = el("article", "record-card"); card.append(el("h3", "", `${modelName(job.model_id)} · ${job.id.slice(0, 8)}`), badge(job.status));
    card.append(el("p", "muted-note", `${job.completed_trials} trials completed · Objective: ${job.objective_metric}`));
    const actions = el("div", "record-actions"); actions.append(button("Inspect trials", "text-button", async () => {
      try { const page = await api(`/tuning-jobs/${encodeURIComponent(job.id)}/trials?limit=50`);
        openReview("Saved tuning trials", page.items.map((trial) => ["Trial " + trial.number, `${trial.status} · ${number(trial.objective_value)}`]), null);
      } catch (error) { report(error); }
    }));
    if (activeRuns.has(job.status)) actions.append(button("Cancel search", "text-button", () => {
      openReview("Cancel this tuning search?", [["Job", job.id], ["Effect", "Request cancellation; completed trials are preserved."]], async () => {
        await api(`/tuning-jobs/${encodeURIComponent(job.id)}/cancel`, { method: "POST" }); await loadWorkspace();
      }, "Request cancellation");
    })); card.append(actions); $("tuning-list").append(card);
  }
  if (state.detail) { const run = state.experiments.find((item) => item.id === state.detail); if (run) renderRunDetail(run); }
  updateContext(); renderTrainingRecovery();
}
let workspacePromise = null;
let versionsRequest = 0;
export function loadWorkspace() {
  if (workspacePromise) return workspacePromise.then(() => loadWorkspace());
  const work = loadCurrentWorkspace(); workspacePromise = work;
  return work.finally(() => { if (workspacePromise === work) workspacePromise = null; });
}
async function loadCurrentWorkspace() {
  state.loading = true; const generation = state.generation;
  try {
    const [datasets, models, experiments, tuning] = await Promise.all([
      api("/datasets?limit=100"), api("/models?limit=100"), api("/experiments?limit=100"), api("/tuning-jobs?limit=100"),
    ]);
    if (generation !== state.generation) return;
    state.datasets = datasets.items; state.models = models.items; state.experiments = experiments.items; state.tuning = tuning.items;
    const previous = state.selectedModel;
    if (!state.datasets.some((item) => item.id === state.selectedDataset)) state.selectedDataset = state.datasets[0]?.id || "";
    if (!state.models.some((item) => item.id === state.selectedModel)) state.selectedModel = state.models[0]?.id || "";
    renderWorkspace(); if (previous !== state.selectedModel || state.versionsForModel !== state.selectedModel) await loadVersions();
    $("service-status").className = "status-chip";
    $("service-status").replaceChildren(el("span", "status-dot"), document.createTextNode("Workspace connected"));
  } catch (error) {
    if (!error.stale) { $("service-status").className = "status-chip error";
      $("service-status").replaceChildren(el("span", "status-dot"), document.createTextNode("Connection unavailable")); report(error); }
  } finally { if (generation === state.generation) state.loading = false; }
}
async function submitTraining(attempt) {
  if (state.trainingBusy) return;
  state.trainingBusy = true; state.mutations++; renderTrainingRecovery();
  try {
    const run = await api("/experiments", { method: "POST", body: attempt.body, headers: { "Idempotency-Key": attempt.key } });
    if (typeof run.id !== "string" || run.dataset_id !== attempt.body.dataset_id || run.model_id !== attempt.body.model_id) throw new Error("The training response did not identify the expected saved run. Check the original submission.");
    setPending("training", null); notify("Training submitted. Your serial worker will process this experiment.");
    await loadWorkspace(); await showRun(run.id);
  } catch (error) {
    if (error.stale) return;
    if (error.details?.experiment_id) {
      const id = error.details.experiment_id; setPending("training", null);
      notify(`Experiment ${id} is saved. Dispatch is temporarily unavailable; check its saved status.`, "warning");
      await loadWorkspace(); await showRun(id).catch(report);
    } else if (!error.status || error.status >= 500 || error.status === 408 || attempt.unknown) {
      setPending("training", { ...attempt, unknown: true }); report(error);
    } else { setPending("training", null); report(error); }
  } finally { state.trainingBusy = false; state.mutations--; renderTrainingRecovery(); }
}
function renderTrainingRecovery() {
  $("training-recovery").hidden = !state.pendingTraining;
  $("train-submit").disabled = Boolean(state.pendingTraining) || state.trainingBusy;
  if (state.pendingTraining) {
    const retry = button("Check / retry same submission", "secondary", () => submitTraining(state.pendingTraining)); retry.disabled = state.trainingBusy;
    $("training-recovery").replaceChildren(document.createTextNode("This training submission is unresolved. Check the original request before starting another run."), retry);
  }
}
async function showRun(id) {
  const run = await api(`/experiments/${encodeURIComponent(id)}`);
  state.detail = id; state.detailSignature = ""; renderRunDetail(run); showView("runs");
  $("run-detail").scrollIntoView({ behavior: "smooth", block: "nearest" });
}
function renderRunDetail(run) {
  const signature = JSON.stringify(run); if (state.detailSignature === signature) return;
  state.detailSignature = signature; const panel = $("run-detail"); panel.hidden = false; panel.replaceChildren();
  const heading = el("div", "panel-title"), text = el("div"); text.append(el("h2", "", modelName(run.model_id)), el("p", "", `Experiment ${run.id}`));
  heading.append(text, badge(run.status)); panel.append(heading);
  const metrics = el("div", "detail-metrics");
  for (const [label, value] of [["Validation F1", run.metrics.validation_f1], ["Validation accuracy", run.metrics.validation_accuracy], ["Selected epoch", run.metrics.best_epoch]]) {
    const metric = el("div", "detail-metric", label); metric.append(el("strong", "", number(value, label === "Selected epoch" ? 0 : 3))); metrics.append(metric);
  }
  panel.append(metrics, el("p", "muted-note", `${datasetName(run.dataset_id)} · ${run.attempts} attempt(s) · Started ${date(run.started_at)}`));
  if (run.error_summary) panel.append(el("p", "error-text", run.error_summary));
  const actions = el("div", "record-actions"); actions.append(button("Ask agent about this run", "secondary", () => {
    $("chat-input").value = `Inspect experiment ${run.id}. Return a verified metrics.validation_f1 fact and guide my next pipeline step in one sentence.`; $("chat-input").focus();
  }));
  for (const artifact of run.artifacts) actions.append(button(`Download ${artifact.name}`, "quiet-button", async () => {
    try {
      const blob = await api(`/experiments/${encodeURIComponent(run.id)}/artifacts/${encodeURIComponent(artifact.name)}`, { raw: true });
      const bytes = await blob.arrayBuffer();
      const hash = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)), (item) => item.toString(16).padStart(2, "0")).join("");
      if (bytes.byteLength !== artifact.size_bytes || hash !== artifact.sha256) throw new Error("Artifact hash or size mismatch. Download stopped.");
      download(blob, artifact.name); notify("Artifact hash and size verified before download.");
    } catch (error) { report(error); }
  }));
  const other = state.experiments.filter((item) => item.id !== run.id && item.dataset_id === run.dataset_id && item.status === "succeeded" && Number.isFinite(item.metrics.validation_f1)).sort((a, b) => b.metrics.validation_f1 - a.metrics.validation_f1)[0];
  if (run.status === "succeeded" && other) actions.append(button("Compare validation results", "quiet-button", async () => {
    try { const comparison = await api(`/experiments/compare?experiment_id=${encodeURIComponent(run.id)}&experiment_id=${encodeURIComponent(other.id)}&metric=validation_f1`);
      openReview("Validation comparison", comparison.experiments.map((item) => [item.id, number(item.metrics.validation_f1)]).concat([["Best validation record", comparison.best_experiment_id]]), null);
    } catch (error) { report(error); }
  })); panel.append(actions);
  if (run.status === "succeeded" && run.test_evaluated) {
    const form = el("form", "form-footer"), label = el("label", "", "Register this completed model version"), input = el("input");
    input.name = "version"; input.value = "v1"; input.pattern = "[a-zA-Z0-9_-]{1,80}"; input.maxLength = 80; input.required = true;
    input.setAttribute("aria-label", "Model version name"); label.append(input);
    const submit = el("button", "secondary", "Register version"); submit.type = "submit"; form.append(label, submit);
    form.addEventListener("submit", async (event) => {
      event.preventDefault(); submit.disabled = true; state.mutations++;
      try { const version = await api(`/models/${encodeURIComponent(run.model_id)}/versions`, { method: "POST", body: { version: input.value, experiment_id: run.id } });
        state.selectedModel = run.model_id; await loadVersions(); state.selectedVersion = version.id; $("monitor-version").value = version.id;
        notify("Model version registered. Inference observations will populate its monitoring graphs.");
      } catch (error) { report(error); } finally { submit.disabled = false; state.mutations--; }
    }); panel.append(form);
  }
}
function parseHeaders(text) {
  text = text.replace(/^\uFEFF/, ""); const result = []; let field = "", quoted = false, closed = false;
  for (let index = 0; index < text.length; index++) {
    const char = text[index];
    if (quoted) { if (char === '"' && text[index + 1] === '"') { field += '"'; index++; }
      else if (char === '"') { quoted = false; closed = true; } else field += char;
    } else if (char === ",") { result.push(field); field = ""; closed = false; }
    else if (char === "\n" || char === "\r") { result.push(field); return result; }
    else if (char === '"' && !field && !closed) quoted = true;
    else if (closed) throw new Error("CSV header contains characters after a closing quote."); else field += char;
  }
  throw new Error("CSV header was not complete within the first 64 KiB.");
}
async function chooseFile() {
  const file = $("dataset-file").files[0]; if (!file) return;
  $("file-label").textContent = file.name; $("file-description").textContent = `${(file.size / 1000).toFixed(1)} KB · CSV selected`;
  if (!$("dataset-name").value) $("dataset-name").value = file.name.replace(/\.csv$/i, "").replace(/[^a-zA-Z0-9_-]/g, "_").slice(0, 80);
  try {
    if (state.config && file.size > state.config.max_upload_bytes) throw new Error("File exceeds the upload limit.");
    const headers = parseHeaders(await file.slice(0, 65536).text());
    $("dataset-features").value = headers.filter((item) => item !== $("dataset-target").value && item !== $("dataset-split").value && /^[a-zA-Z0-9_-]{1,80}$/.test(item)).join(", ");
  } catch (error) { report(error, "upload-result"); }
}
async function uploadFile(event) {
  event.preventDefault(); if (state.uploadBusy) return;
  const file = $("dataset-file").files[0]; if (!file) return;
  if (!state.config?.uploads_enabled) { notify("Dataset uploads are unavailable in this stack.", "warning", "upload-result"); return; }
  if (file.size > state.config.max_upload_bytes) { notify("File exceeds the current upload limit.", "error", "upload-result"); return; }
  const query = new URLSearchParams({ name: $("dataset-name").value, version: $("dataset-version").value, target_column: $("dataset-target").value, split_column: $("dataset-split").value });
  for (const column of $("dataset-features").value.split(",").map((item) => item.trim()).filter(Boolean)) query.append("feature_columns", column);
  state.uploadBusy = true; $("upload-submit").disabled = true; state.mutations++;
  try {
    const dataset = await api(`/datasets/upload?${query}`, { method: "POST", body: file, headers: { "Content-Type": "text/csv" }, raw: true, timeout: 45000 });
    notify(`Dataset verified and saved: ${dataset.row_counts.train} training, ${dataset.row_counts.validation} validation, ${dataset.row_counts.test} test rows. SHA-256 ${dataset.sha256}`, "", "upload-result");
    await loadWorkspace(); state.selectedDataset = dataset.id; renderWorkspace();
  } catch (error) { report(error, "upload-result"); }
  finally { state.uploadBusy = false; state.mutations--; $("upload-submit").disabled = false; }
}
async function loadVersions() {
  const model = state.selectedModel, request = ++versionsRequest;
  state.selectedVersion = ""; state.versions = [];
  fillSelect($("monitor-version"), [], "", "Loading registered versions…", (item) => item.version);
  $("grafana-panels").replaceChildren(); $("diagnose-button").disabled = true;
  const versions = model ? (await api(`/models/${encodeURIComponent(model)}/versions?limit=100`)).items : [];
  if (model !== state.selectedModel || request !== versionsRequest) return;
  state.versions = versions; state.versionsForModel = model;
  if (!versions.some((item) => item.id === state.selectedVersion)) state.selectedVersion = versions[0]?.id || "";
  fillSelect($("monitor-version"), versions, state.selectedVersion, "Choose a registered version", (item) => `${modelName(item.model_id)} / ${item.version}`);
  if (!$("view-monitoring").hidden) await updateMonitoring();
}
function graphCard(title, panelId, version) {
  const card = el("article", "grafana-card"), heading = el("h3", "", title);
  const url = new URL(`/d-solo/mlpp-workspace?orgId=1&panelId=${panelId}&theme=dark&from=now-${$("monitor-range").value}&to=now&refresh=15s`, state.config.grafana_origin);
  url.searchParams.set("var-model_version_id", version);
  const link = el("a", "text-button", "Open panel ↗"); link.href = url.href; link.target = "_blank"; link.rel = "noopener noreferrer"; heading.append(link); card.append(heading);
  if (version && state.project === "demo") { const frame = el("iframe"); frame.title = `${title} for version ${version}`; frame.src = url.href; frame.loading = "lazy"; frame.referrerPolicy = "no-referrer"; card.append(frame); }
  else card.append(el("div", "graph-placeholder", state.project === "demo" ? "Choose a registered model version to load this Grafana panel." : "Grafana is configured for demo. These graphs are unavailable in this project."));
  return card;
}
async function updateMonitoring() {
  const version = state.selectedVersion;
  $("grafana-panels").replaceChildren(); $("diagnose-button").disabled = true; state.monitorDataAvailable = null; if (!state.config) return;
  const fullDashboard = new URL("/d/mlpp-workspace", state.config.grafana_origin);
  for (const [key, value] of Object.entries({ "var-model_version_id": version, from: `now-${$("monitor-range").value}`, to: "now", refresh: "15s", theme: "dark" })) fullDashboard.searchParams.set(key, value);
  $("grafana-open").href = fullDashboard.href; $("grafana-open").hidden = !version || state.project !== "demo";
  for (const [title, id] of [["Inference latency · milliseconds", 1], ["Labeled inference accuracy", 2], ["Errors & declared demo delays", 3]]) $("grafana-panels").append(graphCard(title, id, version));
  $("monitor-summary").textContent = version ? `Version ${version} · Checking latest observations…` : "Select a registered version. A newly trained model has no observations until inference samples are collected.";
  await refreshMonitoringSummary();
}
let monitoringRequest = 0;
async function refreshMonitoringSummary() {
  const version = state.selectedVersion, generation = state.generation, request = ++monitoringRequest;
  if (!version) return;
  const summary = await api(`/monitoring/model-versions/${encodeURIComponent(version)}/summary`);
  if (generation !== state.generation || version !== state.selectedVersion || request !== monitoringRequest) return;
  $("monitor-summary").textContent = summary.availability === "missing" ? "No observations in the latest five minutes. Historical graphs may contain earlier samples in the selected range." : `${summary.sample_count} observations · ${summary.seeded_count} declared artificial delays · Max ${number(summary.max_latency_ms, 1)} ms · ${summary.partial ? "Partial window" : "Complete version window"} · Latest ${date(summary.latest_observed_at)}`;
  $("diagnose-button").disabled = state.diagnosing || summary.availability === "missing";
  state.monitorDataAvailable = summary.availability === "observed" ? version : null;
}
async function diagnose() {
  if (state.diagnosing || !state.selectedVersion) return;
  const version = state.selectedVersion; state.diagnosing = true; $("diagnose-button").disabled = true; state.mutations++;
  $("diagnosis-result").replaceChildren(el("p", "loading-text", "The local model is reading the measured window…"));
  try {
    const result = await api(`/monitoring/model-versions/${encodeURIComponent(version)}/diagnosis`, { method: "POST", timeout: 90000 });
    if (version !== state.selectedVersion) return;
    $("diagnosis-result").replaceChildren(el("span", "message-label", "AI interpretation · review required"), el("p", "", result.generated_advice.interpretation), el("p", "muted-note", "Suggested checks: " + result.generated_advice.proposed_checks.join(", ")), el("p", "hash-text", "Observed evidence: " + result.generated_advice.observation_ids.join(", ")));
  } catch (error) { if (!error.stale) $("diagnosis-result").replaceChildren(el("p", "error-text", describe(error))); }
  finally { state.diagnosing = false; state.mutations--; $("diagnose-button").disabled = state.monitorDataAvailable !== state.selectedVersion; }
}
export function initWorkspace() {
  state.refresh = loadWorkspace; state.renderWorkspace = renderWorkspace;
  state.renderTrainingRecovery = renderTrainingRecovery; state.updateMonitoring = updateMonitoring;
  state.refreshMonitoring = refreshMonitoringSummary;
  $("connection-open").addEventListener("click", () => {
    if (state.mutations) { notify("Let the current request finish before changing workspace.", "warning"); return; }
    $("connection-project").value = state.project; $("connection-key").value = state.key; $("connection-dialog").showModal();
    $("connection-project").focus();
  });
  $("connection-form").addEventListener("submit", async (event) => {
    event.preventDefault(); if (state.mutations) return; abortReads(); state.generation++;
    state.project = $("connection-project").value; state.key = $("connection-key").value; $("connection-key").value = ""; $("connection-dialog").close();
    Object.assign(state, { datasets: [], models: [], experiments: [], tuning: [], versions: [], selectedDataset: "", selectedModel: "", selectedVersion: "", conversation: "", revision: 0, turns: [], detail: "", detailSignature: "", loading: false });
    state.actions.clear(); state.actionReads.clear(); state.actionBusy.clear(); $("run-detail").hidden = true;
    $("grafana-panels").replaceChildren(); $("diagnosis-result").replaceChildren(); $("global-message").hidden = true;
    restoreSession(); renderWorkspace(); state.renderChat(); state.renderConversationSelect(); await loadWorkspace();
    if (state.conversation) await state.loadHistory().catch(report);
  });
  $("training-dataset").addEventListener("change", () => { state.selectedDataset = $("training-dataset").value; updateContext(); });
  $("training-model").addEventListener("change", async () => { state.selectedModel = $("training-model").value; state.selectedVersion = ""; updateContext(); await loadVersions().catch(report); });
  $("model-create-open").addEventListener("click", () => { $("model-dialog").showModal(); $("model-name").focus(); });
  $("model-form").addEventListener("submit", async (event) => {
    event.preventDefault(); if (state.modelBusy) return;
    state.modelBusy = true; const submit = event.submitter; submit.disabled = true; state.mutations++;
    try { const model = await api("/models", { method: "POST", body: { name: $("model-name").value } });
      $("model-dialog").close(); $("model-form").reset(); await loadWorkspace(); state.selectedModel = model.id; renderWorkspace(); await loadVersions(); notify("Model created. Choose your dataset and review training settings.");
    } catch (error) { $("model-dialog").close(); report(error); }
    finally { state.modelBusy = false; submit.disabled = false; state.mutations--; }
  });
  $("training-form").addEventListener("submit", (event) => {
    event.preventDefault(); if (state.pendingTraining) { renderTrainingRecovery(); return; }
    const data = new FormData($("training-form")), config = {};
    for (const key of ["epochs", "batch_size", "learning_rate", "hidden_units", "max_runtime_seconds", "seed"]) config[key] = Number(data.get(key));
    const body = { dataset_id: state.selectedDataset, model_id: state.selectedModel, config };
    openReview("Review your training run", [["Dataset", datasetName(body.dataset_id)], ["Model", modelName(body.model_id)], ...Object.entries(config)], async () => {
      const attempt = { key: crypto.randomUUID(), body, unknown: false }; setPending("training", attempt); await submitTraining(attempt);
    });
  });
  $("refresh-runs").addEventListener("click", loadWorkspace); $("dataset-file").addEventListener("change", chooseFile); $("upload-form").addEventListener("submit", uploadFile);
  $("monitor-version").addEventListener("change", () => { state.selectedVersion = $("monitor-version").value; $("diagnosis-result").replaceChildren(); updateMonitoring().catch(report); });
  $("monitor-range").addEventListener("change", () => updateMonitoring().catch(report)); $("diagnose-button").addEventListener("click", diagnose);
}
