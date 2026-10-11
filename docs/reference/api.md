# API reference

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
