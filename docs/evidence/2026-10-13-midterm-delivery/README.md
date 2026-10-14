# Minimal midterm delivery evidence

[Raw execution/source archive](raw.zip) and [checksums/provenance](results.json)
retain passing and failed attempts. Client date is October 13; raw UTC timestamps
may fall on October 14. Generated interpretation is separate from measured results.

| Check | Measured outcome |
| --- | --- |
| Fast / ordinary / isolated recovery | 570 / 63 / 10 pass; ordinary uses both flags, recovery serial |
| Original local-model dialogue / snippets | 10 / 7 pass at original 20-second calls/120-second suites; no repair/retry/execution |
| Locked build/dependencies | Compatible; 44 canonical wheel modules; private/cache/model files absent |
| Clean onboarding | Pushed checkout `2945bd2`, fresh venv/storage, built image and actual complete AI walkthrough pass |
| Kubernetes | All domains, actual local AI, three-trial tuning and direct replay through both model API pods pass |
| MongoDB startup recovery | Injected DNS failure, one automatic process restart, writable primary and identical saved IDs/config version |
| Measured monitoring | 20 actual CPU inferences, five declared 150 ms delays; Prometheus visibility 4.1 seconds; Grafana query/refresh verified |
| Human / independent review | Jacob: drafts/missing guidance and monitoring clear/useful; separate same-vendor boundary review, different-vendor unavailable |
| Remote CI | All five jobs pass at `3ac78d3`: tests 3.11/3.13, legacy/three-domain Compose, isolated recovery and actual kind deployment; [successful implementation CI](https://github.com/JacobHermsmeyer21/ML-Pipeline-Pro/actions/runs/38505646188) |

The clean checkout reuses an explicitly installed verified external runtime/model
and checksum-pinned tokenizer; it does not claim a fresh model download. Its isolated
Compose project/volumes were removed afterward, preserving the existing stack.
Kubernetes uses an explicit disposable name/context; kubeconfig credentials, model
weights, `.env` and full runtime startup dumps are excluded from this archive.

Prior 7B runs timed out on the tuning draft at roughly 24 seconds. Later throughput
improved: the final original gate's longest call is 3.05 seconds. Cause of timing
variation is unestablished. A separate 30-second diagnostic already completed all
calls below 20 seconds; no timeout change was selected. Synthetic fixture metrics
in ten/seven gates are not training measurements. Raw successful/failed cases are
not combined to manufacture a pass.

The tested 3B candidate passes only five/ten dialogue and one/seven draft cases;
its additive whitelist/setup choice was removed. Structural tokenizer compatibility
does not establish model quality. Installed identity/license and failed outputs
are retained as a rejected approach.

The first remote run timed out with one API pod unavailable and no cause evidence.
The instrumented rerun shows Grafana Pending with `Insufficient cpu`; ten other pods
run. Corrected requests reserve 600m across eleven pods rather than 1100m, retaining
limits, memory and serial execution. This is scheduling evidence, not measured peak
concurrent capacity. The startup-recovery fix addresses a separate proven mechanism.

The dashboard uses a capped five-minute window, nullable label accuracy and declared
seeded delays. No generalization, production latency, large-scale performance,
public hosting or automatic remediation claims. Final evidence source revisions,
working-tree hashes and runtime/package identities qualify each saved run.
