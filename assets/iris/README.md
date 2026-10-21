# Iris submission evidence

Captured October 21, 2026 via read-only HTTP requests to the existing local API,
project `demo`, while the documentation checkout was at `10f1ae2`. The running
service's source revision was not independently established. No retraining,
evaluation mutation, dataset update or model replacement was performed.

* [source.json](source.json): inspected `Downloads/IRIS.csv` hash, size, schema,
  row count and species counts. The source attribution is Kaggle per Jacob;
  the exact download listing was not recorded. The local CSV has five lowercase
  columns and no `Id`, unlike the supplied six-column Kaggle description.
* [dataset.json](dataset.json): `GET /api/v1/datasets/d5` response. Its original
  input hash exactly matches the local file's SHA-256
  `9194e2b71f7144e7d192a1c38f9a54f26b0e8f705c0929b8225b0cd10275efd1`.
* [experiment.json](experiment.json): `GET /api/v1/experiments/e32` response,
  recording successful completion, the configuration, all four validation/test
  metrics, selected epoch, artifact hashes/sizes and runtime dependencies.
* [model.json](model.json): saved model metadata from its canonical-ID read route.
* [manifest.json](manifest.json): downloaded through
  `GET /api/v1/experiments/e32/artifacts/manifest.json`; verified against the
  experiment's SHA-256
  `36b1884deefdc131c0973d5c96cd08a04062ddd83c52c5ce676c7ef95bee958f`
  and 5,032-byte size. It agrees with the saved metrics and includes the reviewed
  four-column numeric recipe, label mapping, stratified split/class counts and
  output/input hashes. The checkpoint was not downloaded or executed in this audit.

The run completed at `2026-10-21T03:49:59.816Z`, October 20 at 23:49 EDT.
Selection maximized validation F1 and retained epoch 6 of the 30-epoch run.
The README rounds saved scores to six decimals. Training-set evaluation metrics
and loss were not recorded. One small split is not repeated performance evidence;
these records establish what was saved, not an independent reproduction of model
predictions or full environment provenance. Original CSV rows are not redistributed.
