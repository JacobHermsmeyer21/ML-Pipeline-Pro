# Course scope requires pre-trained models and separate services

Recorded October 6, 2026 after the user supplied the course implementation
instructions and requested documentation alignment.

The supplied [instructions and coverage checklist](../course-requirements.md)
require LangChain with pre-trained language models, separate model-management,
tuning, and monitoring services, AI-generated Python snippets, Docker, Kubernetes,
and CI/CD. They do not require training a code language model or using a paid
external API. The revised course target uses local pre-trained inference; the
managed PyTorch classifier remains a different model role.

At source baseline `ba6334f`, [main.py](../../src/ml_pipeline_pro/main.py) includes
tracking and tuning routers in one API, [Compose](../../compose.yaml) has process
and dependency services rather than the required separate domain APIs, and the
[manifest](../../pyproject.toml) has no LangChain integration. The
[course-aligned plan](../plans/2026-10-06-conversation-workflows-plan.md) is awaiting
review. These are documented requirements and source findings, not evidence that
the outstanding features or local model have been implemented or evaluated.

Revisit if the user supplies a revised course instruction or approves a different
deployment/model scope. Do not make microservices or Kubernetes conditional on
commercial scale, count templates as AI generation, or infer implementation
approval from the roadmap.
