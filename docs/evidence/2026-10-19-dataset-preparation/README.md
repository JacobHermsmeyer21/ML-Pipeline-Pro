# Original drug200 preparation with editable encoding

October 19, 2026, America/New_York. Some retained raw timestamps are October 20
UTC, the same local evening. Jacob approved the
[plan](../../plans/2026-10-19-dataset-preparation-plan.md) with explicit review/edit
controls for automatic encoding. Approval commit is `c14dd97`; the archived
provenance lists exact changed source hashes and deployed image identities.

The original Downloads `drug200.csv` remains unchanged, SHA-256
`10caebf3b055e149ef1e7494042031e510b47ba644f3c304bbb86c428fe89b66`.
Actual Chrome controls upload that original, choose `Drug`, preview **140 training /
30 validation / 30 test rows** and nine encoded features, save, train, verify both
artifact hashes/sizes and register a completed model version. No external
preparation script or prepared-copy upload stands in for this acceptance.

A second original-file import changes BP to HIGH=3, LOW=1, NORMAL=2 with fallback
0, and changes target IDs to DrugY=4, drugA=0, drugB=1, drugC=2, drugX=3. Saving is
disabled until the updated preview is reviewed. Its seven-feature model trains;
the checkpoint/manifest retain those exact mappings. A bounded three-trial tuning
run on this custom dataset completes final holdout evaluation with the same recipe,
and the original standalone training artifacts remain hash-valid. These are small
educational runs, not repeated accuracy or throughput claims.

| Verified boundary | Result |
| --- | --- |
| Locked dependency sync, Ruff lint/format, dependency compatibility | Pass; 116 compatible installed packages |
| Fast suite | 710 passed, 87 integration deselected, zero selected skips; 81.53% coverage (82% rounded) |
| Ordinary suite, both integration flags | All 77 passed, zero selected skips; includes concurrent prepare replay, shared read-only worker storage and actual gateway/raw caps |
| Serial isolated recovery suite | All 10 passed, zero selected skips, 356.93 seconds; existing failure/ownership/artifact gates remain intact |
| Package build | Offline cached build passes; current preparation Python/JavaScript match wheel; source archive excludes caches/evidence |
| Browser | Default and edited encoding, two real training runs, artifacts/version, reload/double click, lost-save acknowledgement/same settings retry, legacy numeric upload, unavailable preview and project clearing pass |
| Desktop layouts | 1440x900 and 1280x800 fit without horizontal overflow; implementing-assistant visual inspection |
| Actual local agent and monitoring | Agent supplies the real run's verified validation F1; all three version-filtered Grafana canvases and Prometheus checks pass |

API image `sha256:77e13367894331f5ca961fd8211f9b9eb7e6bca5a61dc08843a23ef9b7e27c59`
and worker image
`sha256:b502e1f49bcb9c53ddba105169faadfb9fae3f819a99d52071859e84bbaea388`
contain the same 53 Python files as the checked source. The API's later static-only
loading guard is verified against source/wheel and actual browser behavior. The
shared uploads volume and existing project records/artifacts were preserved.
No remote CI outcome is claimed by these local runs.

The monitoring producer performs 20 actual CPU inferences using finalized
validation-fixture rows and declares five artificial delays. These graphs measure
inference, not training loss or production performance. Heavy checks finished
before the live local-agent inspection. There was no generated-code execution,
training concurrency increase, or model/API reply-budget change.

## Failures, fixes and review limits

- Initial float split sizing produced 139/31/30: `170 * (15 / 85)` is
  `30.000000000000004`, so a ceiling makes validation 31. Integer ceiling counts
  from the original total preserve 140/30/30; exact regression and original-file
  execution pass. [Durable finding](../../memory/stratified-split-counts.md).
- The first browser harness saw an earlier success message before the second
  save completed and read the previous nine-feature record. Scoped API inspection
  confirmed the new seven-feature record already existed. Its retained failure
  report remains separate; the corrected harness waits for the exact new version
  and completed mutation, then passes the entire unchanged UI journey.
- The initial raw-cap test hit the smaller canonical-output cap first. Padding
  the source fixture reaches the intended reception boundary; the 200/413
  assertions and independent output-size tests remain intact. No old assertions
  were weakened, skipped or lowered.
- One later online package build was denied sandbox network access and left an
  older wheel, which the source-match check correctly rejected. Building offline
  from the existing cache succeeds and the refreshed wheel matches source. The
  existing cache-in-source warning remains; archive inspection proves exclusions.
- Source inspection identified file selection before configuration arrival as a
  null access. The small guard has an actual browser boundary check. No backend
  logic changed after the completed real-service gates.

Review is implementing-assistant source/boundary/visual self-review. Independent
boundary/arithmetic review was unavailable, and human usefulness review of the new
controls remains pending. Classification CSVs, bounded category expansion, random
stratification/existing splits and opt-in imputation are the supported scope.
Group/time splitting and learned ordinal/target encoders remain outstanding.

The [results](results.json), [archive member hashes](manifest.json), and
[raw archive](raw.zip) retain JUnit/coverage, source/deployment hashes, browser
reports/scripts, the earlier harness failure, arithmetic reproduction, real tuning,
agent and monitoring outcomes. They exclude original patient rows, model weights,
browser profiles and credentials. Full isolated service logs/snapshots also remain
locally under `artifacts/recovery-validation/`. Unpack the archive in a local
artifact directory to inspect/reuse its scripts and browser helper; running the
journeys creates new real demo records. Chrome and the original Downloads file
are local prerequisites. The [dashboard guide](../../guides/dashboard.md) describes
the supported user workflow.

[Default encoding](default-encoding.png), [edited encoding](custom-encoding.png),
[completed training](trained.png), [1280 layout](encoding-1280.png),
[1440 layout](encoding-1440.png), [agent inspection](drug200-agent.png), and
[actual monitoring](drug200-monitoring.png) show the local browser checks.
