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

## Permanent dataset and model deletion

The model service owns these routes, using the usual project/key headers:

| Method | Route | Result |
| --- | --- | --- |
| GET | `/api/v1/datasets/{dataset_id}/deletion-preview` | Exact dependent-record/file counts, active-job blockers and `preview_sha256`. |
| GET | `/api/v1/models/{model_id}/deletion-preview` | Equivalent preview for the entire classifier model. |
| DELETE | `/api/v1/datasets/{dataset_id}` | Permanently erase the reviewed dataset-version cascade. |
| DELETE | `/api/v1/models/{model_id}` | Permanently erase the reviewed model cascade. |
| GET | `/api/v1/deletions/{operation_id}` | Saved `preparing`, `cleaning` or `complete` status and counts. |

Both DELETE routes require `Idempotency-Key` and JSON containing exactly the
reviewed fingerprint:

```json
{"preview_sha256": "0000000000000000000000000000000000000000000000000000000000000000"}
```

Replace that illustrative hash with the server preview. A changed scope returns
409 `deletion_preview_stale`; fetch/review it again with a new key. Queued,
running or cancelling related jobs, including expired leases awaiting recovery,
return 409 `deletion_blocked` without cancelling or erasing them. Deletion also
waits for live former workers to release their native storage locks.

Dataset erasure removes that version's experiments, tuning jobs/trials, derived
registered versions, associated monitoring observations and all checkpoint
attempts. Model erasure removes the definition and the same history for all its
datasets, preserving the dataset records/inputs. Dataset erasure removes uploaded
source/canonical/preparation files only when no surviving dataset references
them. Shared files and registered operator inputs outside `uploads/<project>/`
are counted as retained. Saved conversations/Python drafts, exports, backups,
retained evidence and historical Prometheus samples remain; saved chat facts
must be checked against current records. This is not forensic disk wiping.

A 200 receipt confirms complete cleanup. Failure or a lost response is uncertain:
retry the same DELETE URL/body/key, and use any returned `operation_id` to inspect
progress. A durable cleanup journal survives restart. New project mutations
temporarily return 409 `deletion_in_progress` until it completes; unrelated reads
remain available. Storage failures return correlated 503. Never delete an
incomplete journal or clear its admission gate to bypass failed file cleanup.
Erased resources return 404. Repeating a completed deletion with its original key
returns the saved receipt; different arguments with that key conflict. Names can
be reused with new record IDs after completion.

Minimal operation and submission-key receipts retain counts, IDs and request/key
hashes, without training data/metrics/configuration. Replaying an erased
training/tuning submission returns 410 `submission_deleted`; changing that old
key's body remains 409. An old submission cannot recreate an erased run.

All participating services must use matching lifecycle-aware code and the shared
artifact volume for native locks. Keep worker uploads read-only. Unsupported
native locking or changed cleanup storage roots blocks cleanup; do not fall back
to expiring soft locks. Existing dataset/model response schemas are unchanged.

## Raw CSV preparation

The opt-in model-service routes `POST /api/v1/datasets/preview` and
`POST /api/v1/datasets/prepare` accept multipart `file` (original UTF-8 CSV) and
`settings` (JSON text). Supply the same project/key headers. Authenticate before
body parsing; absent training dependencies return correlated 503. Preview is
stateless and returns no registered dataset. Prepare requires `reviewed_sha256`
equal to the latest preview's `preview_sha256`, or returns correlated 409
`preparation_review_required`. Do not use the old numeric upload route for raw CSVs.

Settings include `name`, `version`, `target_column`, optional `columns`,
`label_mapping`, `train_percent=70`, `validation_percent=15`, `test_percent=15`,
`seed=42`, `split_column=null` and `impute_missing=false`. Percentages are positive
integers summing to 100. Class-stratified splitting reserves test rows first,
then validation rows, using integer ceiling counts from the original row total;
the training remainder is never empty. Each split must contain every class.
Rare classes/impossible ratios produce 422, without falling back to random splits.

Example JSON for the `settings` part (send it with the original CSV):

```json
{
  "name": "drug200",
  "version": "v1",
  "target_column": "Drug",
  "columns": {
    "BP": {
      "treatment": "mapping",
      "mapping": {"HIGH": 3, "LOW": 1, "NORMAL": 2},
      "unknown_value": 0
    }
  }
}
```

Unspecified columns use training-inferred numeric or one-hot treatment. Overrides
may choose `auto`, `numeric`, `one_hot`, `mapping` or `exclude`; mapping must cover
the training vocabulary with finite numbers of magnitude at most 1e12 and an
explicitly reviewed unknown fallback (default zero). Numeric mappings impose
distances; one-hot is the normal choice for unordered categories. Target/split
columns cannot be features. Optional `label_mapping` reorders contiguous IDs
`0..classes-1` without changing readable names. Custom settings, generated feature
columns, categories, fills, unknown counts and target IDs appear in preview.

Split membership is fixed per dataset version and independent of training seeds.
Type inference, category vocabularies and optional median/mode imputation use only
training rows. Missing targets or entirely missing training features fail 422.
Unseen feature categories use all zeros for one-hot or the configured mapping
fallback; preview warns and feature width stays fixed. There is no automatic
ordinal/target encoding, balancing, grouping, time splitting or row removal.

Source limits: the smaller of 10,000,000 bytes and `MLPP_DATASET_MAX_BYTES`, the
configured row limit, at most 130 unique nonempty headers, 128 UTF-8 bytes per
header/cell, and 2-64 classes. Settings are capped at 32 KiB, multipart overhead at
32 KiB; the gateway's new route guard is 10,065,536 bytes, and the application
uses the effective smaller raw cap plus 64 KiB. Actual received bytes govern the
limits independently of `Content-Length`. Receipt has a 30-second deadline;
parsing/transformation share a separate cooperative 30-second deadline.
The encoded float32 matrix is capped at 64 MiB and 128 features before allocation;
canonical CSV uses `MLPP_DATASET_MAX_BYTES`, and preparation JSON is capped at
256 KiB. These are allocation/output bounds, not a measured peak-memory guarantee.

Prepare publishes source CSV, canonical numeric CSV and versioned preparation JSON
without replacement under `uploads/<project>/`, then inserts one dataset record.
`DatasetRecord.preparation` is optional for old records and references source and
manifest URI/hash/size plus the recipe hash. The existing dataset `sha256` describes
the canonical CSV. Same identity/source/recipe/output replays with 200; creation
returns 201; changed settings conflict even if numeric output happens to match.
All published files survive uncertain metadata writes. Original rows are never
returned in error messages, and preview removes its staging files.

New worker checkpoints/manifests include the verified preparation recipe alongside
existing training-only normalization. `dataset_preparation.transform_rows` applies
saved encodings to raw feature dictionaries, then inference applies checkpoint
`mean`/`std`; `decode_labels` restores class names. Old checkpoints remain numeric.
Final evaluation preserves original training artifacts. There is no new scoring
route or automatic generated-code execution.

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
