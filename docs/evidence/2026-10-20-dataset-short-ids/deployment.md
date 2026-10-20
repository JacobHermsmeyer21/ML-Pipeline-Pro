# Preserved-data local demo rollout

October 20, 2026: implementation `5f91135` was committed and pushed to `origin/main`
before upgrading the existing `mlpp-rx9070-walkthrough-20261014` Compose project.
The same base, domain-service, monitoring, dashboard and OpenAI overlays and named
data volumes were reused. The isolated verification stack was stopped afterward.

No training/tuning jobs were active before building or at the pre-stop recheck.
Gateway, domain APIs, worker and scheduler stopped for the migration. The upgraded
model API image ran `python -m ml_pipeline_pro.short_ids --writers-paused`, then
all original services restarted healthy. No hosted model or new training request
was made for live deployment verification.

The current saved dataset receives `d1`. All seven current experiments and 26
conversations retain their existing eN/cN mappings. Canonical document payload
hashes match before/after migration across all ten checked collections, excluding
only short-ID metadata on the three aliased record kinds. The 205 current artifact
and input files retain identical paths and SHA-256 hashes. These counts describe
this rollout's before/after snapshot, independently of earlier demo snapshots.

Live gateway reads by d1 and full ID return the same dataset. Chrome verifies the
dataset card, full ID, selector, `Inspect dataset d1` starter prompt and reload,
without page errors. There is currently one dataset in this demo; d2 understanding
was exercised with the second dataset in the isolated real-Qwen acceptance run.

`deployment.zip` retains the preservation report, file manifest, Compose log and
concise browser report. The live screenshot stays in local ignored artifacts.
Configured project keys were read into memory only and excluded from reports.
This is a local Compose rollout, with no new Kubernetes/hosted-provider evaluation
or human usefulness acceptance claim.
