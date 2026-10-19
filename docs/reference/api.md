# API reference

## Dataset upload

`POST /api/v1/datasets/upload` is an opt-in model-service route. Supply the usual
project/key headers, `Content-Type: text/csv`, the raw CSV body, and query metadata
`name`, `version`, repeated `feature_columns`, optional `target_column=target` and
`split_column=split`. The original `POST /datasets` JSON registration route remains
available. Both routes enforce project ownership of the reserved `uploads/` files.

Set `MLPP_DATASET_UPLOAD_ENABLED=true`, or use `compose.dashboard.yaml`. The API
counts received bytes independently of `Content-Length` and allows the smaller of
10,000,000 bytes and `MLPP_DATASET_MAX_BYTES`; receipt is limited to 30 seconds.
The existing CSV validation and row/class limits also apply. The gateway has a
10,000,000-byte outer guard on this exact route only. Responses use the existing
error envelope/correlation header: 201 created, 200 matching name/version/content/
column replay, 400 interrupted body, 403 access denied, 404 disabled/foreign file,
408 receipt timeout, 409 identity/file conflict, 413 oversized body, 415 unsupported
media type, 422 invalid CSV/metadata and 503 unavailable storage.

Files are published without replacement under project-scoped content hashes,
then registered with the existing `DatasetRecord`. Concurrent identical uploads
converge on one identity; conflicting versions are not replaced. A database
acknowledgement can be lost after commit, so published files are retained on
uncertain writes and the same upload can recover its saved record. Only the
request's private staging file is automatically removed. Never delete a shared
uploads volume while registered datasets reference it.

`GET /dashboard/` serves the packaged UI; `GET /dashboard/config.json` exposes
public capability/limit information without credentials. See the
[dashboard guide](../guides/dashboard.md) for local startup and browser workflows.

Open [interactive API docs](http://127.0.0.1:8000/docs) after
[setup](../guides/setup.md). Run example requests from the repository root.

## Access and submissions

Metadata, experiment, tuning, and conversation operations require `X-Project-ID`
and, when project keys are configured, `X-API-Key`. Referenced records must belong
to the selected project. Training and tuning submissions require an
`Idempotency-Key`; retries reuse the original key and body.

## Endpoints

| Endpoint | Meaning |
| --- | --- |
| `GET /api/v1/health/live` | Process is running; does not contact dependencies |
| `GET /api/v1/health/ready` | MongoDB and Redis both respond within the configured timeout |
| `POST /api/v1/datasets` | Validate a local CSV and register its content hash and split metadata |
| `GET /api/v1/datasets` and `GET /api/v1/datasets/{id}` | List or retrieve datasets within a project |
| `POST /api/v1/models` | Register a PyTorch classification model |
| `GET /api/v1/models` and `GET /api/v1/models/{id}` | List or retrieve models within a project |
| `POST /api/v1/experiments` | Queue a bounded training job; requires `Idempotency-Key` |
| `GET /api/v1/experiments` and `GET /api/v1/experiments/{id}` | Filter experiments or retrieve status, metrics, and artifacts |
| `GET /api/v1/experiments/compare` | Compare completed experiments using validation metrics |
| `GET /api/v1/experiments/{id}/artifacts/{name}` | Download a hash-verified checkpoint or manifest |
| `POST /api/v1/models/{id}/versions` | Register a model version from a completed experiment |
| `GET /api/v1/models/{id}/versions` and `GET /api/v1/models/{id}/versions/{version_id}` | Retrieve registered model versions |
| `POST /api/v1/tuning-jobs` | Queue a bounded TPE search; requires `Idempotency-Key` |
| `GET /api/v1/tuning-jobs` and `GET /api/v1/tuning-jobs/{id}` | Retrieve tuning status, budgets, and the selected configuration |
| `GET /api/v1/tuning-jobs/{id}/trials` | Inspect trial parameters, metrics, durations, and failures |
| `POST /api/v1/tuning-jobs/{id}/cancel` | Cancel queued tuning or cooperatively stop an active trial |
| `POST /api/v1/chat` | Generate or replay a bounded project conversation; enabled chat required |
| `GET /api/v1/conversations/{id}` | Read ascending saved turns (`limit=50`, maximum 100; `offset=0`) |
| `GET /api/v1/conversations/{id}/actions/{action_id}` | Inspect the saved proposal, decision, attempts and outcome |
| `POST /api/v1/conversations/{id}/actions/{action_id}/decision` | Approve/reject the exact saved fingerprint without inference |
| `POST /api/v1/monitoring/observations` | Save/replay immutable project sample ID; require a project-owned model version |
| `GET /api/v1/monitoring/observations` | Project-scoped pagination (`limit` 1-100, nonnegative `offset`) |
| `GET /api/v1/monitoring/model-versions/{version_id}/summary` | Newest-100 observations in a 30-3600 second window; missing/partial/unknown labels explicit |
| `POST /api/v1/monitoring/model-versions/{version_id}/diagnosis` | One local-model interpretation/checks with observation citations; review required, no changes |
| `GET /api/v1/monitoring/metrics` | Authenticated Prometheus metrics for the selected project, bounded five-minute window |

Readiness returns `503` with each dependency's status when either service is unavailable. Responses include `X-Correlation-ID`; an optional valid caller ID is preserved in the response and request logs. Errors contain `error.code`, `error.message`, and `error.correlation_id`.

Readiness checks MongoDB/Redis connectivity. Experiment status and heartbeat timestamps show worker progress separately.

Conversation generation and decisions default to disabled (`MLPP_CHAT_ENABLED=false`);
authenticated history/action reads remain available. All four routes use the existing
project headers. A repeated request ID must retain its original body; an action
decision sends only `decision` and the displayed `arguments_hash`. Running replays
return 202; saved outcomes retain their original execution correlation while the
HTTP header carries the current request correlation. Explicit retries of uncertain
actions reuse the original submission key and stop after three dispatch attempts.
See the [conversation guide](../guides/conversation-development.md#confirmed-actions-and-http-routes).
The default adapter still requires an artifact-specific verified token counter;
enabling chat alone does not establish working local inference.

Chat turns can also include an optional `snippet` containing a generated Python
draft or a rejected generation result. It always requires human review and
creates no action or domain submission. Conversation history and same-request
replay retain the original draft/provenance. See [snippet generation](../guides/snippet-generation.md).

For request examples, see [workflows](../guides/workflows.md).

Monitoring routes belong to the independent monitoring factory and three-domain
topology; the compatibility application retains its original routes. Monitoring
samples use body `sample_id` for immutable replay (409 altered input); existing
accepted samples remain replayable after fresh-time admission expires. New samples
must be observed within the last day and no more than five seconds in the future.
Observed/error labels and latency are validated; unknown version references are 404.
Monitoring POST bodies share the bounded host request cap. See [monitoring](../guides/monitoring-demo.md).
