# Changing a CSV target must also update inferred features

October 19, 2026: the Downloads `drug200.csv` has distinct headers. Selecting it
autofilled every column as a feature because neither default name (`target`,
`split`) appeared in its header. Changing the target to `Drug` left `Drug` among
the features. The upload's `DatasetCreate` validator then correctly returned
`422 invalid_dataset: Dataset columns must be distinct`. This was a metadata
overlap, not duplicate source headers.

The dashboard now removes the current target/split from the existing features
when either mapping changes, preserving the user's remaining feature subset.
Submission also checks empty features, duplicates and overlaps before sending
the file. Server validation and the numeric-only CSV contract are unchanged.

Raw drug200 still needs categorical encoding, integer labels and explicit splits.
A separate demo copy uses fixed one-hot vocabularies and label IDs, then seeded
per-class splitting. Existing training fits numeric normalization on training rows
and selects its checkpoint by validation F1. Do not mistake the mapping fix for
a general CSV importer or relax the loader to accept unprepared categorical data.

[Retained browser reproduction and successful demo](../evidence/2026-10-19-drug200-demo/README.md)
include before/after requests, real worker results and file hashes. Revisit when
adding a reviewed data preparation interface or changing mapping controls.
