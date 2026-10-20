# Dropping columns must preserve saved transforms and row membership

October 19, 2026: the approved column editor derives a dataset version by
projecting its verified canonical CSV. Re-running raw preparation could change
split membership, learned vocabularies, fills or feature aliases. Whole original
categorical groups are removed together; retained values, internal aliases,
target IDs, row order and splits stay unchanged.

Prepared children retain a direct reference to the original raw source and a
self-contained v2 selection manifest. They need no surviving parent record or
parent manifest at training time. Parent IDs/content hashes are provenance,
not cascade ownership. Existing v1 recipes still load. The new reader checks
the v2 recipe digest, selection provenance and exact output-feature order.

The save route uses the shared publication lock and lifecycle-generation fence.
It checks an existing matching child before loading the parent, allowing a lost
save acknowledgement to replay after parent deletion. Surviving child references
protect shared raw files from deletion. Published files are retained after
uncertain writes; cancellation waits for owned work before releasing its lock.

Evidence: [projection](../../src/ml_pipeline_pro/dataset_columns.py),
[cell/transform regressions](../../tests/test_column_api.py),
[real transaction/deletion checks](../../tests/integration/test_dataset_columns.py),
and [browser/shared-volume evidence](../evidence/2026-10-19-dataset-columns/README.md).
The browser also verifies removal of a column literally named `__proto__`;
frontend override dictionaries must support source names without prototype setters.

Limits: dropping an input removes it from the new training-ready CSV, while
earlier versions/raw-source files retain original values. This is not permanent
erasure, a leakage detector or a model-quality improvement claim. Revisit before
adding partial one-hot selection, refitting transformations, mutable versions,
parent cascades, or independently deployed older schema/recipe readers.
