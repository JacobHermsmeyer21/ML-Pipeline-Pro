# Final evaluation must preserve recorded training artifacts

Recorded October 6, 2026 from the existing manifest recovery fix and its validation.

Writing final evaluation into the training attempt's directory can overwrite a
manifest whose hash is already recorded. If persistence is interrupted or ownership
is rejected, recovery then cannot verify the original training manifest. Service
evaluation uses a separate `WORKER_TOKEN-evaluation` attempt directory and changes
recorded artifact references only after the authorized commit.

Evidence: [evaluation execution](../../src/ml_pipeline_pro/tuning_execution.py),
[replay regressions](../../tests/test_tuning_execution.py), and
[recorded validation](../project/project-status.md#ownership-fix-validation), introduced
in commit `a2a089c`. The documented validation predates this memory entry.

The local tuning demo similarly retains `local/manifest.json` and writes the
winner's evaluated manifest under `final/`; follow the current artifact references,
as explained in [the manifest guide](../project/project-status.md#reading-a-local-tuning-manifest).
A validation-only trial manifest is expected, even for a subsequently selected winner.

Revisit if artifact layout/storage changes. Verify interruption before reference
persistence leaves the original hash-valid artifacts available for replay. This
does not establish a retention, garbage-collection, or backup policy.
