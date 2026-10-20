import { $, state, terminalTurns, el, button, api, stored, store, notify, report, describe,
  setPending, date, download, selectedDataset, selectedModel, showView } from "./core.js";
import { validationExplanation } from "./reply-errors.js";

const welcome = $("chat-messages").firstElementChild.cloneNode(true);
function rememberConversation(id) {
  const ids = stored("conversations", []).filter((item) => typeof item === "string" && item !== id);
  store("conversations", [id, ...ids].slice(0, 20)); store("conversation", id); renderConversationSelect();
}
export function renderConversationSelect() {
  const select = $("conversation-select"); select.replaceChildren(new Option("New conversation", ""));
  for (const id of stored("conversations", []).slice(0, 20)) if (typeof id === "string") select.append(new Option(`Conversation ${id.slice(0, 8)}`, id));
  select.value = state.conversation;
}
function renderRecovery() {
  $("chat-recovery").hidden = !state.pendingChat;
  if (state.pendingChat) {
    const check = button("Check saved turn", "secondary", checkPending); check.disabled = state.chatBusy;
    $("chat-recovery").replaceChildren(document.createTextNode("This turn may still be running. Check its saved result using the original request identity."), check);
  }
  $("chat-send").disabled = state.chatBusy || Boolean(state.pendingChat);
  $("new-chat").disabled = state.chatBusy || Boolean(state.pendingChat);
  $("conversation-select").disabled = state.chatBusy || Boolean(state.pendingChat);
}
export function renderChat() {
  const log = $("chat-messages"); log.replaceChildren();
  if (!state.turns.length && !state.pendingChat) { log.append(welcome.cloneNode(true)); bindStarters(log); }
  for (const turn of state.turns) {
    const user = el("div", "chat-message user"); user.append(el("span", "message-label", "You"), el("p", "", turn.user_message)); log.append(user);
    const assistant = el("div", "chat-message assistant"); assistant.append(el("span", "message-label", "Pipeline agent"), el("p", "", turn.message || (turn.status === "running" ? "Working with your saved records…" : turn.error?.message || "No message was saved.")));
    if (turn.required_inputs?.length) assistant.append(el("p", "muted-note", "Needed: " + turn.required_inputs.join(", ")));
    if (turn.facts?.length) { const facts = el("div", "facts-list");
      for (const fact of turn.facts) facts.append(el("div", "fact", `${fact.field}: ${typeof fact.value === "object" ? JSON.stringify(fact.value) : fact.value} · ${fact.record_id}`));
      assistant.append(facts);
    }
    if (turn.error) {
      assistant.append(el("p", "error-text", `${turn.error.code || turn.status}: ${turn.error.message || "The saved turn did not complete."}`));
      const explanation = validationExplanation(turn.error);
      if (explanation) assistant.append(el("p", "error-text", explanation));
      if (turn.correlation_id) assistant.append(el("p", "muted-note", `Reference: ${turn.correlation_id}`));
    }
    if (turn.snippet) {
      const draft = el("div", "snippet-card"); draft.append(el("h4", "", "Generated Python draft"), el("p", "", `${turn.snippet.status} · Review before use. Never executed here.`));
      if (turn.snippet.code) {
        draft.append(el("pre", "", turn.snippet.code));
        draft.append(button("Copy draft", "text-button", async () => {
          try { await navigator.clipboard.writeText(turn.snippet.code); notify("Draft copied. Review it before use."); }
          catch { notify("Clipboard unavailable. Select and copy the visible draft.", "warning"); }
        }), button("Download draft", "text-button", () => download(new Blob([turn.snippet.code], { type: "text/plain" }), "pipeline-draft.py")));
      }
      if (turn.snippet.validation_issues?.length) draft.append(el("p", "error-text", turn.snippet.validation_issues.join(", ")));
      assistant.append(draft);
    }
    if (turn.pending_action) assistant.append(renderAction(turn.pending_action));
    log.append(assistant);
  }
  const pending = state.pendingChat;
  if (pending && !state.turns.some((turn) => turn.request_id === pending.body.request_id)) {
    const user = el("div", "chat-message user");
    user.append(el("span", "message-label", "You"), el("p", "", pending.body.message));
    const waiting = el("p", "loading-text", state.chatBusy ? "Reading your records on this machine…" : "A saved reply has not been confirmed yet. Check the original turn below.");
    log.append(user, waiting);
  }
  if (state.turns.length === 50) log.prepend(el("p", "muted-note", "Showing the latest 50 saved turns."));
  log.scrollTop = state.turns.length || pending ? log.scrollHeight : 0;
}
function renderAction(snapshot) {
  const action = state.actions.get(snapshot.action_id), shown = action || snapshot;
  const card = el("div", "action-card"); card.append(el("h4", "", shown.tool.name.replaceAll("_", " ")));
  card.append(el("p", "", action ? `Saved action: ${shown.status.replaceAll("_", " ")} · Expires ${date(shown.expires_at)}` : "Checking the saved action before enabling decisions…"), el("pre", "", JSON.stringify(shown.tool.arguments, null, 2)));
  const controls = el("div", "action-buttons");
  if (action && ["pending_confirmation", "unknown"].includes(action.status)) {
    const expired = Date.parse(action.expires_at) <= Date.now() && action.status === "pending_confirmation";
    const approve = button(action.status === "unknown" ? "Retry same approved action" : "Approve action", "primary", () => decide(action, "approve"));
    const exhausted = action.status === "unknown" && action.attempts.length >= 3;
    approve.disabled = expired || exhausted || state.actionBusy.has(action.action_id); controls.append(approve);
    if (exhausted) card.append(el("p", "error-text", "The saved action's attempt limit has been reached. Check its saved state; do not create a replacement automatically."));
    if (action.status === "pending_confirmation") { const reject = button("Reject", "quiet-button", () => decide(action, "reject")); reject.disabled = expired || state.actionBusy.has(action.action_id); controls.append(reject); }
    if (expired) card.append(el("p", "muted-note", "This proposal has expired. Check its saved state."));
  }
  controls.append(button("Check saved state", "text-button", () => refreshAction(snapshot).catch(report))); card.append(controls);
  if (shown.outcome?.data?.id) card.append(el("p", "hash-text", `Saved outcome record: ${shown.outcome.data.id}`));
  const explanation = validationExplanation(shown.outcome?.error);
  if (explanation) card.append(el("p", "error-text", explanation));
  if (shown.status === "unknown") card.append(el("p", "error-text", "Submission is uncertain. Only an explicit retry of this same action can resolve it. A new job is not generated automatically."));
  if (!action && !state.actionReads.has(snapshot.action_id)) refreshAction(snapshot).catch(report);
  return card;
}
async function refreshAction(snapshot) {
  if (state.actionReads.has(snapshot.action_id)) return;
  state.actionReads.add(snapshot.action_id);
  try {
    const action = await api(`/conversations/${encodeURIComponent(snapshot.conversation_id)}/actions/${encodeURIComponent(snapshot.action_id)}`);
    state.actions.set(action.action_id, action); renderChat();
  } finally { state.actionReads.delete(snapshot.action_id); }
}
async function decide(shown, decision) {
  if (state.actionBusy.has(shown.action_id)) return;
  state.actionBusy.add(shown.action_id); state.mutations++; renderChat();
  try {
    const path = `/conversations/${encodeURIComponent(shown.conversation_id)}/actions/${encodeURIComponent(shown.action_id)}`;
    const current = await api(path); state.actions.set(current.action_id, current);
    if (current.arguments_hash !== shown.arguments_hash) throw new Error("The proposal changed. Review its saved arguments again.");
    if (!(current.status === "pending_confirmation" || (decision === "approve" && current.status === "unknown"))) { notify(`Saved action is already ${current.status.replaceAll("_", " ")}.`); return; }
    const result = await api(path + "/decision", { method: "POST", body: { decision, arguments_hash: shown.arguments_hash } });
    state.actions.set(result.action_id, result); notify(`Saved action: ${result.status.replaceAll("_", " ")}.`);
    await state.refresh(); await loadHistory();
  } catch (error) {
    report(error); await refreshAction(shown).catch(() => { notify("Decision delivery is uncertain. Check the same saved action before retrying.", "warning"); });
  } finally { state.mutations--; state.actionBusy.delete(shown.action_id); renderChat(); }
}
export async function loadHistory() {
  const conversation = state.conversation; if (!conversation) return;
  let history = await api(`/conversations/${encodeURIComponent(conversation)}?limit=50`);
  if (history.revision > 50) history = await api(`/conversations/${encodeURIComponent(conversation)}?limit=50&offset=${history.revision - 50}`);
  if (conversation !== state.conversation) return;
  state.revision = history.revision; state.turns = history.turns;
  const pending = state.pendingChat;
  if (pending && history.turns.some((turn) => turn.request_id === pending.body.request_id && terminalTurns.has(turn.status))) setPending("chat", null);
  renderChat(); renderRecovery();
}
function adoptTurn(turn) {
  state.conversation = turn.conversation_id; state.revision = Math.max(state.revision, turn.revision); rememberConversation(turn.conversation_id);
  const index = state.turns.findIndex((item) => item.turn_id === turn.turn_id);
  if (index < 0) state.turns.push(turn); else state.turns[index] = turn;
  if (terminalTurns.has(turn.status)) setPending("chat", null); renderChat(); renderRecovery();
}
async function sendChat(attempt) {
  if (state.chatBusy) return;
  state.chatBusy = true; state.mutations++; renderRecovery(); renderChat();
  try {
    const turn = await api("/chat", { method: "POST", body: attempt.body, timeout: 90000 });
    if (turn.request_id !== attempt.body.request_id || typeof turn.conversation_id !== "string" || !Number.isInteger(turn.revision) || !(terminalTurns.has(turn.status) || turn.status === "running")) throw new Error("The chat response did not identify the expected saved turn. Check its original request.");
    adoptTurn(turn); await loadHistory();
  }
  catch (error) {
    if (error.stale || state.pendingChat?.body.request_id !== attempt.body.request_id) return;
    if (error.details?.conversation_id) { state.conversation = error.details.conversation_id; rememberConversation(state.conversation); }
    if (error.status && error.status < 500 && error.status !== 408 && !attempt.unknown) {
      setPending("chat", null); if (state.conversation) await loadHistory().catch(() => {});
    } else setPending("chat", { ...attempt, unknown: true });
    report(error);
  } finally { state.chatBusy = false; state.mutations--; renderRecovery(); }
}
async function checkPending() {
  if (state.chatBusy || !state.pendingChat) return;
  try { if (state.conversation) await loadHistory(); if (state.pendingChat) await sendChat(state.pendingChat); }
  catch (error) { report(error); }
}
function bindStarters(parent) {
  parent.querySelectorAll("[data-prompt]").forEach((node) => node.addEventListener("click", () => {
    const dataset = selectedDataset(), model = selectedModel(); let prompt;
    if (node.dataset.prompt === "python") prompt = "Generate Python listing experiments, limit 50, offset 0. Do not execute.";
    else if (!dataset) { notify("Choose or upload a dataset first.", "warning"); showView("datasets"); return; }
    else if (node.dataset.prompt === "inspect") prompt = `Inspect dataset ${dataset.id}. Return verified row_counts.train and row_counts.validation facts and guide my next pipeline step.`;
    else if (!model) { notify("Select or create a model before planning training.", "warning"); showView("runs"); return; }
    else prompt = `Train dataset ${dataset.id} with model ${model.id}. Per-trial runtime is 10 seconds. Do not submit it.`;
    $("chat-input").value = prompt; $("chat-input").focus();
  }));
}
export function initAgent() {
  state.renderChat = renderChat; state.loadHistory = loadHistory; state.renderConversationSelect = renderConversationSelect; state.renderChatRecovery = renderRecovery;
  $("chat-form").addEventListener("submit", async (event) => {
    event.preventDefault(); if (state.chatBusy || state.pendingChat) return;
    const message = $("chat-input").value.trim(); if (!message) return;
    if (new TextEncoder().encode(message).length > 8192) { notify("Message exceeds the 8 KiB text limit.", "error"); return; }
    const body = { request_id: crypto.randomUUID(), message, expected_revision: state.revision, ...(state.conversation ? { conversation_id: state.conversation } : {}) };
    const attempt = { body, unknown: false }; setPending("chat", attempt); $("chat-input").value = ""; await sendChat(attempt);
  });
  $("new-chat").addEventListener("click", () => {
    if (state.chatBusy || state.pendingChat) return;
    state.conversation = ""; state.revision = 0; state.turns = []; store("conversation", null); state.actions.clear(); renderConversationSelect(); renderChat();
  });
  $("conversation-select").addEventListener("change", async () => {
    if (state.chatBusy || state.pendingChat) { renderConversationSelect(); return; }
    state.conversation = $("conversation-select").value; state.revision = 0; state.turns = []; state.actions.clear(); store("conversation", state.conversation); renderChat();
    if (state.conversation) await loadHistory().catch(report);
  });
  bindStarters(document);
}
