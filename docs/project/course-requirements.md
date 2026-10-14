# Course implementation requirements

Source: implementation instructions supplied by the repository user on October 6,
2026 for this machine learning class project. The numbered text below preserves
the supplied requirements. The mapping and implementation choices are the
repository's interpretation, not an instructor's grading decision. No grading
weights, deadline, or additional training requirement were supplied.

Use this document as the acceptance checklist for the course deliverable. The
[roadmap](../../PLAN.md) orders work, the [status record](project-status.md) retains
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

On October 13 Jacob confirmed all nine rows are required for next week's midterm
and approved the [minimal delivery scope](midterm-scope.md) and
[plan](../plans/2026-10-13-midterm-delivery-plan.md). Target one local classification
demo, guided AI, one monitoring dashboard/seeded issue and Kubernetes test-cluster
deployment. Broader drift, large benchmarks and production hardening are deferred.
Existing model failures remain open; scope approval does not establish delivery.

- Use Python/uv with its `.venv`, PyTorch, PyMongo, FastAPI, Optuna Bayesian tuning,
  and GitHub Actions. These choose among the stated alternatives; TensorFlow,
  Flask, reinforcement learning, conda, and Jenkins are not additional obligations.
- Use LangChain with a locally served pre-trained language model for dialogue,
  suggestions, monitoring explanations, and AI-generated Python snippets. The
  local integration proposed in the [conversation plan](../plans/2026-10-06-conversation-workflows-plan.md)
  uses `ChatOllama`; its model artifact and runtime must be selected and evaluated.
  No paid external model API, provider key, custom language-model training, or
  fine-tuning is required for this course scope. Local inference still uses
  compute and memory. The existing classifier is a separate managed ML workload.
- Model management, tuning, and monitoring must be separately deployable REST
  services. Sharing a repository, image, or MongoDB deployment is compatible with
  that target; modules in one API process do not satisfy the service separation.
  Preserve [transactional tuning ownership](../memory/tuning-parent-fence.md) and
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

The table records the latest minimal delivery; preceding dated progress notes
retain their historical revisions and are superseded where evidence below says so.

Status is source-grounded at `ba6334f` / October 6, 2026. Existing test results
retain the revisions and limits in the linked records; no new application tests
were run for this documentation alignment.

Rechecked against `c28ae06` on October 8, 2026: coverage remains unchanged.
The conversation design now has October 7 human approval, but the required
local-model integration and its acceptance evidence remain outstanding.

Person A's October 8 foundation adds locked LangChain/Ollama dependencies,
conversation schemas, the model interface, and chat settings. The
[development guide](../guides/conversation-development.md) records the limited scope;
the next A1 slices add a local LangChain adapter with deterministic SDK/HTTP
tests, durable turn/proposal storage with real-MongoDB claims/replay evidence,
and a bounded host loop that grounds supplied API facts and saves proposals.
Authenticated chat/history/action routes and exact-action dispatch/recovery now
exist. October 9 adds installed Qwen profiles and verified token admission with
retained real-runtime evidence. Every ten-scenario model evaluation failed;
reliable guided dialogue/history, independent review and clean-checkout
onboarding remain outstanding. No course row is closed by this slice.

October 10's approved native completion protocol now translates a strict
model-facing reply function without changing public tools or action permissions.
The selected 7B profile still fails the original gate (three of ten scenarios
passed); C3/C5 remain outstanding. See the
[typed-completion outcome](../plans/2026-10-09-conversation-typed-completion-plan.md#implementation-outcome).

| ID | Requirement | Current minimal coverage | Retained evidence / limits |
| --- | --- | --- | --- |
| C1 | Python environment and required libraries | Demonstrated: clean committed checkout, fresh locked venv, LangChain/PyTorch/PyMongo and verified external runtime/tokenizer. | [Clean setup evidence](../evidence/2026-10-13-midterm-delivery/README.md); reused explicitly installed external model, no automatic pull. |
| C2 | Separate model-management, tuning, monitoring services | Demonstrated: three independent FastAPI processes, shared image/storage and gateway in Compose/Kubernetes. | [Domain guide](../guides/domain-services.md), [monitoring](../guides/monitoring-demo.md), [Kubernetes](../guides/kubernetes-demo.md); contracts/ownership preserved. |
| C3 | LangChain, pre-trained model, dialogue/history | Demonstrated: final original ten-case guided 7B gate and actual-ID/history tutorial pass. | [Guided gate](../guides/guided-midterm-demo.md); missing-input/evidence checks, human examples, earlier native/timing failures retained. |
| C4 | MongoDB parameters, versions, results/metrics, indexes | Demonstrated for one classification workload: saved configurations/versions/trials/metrics and scoped index/query evidence. | [Delivery evidence](../evidence/2026-10-13-midterm-delivery/README.md); small measured demo scale, no 10,000-record speedup claim. |
| C5 | Automated optimization with LangChain and history | Demonstrated: three-trial Bayesian search includes a TPE posterior suggestion; real model proposes a bounded follow-up from refreshed history. | [Complete walkthrough](../guides/midterm-walkthrough.md); validation selection, explicit exact decision, persisted trials and original recovery gates. |
| C6 | Monitoring, visualization, LangChain summaries/fixes | Demonstrated: 20 actual inferences, five declared delays, 15-second scraping/refresh, dashboard/rule and evidence-cited advice. | [Monitoring guide](../guides/monitoring-demo.md); visibility observed at 4.1 seconds, unknown/partial states explicit, human quality reviewed, no automatic fix. |
| C7 | AI-generated Python through LangChain | Demonstrated: original seven-case gate passes; four draft profiles validated, saved/replayed and human examples reviewed. | [Snippet guide](../guides/snippet-generation.md), [guided results](../guides/guided-midterm-demo.md); generated code never executed, older timeout/rejection runs retained. |
| C8 | Tests, Docker, Kubernetes, CI/CD | Local verification passes; final remote deployment run pending after CPU scheduling correction. | [Deployment guide](../guides/kubernetes-demo.md); 570 fast, 63 ordinary, ten serial recovery; actual two-pod replay/startup fault evidence; prior failed CI retained. |
| C9 | Documentation/tutorials/use cases/optimization | Demonstrated: combined fresh-checkout tutorial completes classification, Bayesian tuning, history, drafts and measured diagnosis; Kubernetes AI tutorial also exercised. | [Combined guide](../guides/midterm-walkthrough.md), [evidence](../evidence/2026-10-13-midterm-delivery/README.md); external runtime/model reused explicitly, production/research extras deferred. |

Close a row only with its specified evidence and reviewed scope. Keep failures,
selected-case skips, unavailable models/services, and hardware limits visible.
The full course deliverable requires all nine rows; the earlier milestones 1-3
completion is limited to their initial backend scope.

October 13 guided update: the original ten conversation and seven snippet cases
now pass on the opt-in pinned 7B protocol; real-model HTTP draft/replay and nine
affected store cases pass. This supersedes the table's model-gate failure status
for guided mode, while preserving native/older runs as historical evidence.
C3/C5/C7 remain partial pending human quality and combined onboarding. See the
[guided results](../guides/guided-midterm-demo.md).

October 13 delivery update: C2/C6 now have independent monitoring, actual measured
inference observations, one Prometheus/Grafana threshold/dashboard and local-model
advice. C8 now has an exercised local Kubernetes deployment, two model API pods'
direct replay and a committed CI/CD job. C4 includes measured scoped query/index
evidence at the declared demo scale, not the deferred 10,000-record benchmark.
The complete actual-ID/history walkthrough and human draft/monitoring reviews pass;
final clean-checkout/remote deployment closure remains pending. See the
[combined guide](../guides/midterm-walkthrough.md) and
[delivery outcome](../plans/2026-10-13-monitoring-deployment-plan.md#implementation-outcome).
