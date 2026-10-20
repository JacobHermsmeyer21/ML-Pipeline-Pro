# Course scope requires pre-trained models and separate services

Recorded October 6, 2026 after the user supplied the course implementation
instructions and requested documentation alignment.

The supplied [instructions and coverage checklist](../project/course-requirements.md)
require LangChain with pre-trained language models, separate model-management,
tuning, and monitoring services, AI-generated Python snippets, Docker, Kubernetes,
and CI/CD. They do not require training a code language model or using a paid
external API. The revised course target uses local pre-trained inference; the
managed PyTorch classifier remains a different model role.

At source baseline `ba6334f`, [main.py](../../src/ml_pipeline_pro/main.py) includes
tracking and tuning routers in one API, [Compose](../../compose.yaml) has process
and dependency services rather than the required separate domain APIs, and the
[manifest](../../pyproject.toml) has no LangChain integration. The
[course-aligned plan](../plans/2026-10-06-conversation-workflows-plan.md) was
awaiting review at that baseline. It was approved October 7, 2026; an October 8
source check at `c28ae06` confirms implementation remains outstanding. These are
documented requirements and source findings, not evidence that
the outstanding features or local model have been implemented or evaluated.

Person A's October 8 [foundation](../guides/conversation-development.md) introduces
locked LangChain dependencies, schemas, a model interface, and settings. Its
next A1 slices add a deterministically tested LangChain/Ollama adapter and durable
turn/proposal storage with real-MongoDB claims/replay/takeover coverage. The
bounded host loop now grounds supplied current-turn facts and saves proposals.
Authenticated routes and confirmed action dispatch/recovery are now implemented
in the [action slice](conversation-action-uncertainty.md). Installed-artifact
token verification and live-model evidence remain outstanding; C3/C5 are still open.
The preceding absent-dependency finding
remains historical to its
stated baseline.

October 13: Jacob confirmed all nine midterm requirements and approved the
[minimal delivery plan](../plans/2026-10-13-midterm-delivery-plan.md). Keep separate
services/shared code-image-database, guided AI, small monitoring and local Kubernetes
CI/CD. Large A4 workloads/advanced drift/production scope are deferred. Existing
failed gates remain failures until complete new gates pass.

October 19 reconciliation: the minimal three-domain/local-LangChain/monitoring/
generated-code/Kubernetes scope has retained acceptance, superseding the early
missing-dependency/tokenizer findings above. A separately approved dashboard now
adds immutable managed preparation/column versions and permanent erasure.
Desktop bounded AI and laptop standalone ten/seven gates pass; bounded deployed
laptop acceptance and newer independent/human control reviews remain open. See
the [current course checklist](../project/course-requirements.md) for exact evidence.

Revisit if the user supplies a revised course instruction or approves a different
deployment/model scope. Do not make microservices or Kubernetes conditional on
commercial scale, count templates as AI generation, or infer implementation
approval from the roadmap.
