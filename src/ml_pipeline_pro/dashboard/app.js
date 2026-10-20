import { $, state, activeRuns, api, report, notify, showView, restoreSession, restoreProject } from "./core.js";
import { initWorkspace, loadWorkspace } from "./workspace.js";
import { initAgent, loadHistory, renderChat, renderConversationSelect } from "./agent.js";
import { initDeletion } from "./deletion.js";

async function start() {
  restoreProject();
  if (location.port === "8010") $("preview-notice").hidden = false;
  initWorkspace(); initAgent(); restoreSession(); initDeletion(); renderConversationSelect();
  state.renderTrainingRecovery(); state.renderChatRecovery();
  document.querySelectorAll("[data-view]").forEach((node) => node.addEventListener("click", () => showView(node.dataset.view)));
  document.querySelectorAll("[data-close-dialog]").forEach((node) => node.addEventListener("click", () => node.closest("dialog").close()));
  $("intro-upload").addEventListener("click", () => { showView("datasets"); $("dataset-file").focus(); });
  $("review-confirm").addEventListener("click", async () => {
    if (!state.review || $("review-confirm").disabled) return;
    $("review-confirm").disabled = true;
    try { await state.review(); } catch (error) { report(error); }
    finally { $("review-dialog").close(); state.review = null; }
  });
  try {
    const response = await fetch("/dashboard/config.json", { credentials: "same-origin", redirect: "error" });
    if (!response.ok) throw new Error("Dashboard configuration is unavailable.");
    state.config = await response.json();
    if (state.config.grafana_origin !== "http://127.0.0.1:3000") throw new Error("Unsupported Grafana origin.");
    $("upload-limit").textContent = `UTF-8 CSV · Up to ${(state.config.max_upload_bytes / 1_000_000).toFixed(1)} MB · ${state.config.max_dataset_rows.toLocaleString()} rows · Numeric and categorical features`;
    $("upload-submit").disabled = !state.config.uploads_enabled;
    if (!state.config.uploads_enabled) notify("File uploads are unavailable in this stack. Existing registered datasets remain usable.", "warning", "upload-result");
    $("agent-model").textContent = state.config.chat_enabled ? "Local Qwen · on your machine" : "Local agent is not enabled in this stack";
    await loadWorkspace(); if (state.conversation) await loadHistory(); renderChat();
  } catch (error) { report(error); }
  let polling = false;
  setInterval(async () => {
    if (document.hidden || polling) return;
    const running = state.experiments.some((item) => activeRuns.has(item.status)) || state.tuning.some((item) => activeRuns.has(item.status));
    const pending = state.conversation && (state.pendingChat || state.turns.some((turn) => turn.status === "running"));
    if (!running && !pending) return;
    polling = true;
    try { if (running) await loadWorkspace(); if (pending) await loadHistory(); }
    catch (error) { report(error); } finally { polling = false; }
  }, 2000);
  let readingMonitoring = false;
  setInterval(async () => {
    if (document.hidden || readingMonitoring || $("view-monitoring").hidden || !state.selectedVersion) return;
    readingMonitoring = true;
    try { await state.refreshMonitoring(); } catch (error) { report(error); }
    finally { readingMonitoring = false; }
  }, 15000);
}
start();
