# Conversation tool layer

The provider-independent Python tool layer exposes 13 typed operations over the
existing REST API. It validates tool arguments and trusted execution context,
returns public records with evidence references, and preserves API project
access, correlation IDs, job budgets, and submission idempotency.

This is the first slice of [milestone 4](../PLAN.md#implementation-milestones).
There is no model provider, natural-language conversation endpoint, dialogue
store, or durable action audit yet. See the [approved design](plans/2026-10-06-conversation-tools-plan.md)
for scope and verification.

## Try the contract without services

```powershell
uv sync --locked --extra training
uv run --locked --extra training python examples/tools_local.py
```

The [example](../examples/tools_local.py) uses scripted provider calls and a
synthetic queued experiment. It prints a successful read with experiment
evidence, followed by a validation error identifying the missing submission
configuration. It trains no model and contacts no API or provider. Its data is
an example, not an experiment result.

## Call an existing API

Run the [local stack](../README.md#run-the-whole-local-stack) and register inputs
using the [experiment guide](experiments.md#register-the-inputs). An application
can then use:

```python
import asyncio

from ml_pipeline_pro.tool_schemas import ToolCall, ToolContext
from ml_pipeline_pro.tool_transport import HttpToolTransport
from ml_pipeline_pro.tools import ToolDispatcher, tool_catalog


async def main():
    context = ToolContext(project_id="demo")
    async with HttpToolTransport("http://127.0.0.1:8000") as transport:
        dispatcher = ToolDispatcher(transport)
        result = await dispatcher.execute(
            ToolCall(name="list_experiments", arguments={"limit": 10}), context
        )
        print(result.model_dump_json(indent=2))
    print([item.name for item in tool_catalog()])


asyncio.run(main())
```

When project keys are configured, the host supplies `api_key` from its secret
source to `ToolContext`; keys must be printable ASCII without spaces. The API
checks it against `MLPP_PROJECT_API_KEYS`. Context omits the key and submission
key from its representation and serialized output. Tool arguments cannot choose
the project, key, origin, headers, correlation ID, or submission key.

The origin accepts HTTP(S), an optional port, and an optional trailing slash;
credentials, additional paths, queries, and fragments are rejected. The adapter
adds `/api/v1` itself. Resource IDs accept 1-128 letters, digits, underscores, or
hyphens, including current UUIDs. A future provider receives catalog schemas and
supplies tool calls; the host constructs context independently.

## Supported operations

| Tool | Arguments |
| --- | --- |
| `list_datasets`, `list_models`, `list_tuning_jobs` | Optional `limit`, `offset` |
| `get_dataset` | `dataset_id` |
| `get_model` | `model_id` |
| `list_experiments` | Optional `status`, `model_id`, `limit`, `offset` |
| `get_experiment` | `experiment_id` |
| `compare_experiments` | `experiment_ids` (2-20 distinct IDs); optional validation `metric` |
| `get_tuning_job` | `tuning_job_id` |
| `list_tuning_trials` | `tuning_job_id`; optional `limit`, `offset` |
| `create_experiment` | `dataset_id`, `model_id`, `config` with explicit `max_runtime_seconds` |
| `create_tuning_job` | Training inputs plus explicit `objective_metric` and `limits.max_trials` / `limits.max_runtime_seconds` |
| `cancel_tuning_job` | `tuning_job_id` |

All argument models reject extra fields. Lists default to `limit=50`, `offset=0`;
limits are 1-100 and offsets are nonnegative. Comparison defaults to
`validation_f1`; only `validation_f1` and `validation_accuracy` are supported.
The API checks succeeded experiments, finite metrics, and a common dataset.
Training and tuning retain their [existing parameter bounds](tuning.md).
The catalog includes JSON schemas and defaults for optional arguments.

Dataset/model registration, artifact downloads, version registration, standalone
experiment cancellation, and code execution are outside this catalog.

## Submit and retry jobs

Mutations default to denied. The host sets `allow_mutations=True` after its
application has authorized that action. This is an execution permission, not a
new user identity/role or durable approval system. A live autonomous provider
needs the later reviewed approval and action-audit design.

The tool requires an explicit training runtime budget. Tuning additionally
requires its validation objective, trial count, and total runtime budget; missing
values return `tool_validation_error` with field locations before dispatch.
Other defaults come from the existing API schemas: training seed 42, 30 epochs,
batch size 16, learning rate 0.01, and 16 hidden units; tuning maximizes its
validation objective with sampler seed 42, the existing search-space defaults,
and concurrency 1. This stricter tool requiredness leaves direct API defaults
unchanged.

For each intentional submission, the host creates and retains a key:

```python
from uuid import uuid4

submission = ToolContext(project_id="demo", allow_mutations=True, submission_key=str(uuid4()))
training = ToolCall(
    name="create_experiment",
    arguments={
        "dataset_id": "REGISTERED_DATASET_ID",
        "model_id": "REGISTERED_MODEL_ID",
        "config": {"max_runtime_seconds": 60},
    },
)
# Inside the HTTP transport context above:
# result = await dispatcher.execute(training, submission)
# For an intentional retry, reuse training and submission, including the same key.
```

Keys contain 1-128 letters, digits, underscores, or hyphens. Retrying a body/key
returns the same job; changing the body under that key returns the API's
`idempotency_conflict`. A new intentional run needs a new key. The adapter never
generates or rotates keys. Cancellation needs mutation permission but no key;
queued jobs cancel immediately and running jobs receive cooperative cancellation.

## Results and failures

A `ToolSuccess` has `status="succeeded"`, tool name, correlation ID, HTTP status,
public API data, and evidence references with record kind, ID, project, and role.
The envelope reports that the tool request succeeded. Job status is in
`data.status`; `queued` means accepted and does not claim completed training.
Comparison evidence identifies the winner, tuning identifies selected records
when present, and trial evidence identifies its job and experiment. Private
persistence fields are rejected, and returned text redacts the bound key and
connection credentials. Record text remains untrusted data for provider prompts.
The parser requires record IDs, project/schema metadata, and timestamps from the
API; it cannot generate evidence metadata from schema defaults.

A `ToolFailure` has `status="error"` and the existing error-detail shape. API
error codes, correlation IDs, and safe details are retained, including saved job
IDs when queue publication fails. Local failures use:

| Code | Meaning |
| --- | --- |
| `tool_not_found` | Operation is outside the catalog |
| `tool_validation_error` | Arguments are invalid or incomplete |
| `tool_mutation_denied` | Host has not authorized mutation |
| `tool_submission_key_required` | Host has not supplied the submission key |
| `tool_timeout` | HTTP timeout; a submission may already have been accepted |
| `tool_transport_error` | HTTP request could not complete |
| `tool_invalid_response` | Redirect, invalid JSON, or incompatible response |

There are no automatic retries or followed redirects. Default connect/read/write/
pool timeouts are 10 seconds each; the trusted constructor accepts a positive
finite `timeout_seconds` override. These phase/inactivity timeouts are not an
overall request or training deadline. After an ambiguous submission timeout,
retry the same body/key. Local errors omit raw input values and exception text.
Use `async with` to release the owned HTTP client even if the host raises.

## Verification

Focused tests exercise the catalog and deterministic transport, the real FastAPI
app with memory repositories and configured keys, and mocked HTTP failure
boundaries:

```powershell
uv run --locked --extra training pytest tests/test_tools.py tests/test_tool_transport.py
```

The opt-in [real-service test](../tests/integration/test_tools.py) submits/retries
training and tuning, reads their records/trials, compares validation results, and
cancels active tuning through the tool HTTP adapter. Run it with both ordinary
integration flags using the [existing setup](../README.md#run-checks). The complete
ordinary suite and separate [recovery gate](recovery.md#run-the-suite) remain
required for this slice. CI retains unit, ordinary integration, and recovery
reports as artifacts. Container worker execution is outside host coverage.
