# Documentation

Start with the [project README](../README.md) to run the backend, or the
[roadmap](../PLAN.md) to see what remains.

## Guides: set up, use, and verify

- [Setup](guides/setup.md): Docker, host development, configuration, data, and artifacts.
- [Domain services](guides/domain-services.md): independent model/tuning processes and compatibility routing.
- [Workflows](guides/workflows.md): classification, tuning, and typed conversation tools.
- [Conversation development](guides/conversation-development.md): implemented slices, model boundaries, and open acceptance work.
- [Generated Python drafts](guides/snippet-generation.md): supported profiles, saved validation/provenance, and the opt-in A2 evaluation.
- [Local model setup](guides/local-model-setup.md): pinned Qwen profiles, exact token admission, and reproducing the failing live gate.
- [Verification](guides/verification.md): fast checks, real-service integration, and isolated recovery.

## Reference: APIs and architecture

- [API](reference/api.md): endpoint inventory, access, errors, and submission retries.
- [Architecture](reference/architecture.md): components, data contracts, ownership, and risks.

## Project: requirements, process, and evidence

- [Course requirements](project/course-requirements.md): supplied instructions and acceptance checklist.
- [Midterm scope](project/midterm-scope.md): approved minimal all-nine demo and deferred work.
- [Project status](project/project-status.md): dated audits, capabilities, limitations, and validation records.
- [October 13 audit and Person A handoff](project/2026-10-13-project-audit.md): current branch state, reproduced findings, course gaps and restart point.
- [Development method](project/development-methodology.md): design, human review, implementation, and verification.
- [Measurement criteria](project/measurement.md): unverified improvement targets and how to evaluate them.
- [Design plans](plans/): change-specific scope, approval, acceptance criteria, and outcomes; use the [template](plans/template.md).
- [Technical memory](memory/README.md): short findings linked to evidence.
- [Saved evidence](evidence/): execution output and provenance grouped by change.

Keep tutorials in `guides/`, API/architecture details in `reference/`, and project
requirements/process/status in `project/`. Keep dated designs, durable findings,
and raw results in `plans/`, `memory/`, and `evidence/` respectively. Root
[`AGENTS.md`](../AGENTS.md) owns standing repository rules.

Required live-model, monitoring, generated-code, separate-service, and
Kubernetes/CI/CD tutorials remain outstanding with their features.
