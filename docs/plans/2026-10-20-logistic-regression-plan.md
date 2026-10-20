# Add logistic regression experiments

- Status: approved; implementation in progress
- Date: 2026-10-20 (America/New_York)
- Source baseline: `37904ac` / `main`; fetched `origin/main` matches
- Request: a plan for logistic regression only, following the one-night scope discussion
- Human reviewer/approval: Jacob; approved October 20, 2026 in chat
- Independent review: availability unknown; seek review if implementation changes concurrency or resource arithmetic

## Proposed behavior and purpose

Users can create a named model with either the existing MLP architecture or
logistic regression, then train fresh experiments under that model. The dashboard
shows the selected algorithm and appropriate settings. Logistic regression runs
produce the same validation/test metrics, downloadable artifacts, and registered
versions as MLP runs. Existing models and experiments continue to work.

Implement logistic regression in PyTorch as a linear layer with class logits and
cross-entropy loss: binary logistic classification for two classes and multinomial
softmax regression for more classes. There is no hidden layer or ReLU. Reuse the
existing Adam/minibatch training loop and validation checkpoint selection. This is
gradient-trained logistic regression, not scikit-learn's solver or a guarantee of
convergence. No new dependency or artifact extension is needed.

This adds a useful linear baseline for course requirements C4/C9 in the
[course checklist](../project/course-requirements.md). It does not close a missing
course requirement or establish new AI/deployment acceptance.

## Clarification and critique

Source establishes that model records currently allow only PyTorch/classification/
MLP; the worker fetches the model but does not pass its architecture into training.
Both training and checkpoint evaluation construct an MLP. Tuning and conversation
configuration schemas assume MLP settings. Registered versions reference `model.pt`.

The smallest alternative is retaining MLP alone; its existing tuning already
supports baseline comparisons. Adding logistic regression is justified by making
algorithm comparisons possible and the model selector meaningful. A scikit-learn
implementation is familiar but would require a second fitting, cancellation, and
serialization path. The proposed PyTorch implementation preserves existing bounds
and artifact loading. KNN is excluded.

Human decisions proposed for this review: accept gradient-trained PyTorch logistic
regression, include binary and multiclass classification, retain MLP as the default,
and defer logistic regression tuning and AI-created training configurations. No
remaining source question blocks this proposal; these scope choices need approval.

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | Create an immutable `logistic_regression` model; omitted architecture still means `mlp`. | API/schema tests and dashboard creation walkthrough. |
| F2 | Functional | Train a fresh linear classifier using logistic settings and training-only standardization; report existing accuracy and macro-F1 metrics. | Binary and three-class fixtures; independent metric calculation; saved preprocessing checks. |
| F3 | Functional | Download, verify, reload, and register the trained checkpoint; reloaded predictions match the selected trained state. | Artifact/hash tests, reload tests, real queued-worker run and version registration. |
| F4 | Compatibility | Old model/config/checkpoint records retain MLP behavior, defaults, submission fingerprints and replay. | Legacy fixtures, same-key replay tests, existing MLP/tuning suite. |
| F5 | Functional | Reject mismatched configs and logistic tuning/AI mutation requests explicitly, without queued work or an MLP fallback. | API and conversation action tests reaching each unsupported boundary. |
| N1 | Reliability | Preserve project scoping, serial CPU execution, budgets, ownership, cancellation, recovery and artifact integrity. | Existing gates plus logistic worker runtime-expiry and recovery cases. |
| N2 | Usability | Algorithm labels and controls match the saved model and submitted request. | Browser walkthrough covering model switching, review, retry and run details. |

## Constraints and scope

No KNN, automatic logistic tuning, new inference endpoint, probability/calibration
UI, AI-generated logistic snippets, service split, parallel training or dependency
update. Existing MLP AI workflows remain available. Monitoring observation storage
and dashboard remain unchanged; registration alone does not create measurements.

Preserve `/api/v1` routes and existing MLP payloads. New schemas are additive.
Model architecture cannot change after creation; experiments never reuse another
experiment's weights. Preserve dataset preparation, project-scoped references,
correlation errors, idempotency, ownership transactions, and test-data isolation.
Follow the [artifact preservation finding](../memory/evaluation-artifacts.md).

## Design

1. **Records and configuration.** Extend `ModelCreate.architecture` to
   `mlp | logistic_regression`; keep `framework=pytorch` and the existing defaults.
   Retain `TrainingConfig` serialization exactly for MLP. Add a strict
   `LogisticRegressionConfig` variant distinguished by a required
   `algorithm: logistic_regression` field. Its fields are `seed`, `epochs`,
   `batch_size`, `learning_rate`, `max_runtime_seconds` with existing bounds and
   defaults, plus `l2_strength` (finite, 0 through 1, default 0). Exclude hidden
   units. Use coupled request/result/persistence config unions; absent config keeps
   the existing MLP default. Logistic submissions must supply the explicit variant.
   Check variant against the referenced model before first admission and again in
   the worker. Return scoped `409 model_config_mismatch` on mismatch. Existing
   same-key replay checks precede new admission checks; do not alter old canonical
   request serialization or hashes. No bulk migration.
2. **Training.** Pass the model architecture explicitly from `execution.py` into
   training. Use `Linear(feature_count, class_count)` for logistic regression and
   keep the MLP construction unchanged. Standardize from training rows only. Use
   existing deterministic seeds, single CPU thread, budget/cancellation checks,
   validation selection and final test evaluation. For logistic regression define
   the loss as cross entropy plus `0.5 * l2_strength * sum(weight ** 2)`; leave bias
   unpenalized. Check finite loss/metrics and retain the best validation checkpoint.
   Reject incompatible stored records explicitly rather than guessing a model type.
3. **Artifacts.** Keep `model.pt` and `manifest.json`. New logistic checkpoints
   record a format version, algorithm, linear state, class/feature dimensions,
   feature order, mean/std and existing preparation metadata. Load tensors and
   primitives through `torch.load(..., weights_only=True)` after hash/size checks;
   never pickle an estimator. Missing algorithm in historical checkpoints means
   legacy MLP. Unknown tags, dimension mismatches and model/config conflicts fail
   clearly. Extend checkpoint reconstruction/evaluation for both architectures;
   preserve original training artifacts during any final evaluation. Registration
   continues to reference the experiment's verified checkpoint.
4. **Dashboard.** Add an architecture selector to model creation, with MLP selected
   initially. Show architecture beside model names and in run details. Selecting
   logistic regression hides hidden units and shows L2 strength; common training
   controls remain. Review shows algorithm and only applicable settings. Build the
   correct config variant; keep pending submissions immutable across model changes
   and reconnect/retry. Explain that each experiment starts fresh.
5. **Deferred capabilities.** Before tuning admission, reject logistic models with
   scoped `409 unsupported_model_algorithm`; keep MLP tuning unchanged. Preserve
   current MLP-only AI mutation schemas for this slice. Add explicit host/tool
   preflight rejection of logistic training/tuning proposals before saving or
   confirming an actionable proposal; enforce again at action execution for stale
   proposals. Read/list/compare tools may inspect logistic records. Explain the
   limitation in model-visible guidance and UI errors; never execute an MLP config
   for a logistic model. Update fixtures, contract schemas and relevant grounding
   checks without expanding generated snippets or claiming live-AI acceptance.
6. **Documentation.** Update README model/experiment payload documentation and
   `docs/guides/dashboard.md` with both algorithms, settings, gradient-training
   semantics, limitations and a compare/register example. No new env setting.

## Acceptance and verification

Implement in order: schemas/admission compatibility, training/checkpoint reload,
unsupported-capability guards, dashboard/docs, then real-service acceptance. Run
targeted tests at each step. Do not change existing MLP assertions to accommodate
logistic regression; add tests for the new requirements.

Use fixed, separable binary and three-class numeric datasets with explicit
train/validation/test splits and fixed seeds. Include a real worker comparison
against MLP on the same dataset version; no requirement that one algorithm wins.
Record actual settings, metrics, artifact hashes, commands, revision and runtime.
Reloaded class predictions must match exactly; independently computed accuracy/F1
must agree within `1e-6`. Assert no hidden layer, regularization excludes bias,
test labels never select a checkpoint, and scaling uses training rows only.

Run all fast checks from [verification](../guides/verification.md#fast-checks):

```powershell
uv sync --locked --extra training
uv run --locked --extra training ruff check .
uv run --locked --extra training ruff format --check .
uv run --locked --extra training pytest -m "not integration" --cov
uv pip check
```

Because worker/persistence behavior changes, run ordinary integration with both
`MLPP_RUN_INTEGRATION=1` and `MLPP_RUN_WORKER_INTEGRATION=1`, then serial isolated
recovery with `MLPP_RUN_RECOVERY_INTEGRATION=1`, using the guide's distinct setup.
Add a logistic recovery case proving the same experiment/config survives worker
loss, and an expiry case proving no successful artifact publication after budget
failure. Check duplicate submission, foreign-project references, incompatible
configs and version registration through the real API/worker. Preserve existing
MLP tuning ownership and final-evaluation recovery cases. Missing services or skips
are gaps, not acceptance. Run a browser walkthrough for F1/N2 and retain evidence
under `docs/evidence/2026-10-20-logistic-regression/` when implementation occurs.

Review the final diff for legacy serialization, architecture dispatch, checkpoint
loading, artifact publication and unsupported-action guards. If concurrency or
resource arithmetic changes, seek an independent reviewer and record availability,
scope, findings and resolutions; self-review is not independent review. Human
usefulness review checks the model selector/settings and comparison flow.

## Risks and rollback

Default training settings may underfit; report measured outcomes without promising
convergence or superiority. New union schemas can affect AI adapters and old
idempotency hashes; compatibility tests are required before broadening UI access.
Mixed old/new workers are unsupported for logistic jobs: deploy compatible API,
worker and dashboard versions together before enabling creation.

Rollback disables new logistic submissions/proposals and retains support for
reading their records/artifacts. Drain or cancel logistic jobs before worker
rollback. A full old binary cannot decode new records/configs: preserve a compatible
reader or restore a pre-change backup in a disposable demo environment. Do not
rewrite logistic records as MLP or delete records/artifacts as an implicit rollback.

## Human review and approval

- Reviewer: Jacob.
- Decision/date/reference: approved October 20, 2026; chat request: "i approve the logistic regression plan, implement it".
- Approved scope: this logistic-only PyTorch implementation, including
  compatibility, dashboard, rejection guards, docs and required verification.
- Material changes, including a scikit-learn backend or logistic tuning/AI mutation
  support, require an updated plan and renewed review.

## Implementation outcome

Implemented in the working tree after Jacob's explicit approval. Automated
acceptance is in progress; see the [execution record](../evidence/2026-10-20-logistic-regression/README.md)
for scope, test justification, provenance, results, reviews and remaining gaps.
No logistic tuning, AI mutation, alternative backend or concurrency change was
introduced. The approval record is published as `10e9f37` on `origin/main`.
