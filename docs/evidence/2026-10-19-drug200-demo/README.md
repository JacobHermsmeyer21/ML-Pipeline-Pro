# Drug200 dashboard demo and column-mapping correction

Jacob reported `Dataset columns must be distinct (invalid_dataset)` with reference
`c7064d87d9e7fc9253bd5cb79a212413` while using Downloads `drug200.csv`. The running
model API log confirms that request returned 422. The CSV contains 200 rows and
six unique headers. Installed Chrome reproduced the error: file selection
inferred all six columns as features, then changing the target to `Drug` retained
`Drug` in the feature list. The saved request proves the overlap.

The local correction updates inferred features when the target/split changes and
rejects duplicate/overlapping mappings before upload. A manual feature subset
stays intact. This follows the debugging/compressed loop: it restores the approved
editable mapping behavior without changing the upload API, numeric loader,
defaults, publication, ownership or concurrency.

## Prepared input and completed run

The original Downloads file is unchanged. Its SHA-256 is
`10caebf3b055e149ef1e7494042031e510b47ba644f3c304bbb86c428fe89b66`.
Raw features include categorical `Sex`, `BP` and `Cholesterol`, labels are strings,
and no split exists. The current dashboard requires a prepared numeric CSV.

The local copy `artifacts/drug200-demo/drug200-demo.csv` has SHA-256
`79e503b35338bf89eb38e0f7ad07d030caff401a02f750bc2f7a2febd99f917c`.
It uses `Age`, `Na_to_K`, and seven one-hot category features. Fixed vocabularies
are `Sex: F/M`, `BP: HIGH/LOW/NORMAL`, `Cholesterol: HIGH/NORMAL`; labels are
`DrugY=0`, `drugA=1`, `drugB=2`, `drugC=3`, `drugX=4`. No category vocabulary or
numeric statistics are learned from validation/test rows. Seed 42 shuffles each
class; floor 60% train, floor 20% validation and the remainder test gives
**117 train / 38 validation / 45 test** rows, with every class in each split.
The existing trainer fits normalization on training rows only.

| Saved project `demo` record | Value |
| --- | --- |
| Dataset | `drug200_demo` / `v1`; `667f758c-dfd2-4afd-8ee3-f51234d98bd3` |
| Model | `drug200_classifier_235150`; `6d2e21f7-c0d4-42fc-b6b5-164c913a2170` |
| Experiment | `4456f825-3710-41f7-bd74-9fae5430be46` |
| Registered version | `v1`; `231b8e87-0e58-434d-bc54-ecf45689b62f` |
| Config | Seed 42, 30 epochs, batch 16, learning rate 0.01, hidden units 16, 60-second maximum |
| Validation | Accuracy 1.0, macro F1 1.0; selected epoch 24 |
| Final held-out test | Accuracy 0.9555555582; macro F1 0.9586666667 |

Actual dashboard controls uploaded the prepared copy, created a model, reviewed
and submitted one training run, and registered the completed version. The serial
worker read the existing shared uploads volume. Both saved artifacts pass their
recorded SHA-256 and size checks; refresh retains the dataset and experiment.
These are results of one small educational split, not repeated performance claims.

The installed local 7B agent read the actual experiment and returned a verified
`metrics.validation_f1=1.0` fact without proposing or submitting another job.
The existing monitoring producer recorded 20 real CPU inferences against the
finalized checkpoint, including five declared 150 ms artificial delays.
Version-specific Prometheus queries and all three actual Grafana canvases pass.
These graphs replay validation rows after finalization; they are separate from
the held-out test metrics and do not write training artifacts. The bounded
five-minute summary eventually expires; older scrapes remain in the graph range.

## Verification and provenance

- Baseline `14c62f85d991d2a5bf7c72947e3812550eece493`; changed JavaScript is identified
  by its saved hash and matches both the built wheel and running model API.
- Locked sync, Ruff lint/format, and dependency compatibility pass. Fast gate:
  **684 passed, 85 integration deselected**, 81% rounded coverage, 52.15 seconds.
- `uv build` passes. Wheel JavaScript matches source; wheel/sdist contain no uv
  cache despite the existing cache-in-source warning.
- Chrome reproduces the original failure and verifies target edits, split edits
  preserving manual subsets, rejected duplicate features, manual target overlap,
  target/split conflict, and the original raw CSV's missing split boundary.
  The prepared upload and real worker completion pass the original precondition.
- The same desktop Compose project preserves existing volumes and workers. Only
  model API was rebuilt/recreated for this static-asset change. Backend Python,
  persistence, worker code, image recipe and mounts are unchanged. Full ordinary
  and isolated recovery suites were not rerun; this evidence covers the actual
  upload-to-worker journey, not those full suites.
- Review is implementing-assistant self-review. No independent review is claimed.

Initial sandbox Chrome capture and package-index access needed authorized tool
execution. Two overlapping initial browser captures timed out; the subsequent
isolated reproduction and corrected implementation checks passed. uv's native
stderr appears as PowerShell error records even on successful commands; command
exit status and saved reports distinguish this from failures. Browser checks
use the installed Chrome with a separate profile and preserve the original
application assertions and model/turn budgets.

The first graph capture verified the agent but found only one canvas because the
remaining iframes were outside the viewport and lazy loaded. Its failure is
retained. Scrolling each panel into view, as the existing graph harness does,
passes all three canvas/no-data checks and Prometheus queries. Only the graph
capture was repeated; no inference retry, application change or weaker assertion
was needed.

The [raw archive](raw.zip) retains preparation/execution scripts, safe API results,
checks and source/deployment hashes; [member hashes](manifest.json) verify each
payload. It excludes input/output patient rows, browser profiles, credentials and
model checkpoints. The local prepared CSV and published upload remain available
on this computer. [Results](results.json) identify final outcomes and review limits.

Refresh [the dashboard](http://127.0.0.1:8000/dashboard/) and select the saved
dataset/model. The [guide](../../guides/dashboard.md#column-mapping-and-an-unprepared-csv)
explains the mapping and prepared-file requirement.

[Completed training](training.png), [agent inspection](agent.png), and
[rendered monitoring panels](monitoring.png) show the local browser run.
