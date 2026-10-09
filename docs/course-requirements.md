# Course implementation requirements

Source: implementation instructions supplied by the repository user on October 6,
2026 for this machine learning class project. The numbered text below preserves
the supplied requirements. The mapping and implementation choices are the
repository's interpretation, not an instructor's grading decision. No grading
weights, deadline, or additional training requirement were supplied.

Use this document as the acceptance checklist for the course deliverable. The
[roadmap](../PLAN.md) orders work, the [status record](project-status.md) retains
verification evidence, and feature designs still require human review under the
[development method](development-methodology.md). Correcting documentation does
not implement or verify any outstanding requirement.

## Supplied implementation instructions

1. Initialize Project Environment: Set up a Python environment with venv or conda. Install required packages including LangChain, PyTorch/TensorFlow for model handling, and PyMongo for database connections.

2. Design Architecture: Implement a microservices architecture. Create separate services for model management, hyperparameter tuning, and performance monitoring. Use Flask or FastAPI as lightweight web frameworks for RESTful APIs.

3. Integrate LangChain: Leverage LangChain to develop conversational interfaces. Use pre-trained language models to generate commands and insights from natural language queries. Implement a dialogue management system that guides users through pipeline creation and enhancement steps based on best practices and historical data.

4. Data Storage with MongoDB: Design a robust data model with MongoDB. Store model parameters, versions, tuning results, and evaluation metrics. Index collections for efficient search and retrieval.

5. Automate Hyperparameter Tuning: Implement an automated tuning module using Bayesian optimization or reinforcement learning integrated with LangChain for intelligent suggestions. Log configurations and results to MongoDB for future reference.

6. Model Monitoring: Develop a real-time monitoring system using Python libraries such as Prometheus or Grafana for visualization. Utilize LangChain to generate summaries and potential fixes for performance issues identified in logs.

7. Integrate AI Code Generation: Incorporate AI-based code generation with LangChain, enabling engineers to automatically generate Python snippets for pipeline integration, directly from conversational inputs.

8. Testing and Deployment: Write comprehensive unit and integration tests. Use Docker to containerize services and Kubernetes for scalable deployment. Implement CI/CD pipelines using GitHub Actions or Jenkins.

9. User Documentation: Provide clear user documentation and tutorials to help engineers quickly onboard and leverage the tool's features. Offer examples of common use cases and advanced optimization strategies that the platform supports.

## Implementation choices and boundaries

- Use Python/uv with its `.venv`, PyTorch, PyMongo, FastAPI, Optuna Bayesian tuning,
  and GitHub Actions. These choose among the stated alternatives; TensorFlow,
  Flask, reinforcement learning, conda, and Jenkins are not additional obligations.
- Use LangChain with a locally served pre-trained language model for dialogue,
  suggestions, monitoring explanations, and AI-generated Python snippets. The
  local integration proposed in the [conversation plan](plans/2026-10-06-conversation-workflows-plan.md)
  uses `ChatOllama`; its model artifact and runtime must be selected and evaluated.
  No paid external model API, provider key, custom language-model training, or
  fine-tuning is required for this course scope. Local inference still uses
  compute and memory. The existing classifier is a separate managed ML workload.
- Model management, tuning, and monitoring must be separately deployable REST
  services. Sharing a repository, image, or MongoDB deployment is compatible with
  that target; modules in one API process do not satisfy the service separation.
  Preserve [transactional tuning ownership](memory/tuning-parent-fence.md) and
  current `/api/v1` contracts during a separately reviewed extraction.
- Monitoring needs observations/metrics, a defined refresh interval, visualization,
  and LangChain summaries with evidence-linked proposed fixes. Logs and health
  endpoints alone do not satisfy instruction 6. Establish observable update/alert
  timing in its design rather than assert an unmeasured real-time guarantee.
- Instruction 7 requires model-generated Python through LangChain. Templates may
  guide or validate output; checked-in examples or templates alone do not satisfy
  it. Generated code remains subject to syntax/API checks and human review.
  Automatic execution is not required by the supplied instructions.
- Kubernetes deployment and an exercised CI/CD deployment path are part of the
  course acceptance, including a documented test-cluster workflow. Docker Compose
  alone is insufficient. Demonstrate the supported stateless API replica-scaling
  behavior while keeping training workers serial until their existing gates
  support a change. Concurrent training, public hosting, paid cloud
  infrastructure, and production hardening are separate from the local course
  demonstration; shared/public use still needs the [operational controls](project-status.md#deployment-and-operational-gaps).

## Requirement coverage and acceptance evidence

Status is source-grounded at `ba6334f` / October 6, 2026. Existing test results
retain the revisions and limits in the linked records; no new application tests
were run for this documentation alignment.

Rechecked against `c28ae06` on October 8, 2026: coverage remains unchanged.
The conversation design now has October 7 human approval, but the required
local-model integration and its acceptance evidence remain outstanding.

Person A's October 8 foundation adds locked LangChain/Ollama dependencies,
conversation schemas, the model interface, and chat settings. The
[development guide](conversation-development.md) records the limited scope;
the next A1 slices add a local LangChain adapter with deterministic SDK/HTTP
tests, durable turn/proposal storage with real-MongoDB claims/replay evidence,
and a bounded host loop that grounds supplied API facts and saves proposals.
Authenticated chat/history/action routes and exact-action dispatch/recovery now
exist. Installed-artifact tokenization, live inference, real-model
evidence, and clean-checkout
onboarding remain outstanding. No course row is closed by this slice.

| ID | Requirement | Current coverage | Evidence needed to close the requirement |
| --- | --- | --- | --- |
| C1 | Python environment and required libraries | Partial: uv/venv, PyTorch, PyMongo, and locked LangChain/Ollama dependencies exist; local runtime setup and clean-checkout evidence remain outstanding. | Locked LangChain/local-model dependencies installed on a clean checkout; documented setup succeeds. See [manifest](../pyproject.toml) and [setup](../README.md#development-setup). |
| C2 | Separate model-management, tuning, and monitoring services | Outstanding: one FastAPI application serves tracking/tuning; monitoring is absent. | Start each domain service independently; integration proves REST interactions and preserved transaction/project boundaries. See [current app](../src/ml_pipeline_pro/main.py) and [Compose](../compose.yaml). |
| C3 | LangChain, pre-trained model, guided dialogue/history | Outstanding: tools, a tested local adapter, durable grounded conversations, routes and confirmed actions exist; installed-artifact token verification and real-model evidence are absent. | A real local pre-trained model guides pipeline steps, requests missing inputs, uses recorded history, and returns grounded commands/insights. Deterministic tests alone cannot establish model integration. See [tool guide](workflows.md#conversation-tool-layer). |
| C4 | MongoDB parameters, versions, tuning results/metrics, indexes | Initial classification scope delivered; representative query performance remains unmeasured. | Retain schema/index/persistence regressions and demonstrate retrieval of saved configurations, versions, trials, and metrics. See [tracking](../src/ml_pipeline_pro/tracking.py), [tuning store](../src/ml_pipeline_pro/tuning_store.py), and [status](project-status.md#architecture-and-durable-records). |
| C5 | Automated optimization with LangChain suggestions and saved history | Partial: serial Bayesian tuning and MongoDB history exist; LangChain suggestions are absent. | Demonstrate bounded, user-confirmed tuning suggestions grounded in previous trials; existing worker limits, validation selection, ownership, and recovery gates pass. See [tuning guide](workflows.md#bounded-classification-tuning) and [sampler](../src/ml_pipeline_pro/tuning_sampler.py). |
| C6 | Real-time monitoring, visualization, LangChain summaries/fixes | Outstanding: logs/health and experiment metrics exist, but monitoring observations/dashboards do not. | A running sample workload updates metrics/dashboard within the reviewed interval; a seeded issue produces an evidence-linked summary and proposed checks/fixes. See [milestone 5](../PLAN.md#5-add-monitoring-and-diagnosis). |
| C7 | AI-generated Python snippets from conversation via LangChain | Outstanding: Python demos are authored examples. | Natural-language requests produce model-generated integration snippets; syntax, supported API use, provenance, rejection, and review behavior pass. See [milestone 6](../PLAN.md#6-generate-reviewable-pipeline-code). |
| C8 | Tests, Docker, Kubernetes, and CI/CD | Partial: tests, Docker/Compose, and GitHub Actions checks exist; Kubernetes and deployment CI/CD are absent. | Rebuilt domain-service containers, affected integration/recovery gates, CI/CD rollout/smoke tests, and supported stateless API replica scaling in a documented Kubernetes test cluster pass. See [CI](../.github/workflows/ci.yml), [recovery](verification.md#worker-and-dependency-recovery-validation), and [milestone 7](../PLAN.md#7-prepare-deployment-and-onboarding). |
| C9 | Onboarding/tutorials, use cases, advanced optimization | Partial: classification, tuning, recovery, and tool guides exist. | A clean-checkout tutorial completes local-model dialogue, history-based optimization, monitoring, AI snippet generation, and the required service/Kubernetes workflow. See [documentation roadmap](../README.md#documentation-roadmap). |

Close a row only with its specified evidence and reviewed scope. Keep failures,
selected-case skips, unavailable models/services, and hardware limits visible.
The full course deliverable requires all nine rows; the earlier milestones 1-3
completion is limited to their initial backend scope.
