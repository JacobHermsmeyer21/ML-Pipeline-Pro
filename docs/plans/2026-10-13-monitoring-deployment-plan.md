# Minimal monitoring and local Kubernetes delivery

- Status: approved October 13 midterm direction; implementation pending
- Date: 2026-10-13
- Source baseline: `62b22db` / `person-a/conversation-foundation`
- Human approval: Jacob approved all scope-review recommendations and requested implementation; [record](2026-10-13-midterm-delivery-plan.md#human-review-and-approval)
- Independent review: separate boundary reviewer; different-vendor review unavailable

## Proposed behavior and purpose

Complete the minimal three-service demo: record actual classification inference
observations, visualize a short window, seed one latency issue and ask the local
LangChain model for an evidence-linked explanation/checks. Deploy the same domain
services into a disposable single-node Kubernetes cluster and exercise that path
in GitHub Actions after checks. Keep one serial worker and scheduler.

## Clarification and critique

This is a classroom workload, not production monitoring or drift detection.
Use existing finalized model versions/artifacts and immutable monitoring samples;
do not retrain/select on inference observations. A seeded delay is a declared
injection, not evidence of a real regression. Missing labels produce unknown
accuracy. Refresh/scrape 15 seconds, target measured visibility within 30 seconds
after an accepted sample. Bounded newest-100 window summaries explicitly report
partial data; no large-scale latency guarantee. Prose is generated interpretation,
never a replacement for measured facts. No automatic fixes/code execution.

Local kind is sufficient deployment scope; public hosting/cloud infrastructure,
autoscaling workers and distributed training are deferred. The independent domain
factories keep the compatibility stack and recovery harness. No unresolved intent
is required to implement this already approved minimal direction. Human model
quality and combined onboarding review remain separate acceptance obligations.

## Requirements

| ID | Type | Requirement | Evidence |
| --- | --- | --- | --- |
| F1 | Functional | Independent monitoring API; samples reference a project-owned saved model version. | Separate factory/topology, authenticated foreign-reference checks. |
| F2 | Functional | Immutable idempotent samples and bounded measured summaries with timestamp/labels/errors/seed declaration. | Same-key replay/conflict/concurrent insert, missing/stale/partial windows and MongoDB index evidence. |
| F3 | Functional | Prometheus and one Grafana dashboard update; seeded latency issue has local-model explanation/checks citing observations. | Real inference producer, measured scrape/query delay, provisioned dashboard and actual LangChain output. |
| F4 | Functional | Local Kubernetes rollout/smoke and checked CI/CD deployment. | kind apply/rollout, training+tuning+monitoring workflow, two model API replicas/one worker and remote CI result. |
| N1 | Reliability | Existing access/correlation, selection/artifact integrity and tuning ownership remain intact. | Fast, ordinary and isolated recovery gates; independent boundary review. |

## Constraints and scope

Preserve existing `/api/v1` schemas/actions and native defaults. Add monitoring
routes without adding arbitrary public conversation tools. Use immutable model
version references, shared MongoDB, existing artifact hash/size verification and
training-fitted preprocessing. No training artifact writes during monitoring.
No arbitrary log text, URLs or secret values in samples; safe fault categories.
No production retention/migration/identity claim. Existing named local volumes
remain intact; disposable test cluster has a separate kubeconfig/context.

## Design

Add `/api/v1/monitoring/observations` POST and GET (project-scoped pagination),
`/api/v1/monitoring/model-versions/{id}/summary` GET and `/diagnosis` POST,
and authenticated `/api/v1/monitoring/metrics` for the configured demo project
scrape. Samples have caller sample ID, observed timestamp (UTC milliseconds),
model-version ID, latency milliseconds, success/error, nullable correctness and
fault enum `none|seeded_latency|inference_error`. Explicitly validate time and
error/label consistency. Derive sample record identity from project/sample ID;
MongoDB's unique `_id` atomically arbitrates immutable insert, identical replay or
409 changed-body conflict. Store normalized input hash and scoped timestamp indexes.
Model versions cannot be deleted by existing public routes, so reference validation
does not require a new cross-domain ownership transaction.

Summary queries cover a 30-3600 second window, fixed upper time, newest 101 records
and return at most 100 with `partial`; no-data/stale/labels-unknown are explicit.
Calculate observed latency mean/max, errors and labeled accuracy separately;
fixed demo latency threshold 100 ms on maximum. Prometheus gauges describe this
bounded window, including availability/partial flags, not lifetime counters.
Export one project and bounded model-version labels; omit unknown accuracy.

The existing isolated LangChain/Ollama adapter gains a separate typed diagnosis
candidate with observation citations and proposed check categories. One bounded
inference, same exact counter/byte/output limits, no native tools. Validate citations
against the authorized snapshot; generated text stays labeled interpretation and
the response includes measured summary plus model provenance. Lack of data/model
fails safely. Monitoring factory owns and closes its model client; ordinary
readiness retains documented MongoDB/Redis dependency checks.

Add an opt-in monitoring Compose overlay and gateway routes/docs. Provision
Prometheus scrape/rule interval and Grafana dashboard at 15 seconds. The local
unkeyed demo scrapes project `demo`; keyed setups must supply a private custom
header configuration (never commit credentials). Dashboard ports bind loopback.
Use official [Prometheus configuration](https://prometheus.io/docs/prometheus/latest/configuration/configuration/)
and [Grafana provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/).

Kubernetes manifests use namespace `mlpp-demo`, internal Services, ConfigMaps,
singleton MongoDB replica set/Redis/worker/scheduler, persistent local artifacts,
domain APIs and gateway, plus monitoring visualization. Use explicit image tags,
requests/limits and health probes. Local volumes are for one node; this is not a
multi-node persistence solution. Scale stateless model API to two replicas and
exercise shared-store idempotency; do not scale the worker. Build/load the image,
apply and await rollout in an isolated kind cluster via explicit kubeconfig. The
CI job needs checks, creates an ephemeral kind cluster, loads the image and runs
the same deployment smoke; it does not require paid credentials. Follow official
[kind setup](https://kind.sigs.k8s.io/docs/user/quick-start/).

## Acceptance and verification

Before performance runs: train/register one finalized classification version,
run 20 inference observations including at least five declared 150 ms delays,
poll Prometheus at most 30 seconds after accepted samples, and retain raw queries,
timestamps, dashboard configuration and actual diagnosis. Report measured delay
only for this workload/machine; missing labels and empty/partial windows must not
show zero accuracy or complete healthy state. Retain generated text separately.

Run all fast checks, build/dependency checks, affected monitoring MongoDB/API tests,
ordinary gates with both flags and serial isolated recovery after container changes.
Review insert races, window/count arithmetic, inference artifact use and deployment
replica scope independently. Check links/examples and whitespace. Run isolated
Kubernetes smoke, collect revision/image identity and inspect remote deployment CI.
Human usefulness/combined onboarding remain outstanding until actually reviewed.

## Risks and rollback

Local model explanations may be unhelpful despite schema correctness; retain failures
and require review. Small capped windows can omit older failures and must display
partial status. Private scrape config can become stale or deny access; show `up=0`,
not healthy fallback metrics. Local Kubernetes resource shortages may cause rollout
failure; report it and preserve logs. Remove only the explicitly named disposable
cluster; retain local Compose data. Reverting monitoring routes leaves additive
immutable samples intact and does not rewrite training artifacts or tuning state.

## Human review and approval

Implementation detail within Jacob's October 13 approved minimal monitoring,
three-service and local Kubernetes/CI-CD direction. This is not a claim of separate
human review of this document. No broader A3/A4 criteria are retrospectively passed;
material changes to approved intent require renewed review.

## Implementation outcome

Pending. No monitoring/deployment row closed by this plan.
