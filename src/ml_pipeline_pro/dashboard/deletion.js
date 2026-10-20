import { $, state, api, el, button, openReview, report, notify, store, stored, setPending } from "./core.js";

function saveAttempt(attempt) {
  state.pendingDeletion = attempt; store("pendingDeletion", attempt); renderDeletionRecovery();
}
function matches(result, attempt) {
  return result?.kind === attempt.kind && result?.record_id === attempt.id && typeof result.operation_id === "string";
}
async function finishDeletion(result, attempt) {
  if (!matches(result, attempt) || result.status !== "complete") throw new Error("Deletion is not confirmed complete. Check the original operation.");
  saveAttempt(null);
  if (state.pendingTraining?.body?.[attempt.kind === "datasets" ? "dataset_id" : "model_id"] === attempt.id) setPending("training", null);
  state.detail = ""; state.detailSignature = ""; $("run-detail").hidden = true;
  state.selectedVersion = ""; state.versions = []; state.versionsForModel = "";
  $("grafana-panels").replaceChildren(); $("diagnosis-result").replaceChildren();
  $("monitor-summary").textContent = "Select a registered version to inspect its observations.";
  $("diagnose-button").disabled = true;
  if (attempt.kind === "datasets" && state.selectedDataset === attempt.id) state.selectedDataset = "";
  if (attempt.kind === "models" && state.selectedModel === attempt.id) state.selectedModel = "";
  const field = attempt.kind === "datasets" ? "dataset_id" : "model_id";
  state[attempt.kind] = state[attempt.kind].filter((item) => item.id !== attempt.id);
  state.experiments = state.experiments.filter((item) => item[field] !== attempt.id);
  state.tuning = state.tuning.filter((item) => item[field] !== attempt.id);
  state.renderWorkspace();
  await state.refresh();
  notify(`Permanently deleted ${attempt.name} and its training history. Conversations and drafts are preserved.`);
}
async function submitDeletion(attempt, checkFirst = false) {
  if (state.deletionBusy) return;
  const generation = state.generation;
  state.deletionBusy = true; state.mutations++; renderDeletionRecovery();
  try {
    if (checkFirst && attempt.operation) {
      const saved = await api(`/deletions/${encodeURIComponent(attempt.operation)}`);
      if (!matches(saved, attempt)) throw new Error("Saved deletion does not match this item.");
      if (saved.status === "complete") { await finishDeletion(saved, attempt); return; }
    }
    const result = await api(`/${attempt.kind}/${encodeURIComponent(attempt.id)}`, {
      method: "DELETE", body: attempt.body, headers: { "Idempotency-Key": attempt.key }, timeout: 90000,
    });
    await finishDeletion(result, attempt);
  } catch (error) {
    if (error.stale) return;
    if (!error.status || error.status >= 500 || error.status === 408 || attempt.unknown) {
      const operation = error.status >= 500 ? error.details?.operation_id : null;
      saveAttempt({ ...attempt, ...(operation ? { operation } : {}), unknown: true });
    } else saveAttempt(null);
    report(error);
  } finally {
    state.deletionBusy = false; state.mutations--;
    if (generation === state.generation) renderDeletionRecovery();
  }
}
export async function reviewDeletion(kind, item) {
  if (state.pendingDeletion) { renderDeletionRecovery(); notify("Resolve the saved deletion before starting another.", "warning"); return; }
  if (state.deletionBusy) return;
  const generation = state.generation;
  try {
    const preview = await api(`/${kind}/${encodeURIComponent(item.id)}/deletion-preview`);
    if (preview.kind !== kind || preview.record_id !== item.id) throw new Error("Deletion preview did not match the selected item.");
    const labels = { datasets: "Dataset versions", models: "Models", experiments: "Training runs", tuning_jobs: "Tuning jobs", trials: "Tuning trials", model_versions: "Registered versions", monitoring_observations: "Monitoring observations", files: "Files erased", shared_files: "Shared files kept", unmanaged_files: "Operator files kept" };
    const pairs = [["Item", `${preview.name}${preview.version ? " / " + preview.version : ""}`]];
    for (const [field, label] of Object.entries(labels)) pairs.push([label, preview.counts[field]]);
    pairs.push(["Effect", "Permanently erase the listed training history and owned files. This cannot be undone."],
      ["Kept", "Agent conversations and Python drafts, shared inputs, operator originals, exports and previously scraped metrics."],
      ["Active jobs", preview.active_jobs ? `${preview.active_jobs} — wait for these jobs to finish, then review again.` : "None"]);
    if (generation !== state.generation) return;
    openReview("Permanently delete this item?", pairs, preview.active_jobs ? null : async () => {
      if (generation !== state.generation) return;
      const attempt = { kind, id: item.id, name: preview.name, key: crypto.randomUUID(), body: { preview_sha256: preview.preview_sha256 }, unknown: false };
      saveAttempt(attempt); await submitDeletion(attempt);
    }, "Permanently delete");
    $("review-confirm").classList.add("danger-button");
  } catch (error) { report(error); }
}
export function renderDeletionRecovery() {
  const panel = $("deletion-recovery"), attempt = state.pendingDeletion;
  panel.hidden = !attempt || (state.deletionBusy && !attempt.unknown); panel.replaceChildren();
  if (!attempt) return;
  panel.append(el("strong", "", "Deletion needs confirmation"), el("p", "", `${attempt.name}: cleanup may be incomplete. Check and resume the original deletion before starting another.`));
  const retry = button("Check / resume same deletion", "secondary", () => submitDeletion(state.pendingDeletion, true));
  retry.disabled = state.deletionBusy; panel.append(retry);
}
function manageModels() {
  const list = $("models-list"); list.replaceChildren();
  if (!state.models.length) list.append(el("p", "muted-note", "Create a model to begin."));
  for (const model of state.models) {
    const card = el("article", "record-card"); card.append(el("h3", "", model.name));
    card.append(el("p", "muted-note", `${model.framework} · ${model.architecture} · ${model.task}`));
    card.append(button("Delete model", "text-button danger-text", () => { $("models-dialog").close(); reviewDeletion("models", model); }));
    list.append(card);
  }
  $("models-dialog").showModal();
}
export function initDeletion() {
  state.renderDeletionRecovery = renderDeletionRecovery;
  state.pendingDeletion = stored("pendingDeletion"); renderDeletionRecovery();
  $("models-manage-open").addEventListener("click", manageModels);
}
