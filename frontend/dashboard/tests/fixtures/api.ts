import type { Page, Route } from "@playwright/test";

// Shapes follow the Pydantic response models in src/ml_pipeline_pro (schemas.py,
// column_schemas.py, deletion_schemas.py, conversation_schemas.py, monitoring_schemas.py).
const now = "2026-10-19T12:00:00Z";
const later = "2099-01-01T00:00:00Z";
const hash = (seed: string) => seed.repeat(64).slice(0, 64);
const audit = (id: string) => ({ id, project_id: "demo", schema_version: 1, created_at: now, updated_at: now });
const counts = { datasets: 1, models: 0, experiments: 2, tuning_jobs: 0, trials: 0, model_versions: 0,
  monitoring_observations: 0, files: 3, size_bytes: 2048, shared_files: 0, unmanaged_files: 0 };

export const dataset = (overrides: Record<string, unknown> = {}) => ({
  ...audit("ds_1"), name: "customer_outcomes", version: "v1", uri: "uploads/customer_outcomes.csv",
  feature_columns: ["feature_1", "feature_2"], target_column: "target", split_column: "split",
  sha256: hash("a"), num_classes: 2, row_counts: { train: 80, validation: 20, test: 20 },
  preparation: null, selection: null, ...overrides,
});
export const model = (overrides: Record<string, unknown> = {}) => ({
  ...audit("md_1"), name: "baseline_mlp", framework: "pytorch", task: "classification", architecture: "mlp", ...overrides,
});
const config = { epochs: 30, batch_size: 16, learning_rate: 0.01, hidden_units: 16, max_runtime_seconds: 60, seed: 42 };
export const experiment = (id: string, status: string, overrides: Record<string, unknown> = {}) => ({
  ...audit(id), dataset_id: "ds_1", model_id: "md_1", config, status, attempts: 1, heartbeat_at: null,
  started_at: now, completed_at: status === "succeeded" ? now : null,
  metrics: status === "succeeded" ? { validation_f1: 0.912, validation_accuracy: 0.925, best_epoch: 12 } : {},
  artifacts: [], dependencies: {}, error_summary: null, tuning_job_id: null, tuning_trial_number: null,
  test_evaluated: false, ...overrides,
});
export const experimentCompleted = experiment("ex_done_000001", "succeeded");
export const experimentRunning = experiment("ex_run_0000002", "running");

const columnsFor = (id: string) => ({
  dataset_id: id, name: "customer_outcomes", version: "v1", source_sha256: hash("b"),
  columns: [{ name: "feature_1", output_columns: ["feature_1"] }, { name: "feature_2", output_columns: ["feature_2"] }],
  target_column: "target", split_column: "split", row_counts: { train: 80, validation: 20, test: 20 }, encoded_width: 2,
});
const preparationPreview = {
  row_counts: { train: 84, validation: 18, test: 18 }, encoded_width: 2, warnings: [], preview_sha256: hash("c"),
  label_mapping: { "0": 0, "1": 1 },
  columns: ["feature_1", "feature_2"].map((name) => ({ name, treatment: "numeric", categories: [], output_columns: [name],
    missing_count: 0, unknown_count: 0, fill_value: null })),
};
export const actionProposal = (status = "pending_confirmation") => ({
  action_id: "ac_1", conversation_id: "cv_1", turn_id: "tn_1", revision: 1, status,
  tool: { name: "submit_training", arguments: { dataset_id: "ds_1", model_id: "md_1" } },
  arguments_hash: hash("d"), argument_origin: "model_proposed", expires_at: later, decision: null, attempts: [], outcome: null,
});
export const conversationTurn = (request_id: string, message: string) => ({
  conversation_id: "cv_1", turn_id: "tn_1", request_id, revision: 1, status: "awaiting_confirmation",
  user_message: message, message: "I can submit this training run after you approve it.", correlation_id: "co_1",
  required_inputs: [], facts: [], evidence: [], tool_results: [], pending_action: actionProposal(),
  snippet: null, history_omitted: false, error: null, model_provenance: {},
});

export type ApiState = {
  config: Record<string, unknown>;
  datasets: Record<string, unknown>[];
  models: Record<string, unknown>[];
  experiments: Record<string, unknown>[];
  tuning: Record<string, unknown>[];
  failExperimentPost: number | null;
};
export type LoggedRequest = { method: string; path: string; headers: Record<string, string>; body: string | null };
export type ApiLog = { requests: LoggedRequest[]; count: (method: string, path: RegExp) => number };

const json = (route: Route, body: unknown, status = 200) =>
  route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
const page = (items: unknown[]) => ({ items, limit: 100, offset: 0 });

export async function mockApi(target: Page, overrides: Partial<ApiState> = {}): Promise<ApiLog> {
  const state: ApiState = {
    config: { uploads_enabled: true, max_upload_bytes: 10_000_000, max_dataset_rows: 100_000,
      grafana_origin: "http://127.0.0.1:3000", chat_enabled: true, chat_backend: "ollama", chat_model: "qwen2.5:7b" },
    datasets: [dataset()], models: [model()], experiments: [experimentCompleted], tuning: [], failExperimentPost: null,
    ...overrides,
  };
  const requests: LoggedRequest[] = [];
  let turns: unknown[] = [];
  let action = actionProposal();
  await target.route("**/dashboard/config.json", (route) => json(route, state.config));
  await target.route("**/api/v1/**", async (route) => {
    const request = route.request(), url = new URL(request.url()), method = request.method();
    const path = url.pathname.replace("/api/v1", "");
    requests.push({ method, path, headers: request.headers(), body: request.postData() });
    const is = (verb: string, pattern: RegExp) => method === verb && pattern.test(path);
    if (is("GET", /^\/datasets$/)) return json(route, page(state.datasets));
    if (is("GET", /^\/models$/)) return json(route, page(state.models));
    if (is("GET", /^\/experiments$/)) return json(route, page(state.experiments));
    if (is("GET", /^\/tuning-jobs$/)) return json(route, page(state.tuning));
    if (is("GET", /^\/models\/[^/]+\/versions$/)) return json(route, page([]));
    if (is("GET", /^\/experiments\/[^/]+$/)) {
      const id = decodeURIComponent(path.split("/")[2]);
      return json(route, state.experiments.find((item) => item.id === id) ?? experiment(id, "queued"));
    }
    if (is("POST", /^\/experiments$/)) {
      if (state.failExperimentPost) return json(route, { error: { code: "unavailable", message: "Queue unavailable", correlation_id: "co_fail" } }, state.failExperimentPost);
      const body = JSON.parse(request.postData() ?? "{}");
      const created = experiment("ex_new_0000003", "queued", { dataset_id: body.dataset_id, model_id: body.model_id });
      state.experiments = [created, ...state.experiments];
      return json(route, created, 202);
    }
    if (is("POST", /^\/models$/)) return json(route, model({ id: "md_new", name: "new_model" }), 201);
    if (is("POST", /^\/datasets\/preview$/)) return json(route, preparationPreview);
    if (is("POST", /^\/datasets\/prepare$/)) return json(route, dataset({ id: "ds_new", version: "v2" }), 201);
    if (is("GET", /^\/datasets\/[^/]+\/columns$/)) return json(route, columnsFor(path.split("/")[2]));
    if (is("POST", /^\/datasets\/[^/]+\/columns\/preview$/)) {
      const body = JSON.parse(request.postData() ?? "{}"), source = columnsFor(path.split("/")[2]);
      const kept = source.columns.filter((column) => !body.drop_columns.includes(column.name));
      return json(route, { source, version: body.version, drop_columns: body.drop_columns, kept_columns: kept,
        feature_columns: kept.map((column) => column.name), encoded_width: kept.length, row_counts: source.row_counts, preview_sha256: hash("e") });
    }
    if (is("POST", /^\/datasets\/[^/]+\/columns$/)) return json(route, dataset({ id: "ds_v2", version: "v2", feature_columns: ["feature_1"] }), 201);
    if (is("GET", /^\/(datasets|models)\/[^/]+\/deletion-preview$/)) {
      const [, kind, id] = path.split("/"), record = (kind === "models" ? state.models : state.datasets).find((item) => item.id === id);
      return json(route, { kind, record_id: id, name: record?.name ?? id, version: (record?.version as string) ?? null,
        preview_sha256: hash("f"), counts, active_jobs: 0 });
    }
    if (is("DELETE", /^\/(datasets|models)\/[^/]+$/)) {
      const [, kind, id] = path.split("/");
      if (kind === "models") state.models = state.models.filter((item) => item.id !== id);
      else state.datasets = state.datasets.filter((item) => item.id !== id);
      return json(route, { operation_id: "op_1", kind, record_id: id, status: "complete", counts, created_at: now, completed_at: now });
    }
    if (is("POST", /^\/chat$/)) {
      const body = JSON.parse(request.postData() ?? "{}"), turn = conversationTurn(body.request_id, body.message);
      turns = [turn];
      return json(route, turn);
    }
    if (is("GET", /^\/conversations\/[^/]+$/)) return json(route, { conversation_id: "cv_1", revision: turns.length, turns, limit: 50, offset: 0 });
    if (is("GET", /^\/conversations\/[^/]+\/actions\/[^/]+$/)) return json(route, action);
    if (is("POST", /^\/conversations\/[^/]+\/actions\/[^/]+\/decision$/)) {
      const body = JSON.parse(request.postData() ?? "{}");
      action = actionProposal(body.decision === "approve" ? "succeeded" : "rejected");
      return json(route, action);
    }
    if (is("GET", /^\/monitoring\/model-versions\/[^/]+\/summary$/)) return json(route, { availability: "missing" });
    return json(route, { error: { code: "not_mocked", message: `${method} ${path} is not mocked`, correlation_id: "co_test" } }, 501);
  });
  return { requests, count: (method, pattern) => requests.filter((item) => item.method === method && pattern.test(item.path)).length };
}
