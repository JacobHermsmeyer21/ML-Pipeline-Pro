# Two-stage stratification needs integer holdout counts

October 19, 2026: the first raw-drug200 preparation run produced 139 training,
31 validation and 30 test rows instead of the approved 140/30/30. After reserving
30 test rows, `170 * (15 / 85)` evaluates to `30.000000000000004`; scikit-learn's
float test-size ceiling allocates 31 validation rows.

The [preparation module](../../src/ml_pipeline_pro/dataset_preparation.py) now
calculates integer test/validation counts from the original row total with
`(rows * percent + 99) // 100`, then passes those counts to the maintained
stratified splitter. The 200-row regression and original-file browser training
both verify 140/30/30, with disjoint/exhaustive rows and every class in each split.
Small datasets still have ceiling-rounded counts and may fail class coverage;
there is no fallback that duplicates rows, removes classes or weakens stratification.

[Retained arithmetic and execution evidence](../evidence/2026-10-19-dataset-preparation/README.md)
distinguishes this floating-point mechanism from model behavior. Revisit before
changing ratio precision, minimum class counts or the split-allocation policy.
