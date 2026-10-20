# Short dataset, experiment and conversation IDs

Datasets have references such as `d1`, `d2`, `d3`; experiments use `e1`, `e2`, `e3`;
conversations use `c1`, `c2`, `c3`. Each immutable dataset version gets its own
reference. Each project has separate sequences. References survive refreshes,
browser sessions and service restarts. Deleted references are never reused.
Gaps are valid.

The dashboard shows these references in dataset cards/selectors, conversation
choices, experiment rows, details and comparisons. Full dataset and experiment
IDs remain available. Ask the agent "Inspect dataset d1", "Inspect experiment e1"
or "Compare e1 and e2 by validation F1." Use d1/d2 in training/tuning proposals;
review and confirm the saved action before submission. Verified facts
still reference canonical records. Historical messages and Python drafts remain
as originally saved.

API dataset/experiment responses, conversation turns and history include additive
`short_id` metadata. Their existing `id` and `conversation_id` stay canonical.
Existing dataset/experiment/conversation ID inputs accept either form under the usual
`X-Project-ID` and optional `X-API-Key` access controls. For example:

```http
GET /api/v1/datasets/d1
X-Project-ID: demo
```

```http
GET /api/v1/experiments/e1
X-Project-ID: demo
```

```http
GET /api/v1/experiments/compare?experiment_id=e1&experiment_id=e2&metric=validation_f1
X-Project-ID: demo
```

```http
GET /api/v1/conversations/c1
X-Project-ID: demo
```

Continue an existing conversation with `conversation_id: "c1"`, its current
`expected_revision`, and a new `request_id`. Action read/decision URLs can also use
`c1` in the conversation segment; action IDs and confirmation hashes stay unchanged.
Artifact downloads and model-version registration accept experiment aliases.
Dataset reads, column edits, deletion preview/delete and experiment/tuning
`dataset_id` inputs accept dN. Model/version/tuning-job/request IDs retain their
existing format. Column-save digests use canonical parent IDs, allowing exact
saved children to replay by dN even after parent deletion.

Use the exact original body and key to retry a request. Substituting the full ID
for an alias under the same request key changes its body and can return an
idempotency conflict. A duplicate comparison using both forms of one record is
rejected. Unknown references retain the existing missing-record errors. A reference
from another project never authorizes access to that project's record; `e1` may
name a different experiment in each project, just as d1 can name different datasets.

## Upgrade existing data

New records allocate their references transactionally with publication, including
tuning-created experiments. Existing records need a one-time migration. Coordinate
the API, model/tuning/monitoring APIs, worker and scheduler: stop canonical-record
writers before migration and resume them only with the upgraded image. Preserve
MongoDB and artifact/upload volumes. Do not mix old and new writers.

With writers stopped, run the new image against the same database, for example
using the same Compose project and files as the running stack:

```powershell
docker compose --project-name YOUR_PROJECT -f compose.yaml stop api worker scheduler
docker compose --project-name YOUR_PROJECT -f compose.yaml build api
docker compose --project-name YOUR_PROJECT -f compose.yaml run --rm --no-deps api `
    python -m ml_pipeline_pro.short_ids --writers-paused
if ($LASTEXITCODE -ne 0) { throw 'Migration failed; keep writers stopped and retry.' }
docker compose --project-name YOUR_PROJECT -f compose.yaml up --wait --no-build
```

For a domain-service deployment, include its actual overlays and stop the domain
API services too. `--writers-paused` acknowledges that prerequisite; it does not
stop services itself. The command prints counts for records migrated in this run,
checks mapping coverage, and exits without starting the application or calling AI.
It resumes committed progress after interruption. It processes at most 100 pending
records per batch, ordered by creation timestamp then full ID. Equal timestamps do
not establish an exact historical order.

The registry retains minimal identity mappings and counters after record deletion
so an old reference cannot point to a replacement. It retains no copied model or
dataset facts. Rollback application services together if needed; keep the registry
and counters for roll-forward. Older application versions require full IDs.

See the [approved design](../plans/2026-10-20-short-record-ids-plan.md),
[directly authorized dataset extension](../plans/2026-10-20-dataset-short-ids-plan.md), and
[API reference](../reference/api.md#short-record-ids).
