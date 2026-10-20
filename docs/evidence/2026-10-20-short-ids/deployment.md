# Local demo upgrade

October 20, 2026: implementation `c31898c` was committed and pushed to `origin/main`
before this rollout. The same named Compose project
`mlpp-rx9070-walkthrough-20261014` and its base/services/monitoring/dashboard/OpenAI
overlays were reused. No hosted AI or training request was made for deployment
verification.

The script confirmed no queued/running/cancelling experiment or tuning job before
building and checked again afterward. It built the application image, stopped
gateway, model/tuning/monitoring APIs, worker and scheduler, then ran
`python -m ml_pipeline_pro.short_ids --writers-paused` in a one-off model API
container. MongoDB, Redis and named artifact/upload volumes were preserved.
All original application services restarted healthy with the new image.

Five experiments and 25 conversations now have aliases. Canonical record payload
hashes before/after migration match for all ten checked collections when excluding
only the new top-level `short_id` metadata on experiments/conversations. Saved
turns/actions, configurations, metrics, model/dataset identities and request
fingerprints are unchanged. All 209 files under the worker's artifact and dataset
roots retain the same paths and SHA-256 hashes.

Through the live gateway on port 8000, full and short experiment IDs return the
same records, and migrated conversation aliases identify the original
conversations. Headless Chrome verifies run rows/details, short IDs in agent
prompts and remembered conversation labels after reload, without page errors.
The script reads any configured project key into memory only; keys are absent
from reports. The actual demo screenshot remains in local ignored artifacts.

`deployment.zip` retains the structured migration/preservation report, file hash
manifest, Compose build/rollout log and concise live-browser report. The checks
establish this local deployment; no new Kubernetes rollout, hosted-provider
evaluation or human usefulness acceptance is claimed.
