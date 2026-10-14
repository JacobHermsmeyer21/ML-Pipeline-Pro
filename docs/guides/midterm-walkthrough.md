# Complete midterm walkthrough

Use one classification dataset/model, small Bayesian searches and one evaluated
7B profile. The [course checklist](../project/course-requirements.md) remains the
acceptance record; historical failures and broader production work remain visible.

The original ten dialogue and seven code-generation gates pass on the retained
final 7B run. Earlier attempts timed out under slower local inference; no deadline,
assertion or generated output was relaxed/repaired. Run the [acceptance preflight](guided-midterm-demo.md#reproduce-acceptance)
before class, with the local runtime warmed and other heavy work quiescent. The
faster 3B candidate failed semantics and is excluded. See the [profile evaluation](../plans/2026-10-13-small-model-profile-plan.md)
and [final evidence](../evidence/2026-10-13-midterm-delivery/README.md).

1. Install the locked environment per [setup](setup.md), then the explicit 7B
   artifact/runtime/tokenizer per [local setup](local-model-setup.md). Use `7b`
   instead of the historical 14B diagnostic commands. No paid API or model training.
2. Start Docker and the [three domains, monitoring and evaluated AI](monitoring-demo.md).
   Check readiness and open the Grafana workload dashboard on 3000.
3. Run the bounded walkthrough below. It registers real inputs, trains, completes
   three-trial tuning, saves a model version and records measured inference observations.
4. Inspect its saved dialogue/history: the model reads actual validation results,
   proposes tuning using refreshed history/current budgets, and saves a reviewable
   generated Python draft. Check every proposed parameter before use.
5. Demonstrate [Kubernetes](kubernetes-demo.md) and inspect deployment CI evidence.

```powershell
uv sync --locked --extra training
uv run --locked --extra training python examples/warm_local_model.py `
    --model 'mlpp-qwen2.5:7b-instruct-q4_K_M-json-tools-v1'
if ($LASTEXITCODE -ne 0) { throw 'Explicit local artifact load failed.' }
uv run --locked --extra training python examples/midterm_walkthrough.py `
    --confirm-demo-proposal --output artifacts/midterm-walkthrough
if ($LASTEXITCODE -ne 0) { throw 'Walkthrough failed; retain its saved output.' }
```

The flag explicitly authorizes the script's bounded test proposal; generated
Python is never executed. Without the flag the proposal is rejected after review
output is saved. Normal API use always requires a separate exact hash decision.
The script asserts per-trial 10 seconds, two trials, 40 seconds total and validation
selection, including when previous experiments used other limits. Saved replay must
retain the same proposal/draft. It fails on model/worker/assertion errors, preserving
partial results rather than presenting them as a complete demo.

The separate explicit warmup loads only the already installed artifact and requests
30-minute residency; it generates no text and performs no pull. Run it immediately
before the demo, since later calls/runtime settings can change residency. Cold model
loading exceeded the existing 20-second inference deadline in retained attempts.
Application deadlines remain unchanged, with no hidden retry or startup load.

`backend.json` contains measured training/tuning records; `workload.json` identifies
validation-fixture replay, warmup exclusion, saved checkpoint identity and declared
delay. `results.json` separates public tool facts from generated interpretation,
records the explicit test decision/history and monitoring evidence. The backend
smoke also saves a synthetic telemetry routing fixture; it is labeled separately.
No holdout metrics are shown to the model for selection or tuning suggestions.

For a smaller demonstration, use the individual
[classification/tuning tutorials](workflows.md), [guided dialogue](guided-midterm-demo.md),
[generated drafts](snippet-generation.md) and [monitoring producer](monitoring-demo.md).
Use returned IDs, current project/key headers and explicit missing-input questions.
The supported English budget syntax is narrow; conflicting/unsupported phrasing
does not establish general intent extraction. Confirmations remain required.
