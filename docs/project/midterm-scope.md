# Midterm delivery scope

Jacob approved this scope on October 13, 2026 after confirming all nine supplied
requirements are due next week with a minimal working demo. The
[delivery plan](../plans/2026-10-13-midterm-delivery-plan.md) records approval,
implementation boundaries and acceptance. The original
[course instructions](course-requirements.md#supplied-implementation-instructions)
remain authoritative; scope approval does not establish feature completion.

## Deliverable

One machine runs independent model-management/conversation, tuning and monitoring
REST services from one repository/image. Share a MongoDB replica set, Redis, one
serial worker/scheduler and persistent artifacts. Use one evaluated local model
through LangChain, Prometheus/one Grafana dashboard, and local Kubernetes with
exercised CI/CD. Preserve public `/api/v1` and transaction/recovery guarantees.

| Course row | Minimal working demonstration |
| --- | --- |
| C1 | Clean locked environment and local model setup. |
| C2 | Three independent domain REST services with routed interactions. |
| C3 | Guided inspection/training/tuning dialogue with explicit inputs and history. |
| C4 | Saved parameters/versions/trials/metrics; scoping, pagination and index use at declared demo scale. |
| C5 | Small serial Bayesian search with history-grounded LangChain suggestions and confirmation. |
| C6 | Running workload, measured refresh, one dashboard/threshold issue and grounded AI summary/checks. |
| C7 | Four existing generated Python profiles, validation/rejection and human review. |
| C8 | Existing checks/recovery, rebuilt containers, Kubernetes rollout/smoke, two API replicas/one worker and exercised GitHub Actions deployment. |
| C9 | Clean-checkout walkthrough including history-based optimization, drafts, monitoring and deployment. |

## Deferred work

Broader model/data adapters, general runtime compatibility, concurrent training,
advanced drift, automatic remediation, generated-code execution, public/cloud
hosting, large retrieval benchmarks and research measurements remain deferred.
The October 13 scope deferred a custom frontend; separately approved October 19
work subsequently delivered the [local dashboard](../guides/dashboard.md), managed
immutable uploads/preparation, column-subset versions and permanent dataset/model
erasure. Directly registered operator files still depend on preserving their bytes.
Production identity/roles/TLS, scheduled retention, general migrations and
coordinated backup/restore remain outstanding before shared/public use.
Preserve existing checks. Unapproved A3/A4 plans retain their wider criteria;
they are not retrospectively passed. Earlier A1 3/10 and A2 6/7 failures remain
historical evidence. The opt-in guided 7B protocol now passes the original ten/seven
gates; [human review and clean onboarding](../guides/guided-midterm-demo.md) are now
recorded. See [current delivery evidence](../evidence/2026-10-13-midterm-delivery/README.md)
for final runtime, deployment and scope limits.

Current machine limits: October 19 desktop bounded AI acceptance and CPU-laptop
standalone ten/seven gates pass. The bounded deployed laptop walkthrough remains
open; its two passing unbounded diagnostic workflows use different direct-origin
and probe settings. See [current status](project-status.md) for those results and
remaining human/independent review gaps. Later features do not retrospectively
approve wider A3/A4 scope or establish production/research claims.

## Delivery order and completion

Fix HTTP/setup defects, extract factories/routing, deliver small monitoring and
guided AI, exercise Kubernetes, then run the combined tutorial. Prepare deployment
early and reserve final two days for integration/documentation. Keep missing
services, failed gates and review gaps visible in [project status](project-status.md)
and the course checklist. Plans/templates/tutorials alone are not completion.
