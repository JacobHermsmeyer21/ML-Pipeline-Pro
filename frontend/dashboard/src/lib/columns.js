import { $, state, api, el, notify, report, openReview, stored, store, button } from "./core.js";

let source = null, preview = null, busy = false, serial = 0;
function pending(value) { state.pendingColumns = value; store("pendingColumns", value); renderRecovery(); }
function renderRecovery() {
  const node = $("column-recovery"); node.replaceChildren(); node.hidden = !state.pendingColumns;
  if (!state.pendingColumns) return;
  node.append(el("p", "", "A column edit has an uncertain outcome. Check / retry the exact saved request before starting another edit."));
  const retry = button("Check / retry same column save", "secondary", () => save(state.pendingColumns));
  retry.disabled = busy; node.append(retry);
}
function setBusy(value) {
  busy = value;
  for (const node of $("column-form").querySelectorAll("input, button")) node.disabled = value;
  $("column-save").disabled = value || !preview;
  renderRecovery();
}
function invalidate() {
  serial++; preview = null; $("column-save").disabled = true;
  $("column-preview-result").textContent = "Preview your selection before saving a new version.";
}
async function save(attempt) {
  if (busy || !attempt) return;
  const generation = state.generation; setBusy(true); state.mutations++;
  try {
    const saved = await api(`/datasets/${encodeURIComponent(attempt.id)}/columns`, { method: "POST", body: attempt.body, timeout: 90000 });
    pending(null); $("column-dialog").close(); source = null; preview = null;
    await state.refresh();
    state.selectedDataset = saved.id; state.renderWorkspace();
    notify(`Saved ${saved.name} / ${saved.version} with ${saved.feature_columns.length} features. Original versions and training runs are preserved.`);
  } catch (error) {
    if (error.stale) return;
    if (!error.status || error.status >= 500 || error.status === 408 || attempt.unknown) pending({ ...attempt, unknown: true });
    else { pending(null); invalidate(); }
    report(error);
  } finally {
    state.mutations--; busy = false;
    if (generation === state.generation) setBusy(false);
  }
}
export async function editColumns(dataset) {
  if (busy) return;
  if (state.pendingColumns) { renderRecovery(); notify("Resolve the saved column edit before starting another.", "warning"); return; }
  const generation = state.generation, request = ++serial;
  try {
    const details = await api(`/datasets/${encodeURIComponent(dataset.id)}/columns`);
    if (generation !== state.generation || request !== serial) return;
    source = details; invalidate(); $("column-version").value = "";
    $("column-parent").textContent = `${details.name} / ${details.version}. Save an edited copy under a new version.`;
    $("column-choices").replaceChildren();
    for (const column of details.columns) {
      const label = el("label", "check-field column-choice"), input = el("input");
      input.type = "checkbox"; input.checked = true; input.value = column.name; input.setAttribute("aria-label", `Keep ${column.name}`);
      input.addEventListener("change", invalidate);
      label.append(input, el("span", "", column.name), el("small", "muted-note", `${column.output_columns.length} encoded feature${column.output_columns.length === 1 ? "" : "s"}`));
      $("column-choices").append(label);
    }
    $("column-protected").textContent = `Protected: ${details.target_column} (target), ${details.split_column} (split). Rows, labels and splits stay the same. Original source files are retained for reproducibility.`;
    setBusy(false); $("column-dialog").showModal(); $("column-version").focus();
  } catch (error) { report(error); }
}
export function initColumns() {
  state.pendingColumns = stored("pendingColumns"); renderRecovery();
  state.resetColumns = () => {
    serial++; source = null; preview = null; $("column-dialog").close();
    state.pendingColumns = stored("pendingColumns"); renderRecovery();
  };
  $("column-dialog").addEventListener("close", () => { serial++; preview = null; });
  $("column-version").addEventListener("input", invalidate);
  $("column-form").addEventListener("submit", async (event) => {
    event.preventDefault(); if (busy || !source) return;
    const drops = [...$("column-choices").querySelectorAll("input:not(:checked)")].map((input) => input.value);
    if (!drops.length || drops.length === source.columns.length) { notify("Drop at least one input and keep at least one input.", "warning"); return; }
    const body = { version: $("column-version").value, drop_columns: drops, source_sha256: source.source_sha256 };
    const request = ++serial, generation = state.generation; setBusy(true); state.mutations++;
    try {
      const result = await api(`/datasets/${encodeURIComponent(source.dataset_id)}/columns/preview`, { method: "POST", body, timeout: 90000 });
      if (request !== serial || generation !== state.generation) return;
      preview = { id: source.dataset_id, body: { ...body, reviewed_sha256: result.preview_sha256 } };
      const counts = result.row_counts;
      $("column-preview-result").textContent = `Drop: ${drops.join(", ")}. Keep: ${result.kept_columns.map((item) => item.name).join(", ")}. ${source.encoded_width} → ${result.encoded_width} encoded features. ${counts.train} train / ${counts.validation} validation / ${counts.test} test rows, unchanged.`;
    } catch (error) { preview = null; report(error); }
    finally { state.mutations--; if (generation === state.generation) setBusy(false); else busy = false; }
  });
  $("column-save").addEventListener("click", () => {
    if (busy || !preview) return;
    const attempt = structuredClone(preview), generation = state.generation;
    openReview("Save dataset column selection?", [["Dataset", source.name], ["New version", attempt.body.version], ["Drop", attempt.body.drop_columns.join(", ")], ["Result", $("column-preview-result").textContent]], async () => {
      if (generation !== state.generation) return;
      pending(attempt); await save(attempt);
    }, "Save as new version");
  });
}
