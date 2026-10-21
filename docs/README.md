# Documentation

Start with the [project README](../README.md) to run the application and the
[current status](project/project-status.md) for delivered capabilities, saved
verification and remaining gaps. The [roadmap](../PLAN.md) and individual plans
retain their reviewed milestone/design scope.

## Guides: set up, use, and verify

- [Setup](guides/setup.md): Docker, host development, configuration, data, and artifacts.
- [Capabilities and operational limits](guides/project-capabilities.md): detailed feature contracts and dated evidence retained from the pre-template README.
- [Local dashboard](guides/dashboard.md): import raw CSVs, review encodings/splits, drop input columns into new versions, train, permanently delete datasets/models, chat and inspect Grafana.
- [Domain services](guides/domain-services.md): independent model/tuning processes and compatibility routing.
- [Workflows](guides/workflows.md): classification, tuning, and typed conversation tools.
- [Conversation development](guides/conversation-development.md): implemented slices, model boundaries, and open acceptance work.
- [Generated Python drafts](guides/snippet-generation.md): supported profiles, saved validation/provenance, and the opt-in A2 evaluation.
- [Local model setup](guides/local-model-setup.md): pinned Qwen profiles, exact token admission, and opt-in model evaluation.
- [Laptop Qwen diagnostic](guides/laptop-qwen-diagnostic.md): one warmed, bounded inspection request with retained latency and semantic evidence.
- [Five-minute laptop profile](guides/laptop-five-minute.md): coordinated finite budgets, passing standalone gates, unresolved deployed acceptance and the separate unbounded diagnostic.
- [Guided midterm demo](guides/guided-midterm-demo.md): evaluated 7B dialogue and generated-code configuration, original gates and review limits.
- [Monitoring demo](guides/monitoring-demo.md): actual inference observations, Grafana/Prometheus and evidence-linked local-model advice.
- [Kubernetes demo](guides/kubernetes-demo.md): isolated local deployment, replica scope and CI/CD.
- [Complete midterm walkthrough](guides/midterm-walkthrough.md): combined classification/history/tuning/draft/monitoring demonstration.
- [Verification](guides/verification.md): fast checks, real-service integration, and isolated recovery.

## Reference: APIs and architecture

- [API](reference/api.md): endpoint inventory, dataset preparation/column versions, permanent deletion, access, errors and replay.
- [Architecture](reference/architecture.md): components, data contracts, ownership, and risks.

## Project: requirements, process, and evidence

- [Course requirements](project/course-requirements.md): supplied instructions and acceptance checklist.
- [Midterm scope](project/midterm-scope.md): approved minimal all-nine demo and deferred work.
- [Project status](project/project-status.md): dated audits, capabilities, limitations, and validation records.
- [October 18 audit and demo priorities](project/2026-10-18-repo-audit.md): historical pre-dashboard coverage, branch state and laptop findings; later results live in project status.
- [October 13 audit and Person A handoff](project/2026-10-13-project-audit.md): historical branch state, findings and gaps before minimal delivery.
- [Development method](project/development-methodology.md): design, human review, implementation, and verification.
- [Measurement criteria](project/measurement.md): unverified improvement targets and how to evaluate them.
- [Design plans](plans/): change-specific scope, approval, acceptance criteria, and outcomes; use the [template](plans/template.md).
- [Technical memory](memory/README.md): short findings linked to evidence.
- [Saved evidence](evidence/): execution output and provenance grouped by change.

Keep tutorials in `guides/`, API/architecture details in `reference/`, and project
requirements/process/status in `project/`. Keep dated designs, durable findings,
and raw results in `plans/`, `memory/`, and `evidence/` respectively. Root
[`AGENTS.md`](../AGENTS.md) owns standing repository rules.

The minimal all-nine tutorials and implementations have retained acceptance evidence.
October 19 adds verified dashboard import/preparation, column versions and permanent
deletion. Standalone laptop model gates pass, but the bounded deployed laptop
walkthrough remains outstanding. The two passing unbounded diagnostic workflows
have different delivery/probe settings; see [current status](project/project-status.md).
