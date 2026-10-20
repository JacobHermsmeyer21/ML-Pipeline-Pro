# Dashboard classification metrics acceptance

October 20, 2026; [approved plan](../../plans/2026-10-20-dashboard-classification-metrics-plan.md).
Implementation was verified against `a917da0` plus the metrics-only source changes.
[Source hashes and tooling](provenance.json) identify the tested overlay. Concurrent
short-ID work was excluded from the isolated source copy, including its dashboard
reference changes. The existing demo stack and records were not upgraded or erased.

## Results and provenance

- Locked sync passed using repository-local uv 0.12.23 and the existing Python
  3.11.5 environment. Because uv was absent from PATH, commands used
  `.tools/uv/bin/uv.exe` and the workspace-local cache. The isolated checks used
  `UV_PROJECT_ENVIRONMENT` pointing to that synchronized environment, `--no-sync`,
  and `PYTHONPATH` pointing to the isolated source/root.
- Ruff check and format check passed (291 Python files). Dependency compatibility
  passed for 121 installed packages.
- [Fast log](fast.log) / [JUnit](fast.xml): 829 passed, 118 integration cases
  deselected, 80% aggregate coverage; no skipped selected cases or warnings.
  Command: `uv run --no-sync --locked --extra training pytest -m "not integration" --cov`.
- [Integration log](integration.log) / [JUnit](integration.xml): eight selected
  real-service cases passed, no skips. Command: `uv run --no-sync --locked --extra
  training pytest tests/integration/test_experiments.py tests/integration/test_tuning.py
  -m "integration and not recovery"`. Both ordinary integration flags were `1`.
  The isolated Compose project `mlpp-metrics-validation-20261020` used
  `compose.yaml` and `tests/integration/compose.validation.yaml`, API port 18000,
  MongoDB port 37017 and Redis port 16379. API, worker and scheduler were rebuilt
  from the isolated source; existing demo containers were left running.
- [Final browser report](browser-result.json): three real serial worker runs
  (binary MLP, binary logistic, multiclass logistic), artifact hash/size checks,
  independently reconstructed predictions and scikit-learn metric checks,
  matching manifest metrics, all four validation table/detail values and separate
  held-out test details. Distinct display-only values, measured zero, missing
  legacy metrics and running/empty snapshots passed at 1440px and 390px.
  [Desktop](desktop.png) / [mobile](mobile.png) screenshots show the distinct-value
  snapshot; those injected values are display fixtures, not worker measurements.
  Command: `python scripts/verify_metrics_dashboard.py --origin http://127.0.0.1:18000
  --output artifacts/metrics-browser-final`, using the already installed optional
  Playwright 1.64.0 in `.tools/column-browser` and local Chrome. Its full report
  retains run IDs, measured metrics, source hashes and tool provenance.

The first shared-workspace targeted run passed all 31 training/logistic cases but
failed 19 tuning cases before scoring: concurrent `tests/memory.py` short-ID edits
assigned `short_id` to `TuningRecord`, which has no such field. Those edits were
preserved and excluded from the metrics-only verification snapshot; all 50
targeted cases then passed. This does not establish acceptance of short-ID work.
Two intermediate browser attempts failed in the new harness (a Playwright handler
argument and an incorrectly encoded expected dash); both were corrected before
the retained final pass. They were not application scorer failures.

## Scope and limits

New assertions compare macro scores to scikit-learn on imbalanced binary and
multiclass inputs, absent predicted/true classes and all-wrong predictions.
Additional tests verify all evaluated split scores in saved manifests and absence
of test metrics from validation-only training. Logistic checkpoint/final-evaluation
checks now include precision and recall; existing assertions were retained.

Existing fast tuning regressions verify validation-only winner selection,
test-label isolation and preservation of original artifact hashes. Ownership and
recovery mechanisms are unchanged. The separate recovery suite and unrelated
ordinary integration cases were not rerun. No live AI, independent review, human
usefulness acceptance or deployment to the user's demo is claimed. Visual inspection
and implementation review were performed by the implementing assistant.
