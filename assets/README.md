# Evaluation assets and retained evidence

Original evidence is linked here without presenting saved results as new runs.
The root README now reports Iris; no new training was performed for that update.

* **Iris submission results:** [capture notes](iris/README.md),
  [local CSV provenance](iris/source.json), [saved experiment](iris/experiment.json),
  [dataset](iris/dataset.json), [model](iris/model.json) and
  [verified training manifest](iris/manifest.json).

* Drug200 historical run: [provenance and configuration](../docs/evidence/2026-10-19-drug200-demo/README.md),
  [saved results](../docs/evidence/2026-10-19-drug200-demo/results.json),
  [training screenshot](../docs/evidence/2026-10-19-drug200-demo/training.png) and
  [raw execution archive](../docs/evidence/2026-10-19-drug200-demo/raw.zip).
* Later classification-metrics acceptance: [scope and provenance](../docs/evidence/2026-10-20-dashboard-metrics/README.md),
  [real worker/browser results](../docs/evidence/2026-10-20-dashboard-metrics/browser-result.json),
  [fast-check log](../docs/evidence/2026-10-20-dashboard-metrics/fast.log) and
  [integration log](../docs/evidence/2026-10-20-dashboard-metrics/integration.log).

Drug200 and later metric checks cover different runs from the README's Iris table.
No training-set scores, loss curve, confusion matrix or ROC curve is claimed here.
Display fixtures in later screenshots are identified in their original acceptance
record and are not worker measurements.
