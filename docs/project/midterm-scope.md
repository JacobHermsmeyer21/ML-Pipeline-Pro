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
advanced drift, automatic remediation, generated-code execution, custom frontend,
public/cloud hosting, large retrieval benchmarks and research measurements are
deferred. Production identity/roles/TLS, immutable datasets, retention/migrations
and coordinated backup/restore remain outstanding before shared/public use.
Preserve existing checks. Unapproved A3/A4 plans retain their wider criteria;
they are not retrospectively passed. A1 3/10 and A2 6/7 acceptance failures remain
open; original semantic/rejection gates and human review still apply.

## Delivery order and completion

Fix HTTP/setup defects, extract factories/routing, deliver small monitoring and
guided AI, exercise Kubernetes, then run the combined tutorial. Prepare deployment
early and reserve final two days for integration/documentation. Keep missing
services, failed gates and review gaps visible in [project status](project-status.md)
and the course checklist. Plans/templates/tutorials alone are not completion.
