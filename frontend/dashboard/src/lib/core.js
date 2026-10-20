export const $ = (id) => document.getElementById(id);
export const activeRuns = new Set(["queued", "running", "cancel_requested"]);
export const terminalTurns = new Set(["completed", "needs_input", "awaiting_confirmation", "failed", "interrupted"]);
export const state = {
  project: "demo", key: "", generation: 0, config: null, datasets: [], models: [], experiments: [],
  tuning: [], versions: [], selectedDataset: "", selectedModel: "", selectedVersion: "",
  conversation: "", revision: 0, turns: [], actions: new Map(), actionReads: new Set(),
  actionBusy: new Set(), pendingChat: null, pendingTraining: null, chatBusy: false,
  loading: false, mutations: 0, detail: "", detailSignature: "", review: null,
  pendingDeletion: null, deletionBusy: false,
};
const controllers = new Set();
export function el(tag, className = "", text = "") {
  const node = document.createElement(tag); if (className) node.className = className;
  node.textContent = text; return node;
}
export function button(text, className, callback) {
  const node = el("button", className, text); node.type = "button";
  node.addEventListener("click", callback); return node;
}
export function stored(name, fallback = null) {
  try { return JSON.parse(sessionStorage.getItem(`mlpp:${state.project}:${name}`)) ?? fallback; }
  catch { return fallback; }
}
export function store(name, value, project = state.project) {
  try {
    const key = `mlpp:${project}:${name}`;
    if (value === null) sessionStorage.removeItem(key); else sessionStorage.setItem(key, JSON.stringify(value));
  } catch { notify("Browser storage is unavailable. Keep this tab open to retain unresolved request identities.", "warning"); }
}
export function notify(message, kind = "", target = "global-message") {
  const node = $(target); node.className = `notice ${kind}`; node.textContent = message; node.hidden = false;
}
export function describe(error) {
  return `${error.message || "Request could not be completed."}${error.code ? ` (${error.code})` : ""}${error.correlation ? ` · Reference ${error.correlation}` : ""}`;
}
export function report(error, target) { if (!error.stale) notify(describe(error), "error", target); }
export function setPending(kind, value) {
  const name = kind === "chat" ? "pendingChat" : "pendingTraining";
  state[name] = value; store(name, value); state.renderTrainingRecovery?.(); state.renderChatRecovery?.();
}
export function abortReads() { for (const controller of controllers) controller.abort(); }
export async function api(path, { method = "GET", body, headers = {}, timeout = 20000, raw = false } = {}) {
  const generation = state.generation, controller = new AbortController(); controllers.add(controller);
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(`/api/v1${path}`, {
      method, signal: controller.signal, credentials: "same-origin", redirect: "error",
      headers: { "X-Project-ID": state.project, ...(state.key ? { "X-API-Key": state.key } : {}),
        ...(body !== undefined && !raw ? { "Content-Type": "application/json" } : {}), ...headers },
      body: body === undefined ? undefined : raw ? body : JSON.stringify(body),
    });
    const content = raw && method === "GET" && response.ok ? await response.blob() : await response.text();
    if (generation !== state.generation) throw Object.assign(new Error("Workspace changed"), { stale: true });
    let parsed; if (!(content instanceof Blob)) { try { parsed = JSON.parse(content); } catch { parsed = null; } }
    if (!response.ok) throw Object.assign(new Error(parsed?.error?.message || `HTTP ${response.status}`), {
      status: response.status, code: parsed?.error?.code, details: parsed?.error?.details,
      correlation: parsed?.error?.correlation_id || response.headers.get("X-Correlation-ID"),
    });
    if (!(content instanceof Blob) && (!parsed || typeof parsed !== "object" || Array.isArray(parsed))) {
      throw Object.assign(new Error("The service returned an invalid API response. Check the saved request before retrying."), { correlation: response.headers.get("X-Correlation-ID") });
    }
    return content instanceof Blob ? content : parsed;
  } catch (error) {
    if (generation !== state.generation) error.stale = true;
    if (error.name === "AbortError") error.message = "The connection timed out. The server may still be working.";
    throw error;
  } finally { clearTimeout(timer); controllers.delete(controller); }
}
export const number = (value, digits = 3) => Number.isFinite(value) ? value.toFixed(digits) : "—";
export function date(value) {
  const parsed = value ? new Date(value) : null;
  return !parsed || Number.isNaN(parsed.valueOf()) ? "—" : parsed.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}
export function badge(status) { return el("span", `status-badge ${status}`, status.replaceAll("_", " ")); }
export const selectedDataset = () => state.datasets.find((item) => item.id === state.selectedDataset);
export const selectedModel = () => state.models.find((item) => item.id === state.selectedModel);
export const modelName = (id) => state.models.find((item) => item.id === id)?.name || id.slice(0, 10);
export function datasetName(id) {
  const dataset = state.datasets.find((item) => item.id === id);
  return dataset ? `${dataset.name} · ${dataset.version}` : id.slice(0, 10);
}
export function fillSelect(node, items, selected, placeholder, label) {
  node.replaceChildren(new Option(placeholder, ""));
  for (const item of items) node.append(new Option(label(item), item.id));
  node.value = items.some((item) => item.id === selected) ? selected : "";
}
export function download(blob, name) {
  const link = el("a"); link.href = URL.createObjectURL(blob); link.download = name;
  document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}
export function showView(view) {
  const target = view === "experiments" ? "runs" : view;
  document.querySelectorAll(".view-section").forEach((section) => { section.hidden = section.id !== `view-${target}`; });
  document.querySelectorAll(".nav-item").forEach((item) => {
    const selected = item.dataset.view === view; item.classList.toggle("active", selected);
    if (selected) item.setAttribute("aria-current", "page"); else item.removeAttribute("aria-current");
  });
  if (target === "monitoring") state.updateMonitoring?.().catch(report);
  if (view === "experiments") $("runs-body").closest("article").scrollIntoView({ behavior: "smooth", block: "start" });
}
export function valuesList(pairs) {
  const list = el("dl", "key-values");
  for (const [key, value] of pairs) { const item = el("div"); item.append(el("dt", "", key), el("dd", "", String(value))); list.append(item); }
  return list;
}
export function openReview(title, pairs, callback, label = "Start training") {
  $("review-confirm").classList.remove("danger-button");
  $("review-title").textContent = title; $("review-content").replaceChildren(valuesList(pairs));
  $("review-confirm").textContent = label; $("review-confirm").hidden = !callback;
  $("review-confirm").disabled = false; state.review = callback; $("review-dialog").showModal();
}
export function restoreSession() {
  const selection = stored("selection", {});
  state.selectedDataset = selection.dataset || ""; state.selectedModel = selection.model || "";
  state.conversation = stored("conversation", ""); state.pendingChat = stored("pendingChat"); state.pendingTraining = stored("pendingTraining");
  state.pendingDeletion = stored("pendingDeletion"); state.renderDeletionRecovery?.();
  $("project-label").textContent = state.project; $("sidebar-project").textContent = state.project;
}
export function restoreProject() {
  try {
    const project = sessionStorage.getItem("mlpp:active-project");
    if (project && /^[a-zA-Z0-9_-]{1,128}$/.test(project)) state.project = project;
  } catch { /* The default project remains usable without browser storage. */ }
}
export function rememberProject() {
  try { sessionStorage.setItem("mlpp:active-project", state.project); }
  catch { notify("Browser storage is unavailable. Reconnect to this project after refresh.", "warning"); }
}
