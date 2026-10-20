import { $, state, api, el, notify, report } from "./core.js";

let preview = null, overrides = {}, labels = {}, serial = 0, busy = false, pending = null;
const rawMode = () => !$("prepared-upload").checked;
const settingsIds = ["dataset-name", "dataset-version", "dataset-target", "dataset-split", "split-train", "split-validation", "split-test", "split-seed", "impute-missing"];
function invalidate() {
  serial++; preview = null; $("prepare-save").disabled = true;
  $("encoding-review-status").textContent = "Settings changed. Click Preview encoding to review the updated result before saving.";
}
function config() {
  return {
    name: $("dataset-name").value, version: $("dataset-version").value,
    target_column: $("dataset-target").value,
    columns: Object.fromEntries(Object.entries(overrides).filter(([name]) => name !== $("dataset-target").value && name !== $("dataset-split").value)),
    label_mapping: labels, train_percent: Number($("split-train").value),
    validation_percent: Number($("split-validation").value), test_percent: Number($("split-test").value),
    seed: Number($("split-seed").value), split_column: $("dataset-split").value || null,
    impute_missing: $("impute-missing").checked,
  };
}
function body(file, settings) {
  const form = new FormData(); form.append("file", file); form.append("settings", JSON.stringify(settings)); return form;
}
function setBusy(value) {
  busy = value; $("upload-submit").disabled = value || !state.config?.uploads_enabled;
  $("prepare-save").disabled = value || (!preview && !pending);
  $("encoding-reset").disabled = value;
  for (const input of $("upload-form").querySelectorAll("input, select, textarea")) input.disabled = value || Boolean(pending);
}
function numericInput(value, onChange, label) {
  const input = el("input"); input.type = "number"; input.step = "any"; input.value = value;
  input.required = true; input.setAttribute("aria-label", label);
  input.addEventListener("input", () => { onChange(Number(input.value)); invalidate(); }); return input;
}
function render(result) {
  const rows = result.row_counts;
  $("encoding-summary").textContent = `${rows.train} training / ${rows.validation} validation / ${rows.test} test rows · ${result.encoded_width} encoded features`;
  $("encoding-warnings").replaceChildren(...result.warnings.map((warning) => el("p", "", warning)));
  $("encoding-columns").replaceChildren();
  for (const column of result.columns) {
    const card = el("div", "encoding-card"), heading = el("div", "encoding-heading");
    const name = el("strong", "", column.name), select = el("select"); select.setAttribute("aria-label", `Encoding for ${column.name}`);
    for (const [value, label] of [["auto", `Automatic (${column.treatment})`], ["numeric", "Numeric"], ["one_hot", "One-hot categories"], ["mapping", "Custom numeric mapping"], ["exclude", "Exclude column"]]) select.add(new Option(label, value));
    select.value = overrides[column.name]?.treatment || "auto";
    select.addEventListener("change", () => {
      overrides[column.name] = select.value === "mapping" ? { treatment: "mapping", mapping: Object.fromEntries(column.categories.map((category, index) => [category, index])), unknown_value: 0 } : { treatment: select.value };
      invalidate(); render({ ...result, columns: result.columns.map((item) => item.name === column.name ? { ...item, treatment: select.value === "auto" ? column.treatment : select.value } : item) });
    });
    heading.append(name, select); card.append(heading);
    card.append(el("p", "muted-note", `${column.output_columns.length} output columns · ${column.missing_count} missing values · ${column.unknown_count} unseen values`));
    if (column.treatment === "mapping") {
      const option = overrides[column.name] || { treatment: "mapping", mapping: { ...column.mapping }, unknown_value: column.unknown_value };
      overrides[column.name] = option;
      const table = el("div", "encoding-labels");
      for (const category of column.categories) {
        const label = el("label", "", category); label.append(numericInput(option.mapping[category], (value) => { option.mapping[category] = value; }, `${column.name}: ${category}`)); table.append(label);
      }
      const fallback = el("label", "", "Unknown category fallback"); fallback.append(numericInput(option.unknown_value, (value) => { option.unknown_value = value; }, `Unknown fallback for ${column.name}`)); table.append(fallback); card.append(table);
      card.append(el("p", "muted-note", "Your values impose distances between categories. Use one-hot when categories have no meaningful numeric relationship."));
    } else if (column.categories.length) {
      const list = el("div", "encoding-category-list");
      for (const [index, category] of column.categories.entries()) list.append(el("span", "hash-text", `${category} → ${column.output_columns[index] || "excluded"}`));
      card.append(list);
    } else if (column.output_columns.length) card.append(el("p", "hash-text", column.output_columns.join(", ")));
    if (column.fill_value !== null) card.append(el("p", "muted-note", `Training-derived fill: ${column.fill_value}`));
    $("encoding-columns").append(card);
  }
  $("encoding-labels").replaceChildren();
  for (const [name, value] of Object.entries(result.label_mapping)) {
    const label = el("label", "", name), input = numericInput(labels[name] ?? value, (id) => { labels = { ...result.label_mapping, ...labels, [name]: id }; }, `Class ID for ${name}`);
    input.min = 0; input.max = Object.keys(result.label_mapping).length - 1; input.step = 1;
    label.append(input); $("encoding-labels").append(label);
  }
  $("encoding-review").hidden = false;
}

export function initPreparation({ parseHeaders, chooseLegacyFile, uploadLegacyFile, loadWorkspace, renderWorkspace }) {
  const reset = () => {
    if (busy) return;
    overrides = {}; labels = {}; pending = null; invalidate(); $("encoding-review").hidden = true;
    $("prepare-save").textContent = "Save reviewed dataset";
    setBusy(false);
  };
  state.resetPreparation = () => {
    reset(); $("dataset-file").value = ""; $("dataset-name").value = ""; $("dataset-version").value = "v1";
    $("dataset-features").value = ""; $("file-label").textContent = "Choose your original CSV";
    $("file-description").textContent = "Review and edit encoding before saving";
    $("dataset-target").replaceChildren(new Option("Choose a CSV first", ""));
    $("dataset-split").replaceChildren(new Option("Create splits automatically", ""));
    for (const id of ["encoding-columns", "encoding-labels", "encoding-warnings"]) $(id).replaceChildren();
    $("upload-result").hidden = true;
  };
  async function chooseFile() {
    reset(); const file = $("dataset-file").files[0]; if (!file) return;
    $("file-label").textContent = file.name; $("file-description").textContent = `${(file.size / 1000).toFixed(1)} KB · Original CSV selected`;
    if (!$("dataset-name").value) $("dataset-name").value = file.name.replace(/\.csv$/i, "").replace(/[^a-zA-Z0-9_-]/g, "_").slice(0, 80);
    const request = serial, generation = state.generation;
    try {
      if (state.config && file.size > state.config.max_upload_bytes) throw new Error("File exceeds the upload limit.");
      const headers = parseHeaders(await file.slice(0, 65536).text());
      if (request !== serial || generation !== state.generation) return;
      for (const id of ["dataset-target", "dataset-split"]) {
        $(id).replaceChildren(new Option(id === "dataset-target" ? "Choose the prediction target" : "Create splits automatically", ""));
        for (const name of headers) $(id).add(new Option(name, name));
      }
      $("dataset-target").value = headers.includes("target") ? "target" : headers.includes("Drug") ? "Drug" : "";
      if (headers.includes("split")) overrides.split = { treatment: "exclude" };
      if (!rawMode()) { $("dataset-split").value = headers.includes("split") ? "split" : ""; await chooseLegacyFile(); }
    } catch (error) { report(error, "upload-result"); }
  }
  $("dataset-file").addEventListener("change", chooseFile);
  for (const id of settingsIds) $(id).addEventListener("input", () => {
    if (id === "dataset-target") labels = {};
    invalidate();
  });
  $("prepared-upload").addEventListener("change", () => {
    reset(); $("legacy-features").hidden = rawMode(); $("dataset-features").required = !rawMode();
    $("dataset-split").required = !rawMode(); $("upload-submit").textContent = rawMode() ? "Preview encoding" : "Validate & add prepared dataset";
    chooseFile();
  });
  $("encoding-reset").addEventListener("click", reset);
  $("upload-form").addEventListener("submit", async (event) => {
    event.preventDefault(); if (busy || pending) return;
    if (!rawMode()) { await uploadLegacyFile(event); return; }
    const file = $("dataset-file").files[0]; if (!file || !state.config?.uploads_enabled) return;
    const settings = config(), request = ++serial; state.mutations++; setBusy(true);
    try {
      const result = await api("/datasets/preview", { method: "POST", body: body(file, settings), raw: true, timeout: 90000 });
      if (request !== serial) return;
      preview = result; render(result); $("encoding-review-status").textContent = "Review the proposed encoding. You can edit any column or target ID, then refresh the preview.";
      $("prepare-save").textContent = "Save reviewed dataset"; $("upload-result").hidden = true;
    } catch (error) { preview = null; report(error, "upload-result"); }
    finally { state.mutations--; setBusy(false); }
  });
  $("prepare-save").addEventListener("click", async () => {
    if (busy || (!preview && !pending) || !$("upload-form").reportValidity()) return;
    const attempt = pending || { file: $("dataset-file").files[0], settings: { ...config(), reviewed_sha256: preview.preview_sha256 } };
    state.mutations++; setBusy(true);
    try {
      const saved = await api("/datasets/prepare", { method: "POST", body: body(attempt.file, attempt.settings), raw: true, timeout: 90000 });
      pending = null; preview = null; $("prepare-save").textContent = "Dataset saved";
      $("encoding-review-status").textContent = "Saved with this encoding. Use a new dataset version to change preparation.";
      notify(`Dataset verified and saved: ${saved.row_counts.train} training, ${saved.row_counts.validation} validation, ${saved.row_counts.test} test rows. SHA-256 ${saved.sha256}`, "", "upload-result");
      await loadWorkspace(); state.selectedDataset = saved.id; renderWorkspace();
    } catch (error) {
      if (!error.status || error.status >= 500) {
        pending = attempt; $("prepare-save").textContent = "Check / retry same save";
        $("encoding-review-status").textContent = "The save outcome is uncertain. This button retries the same original file and settings; reset only to intentionally begin another import.";
      }
      report(error, "upload-result");
    } finally { state.mutations--; setBusy(false); }
  });
}
