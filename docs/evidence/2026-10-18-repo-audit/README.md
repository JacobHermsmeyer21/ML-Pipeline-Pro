# October 18 repository audit evidence

Audit baseline `cb67bb8b3937dbf4dbe7fe6ae2c9247ee37849d0`, Windows, Python
3.11.5 and repository-local uv 0.12.23. The active machine is the Ryzen 7 7800X3D /
RX 9070 workstation. Jacob's October 20 presentation target is the CPU laptop;
these checks do not repair or replace its failed local-model acceptance.

[Audit and priorities](../../project/2026-10-18-repo-audit.md),
[machine-readable results](results.json) and [raw output](raw.zip) retain scope,
commands, outcomes and provenance. The archive excludes credentials, kubeconfigs,
model weights, dependency binaries, package binaries and private MongoDB snapshots.

| Check | Outcome |
| --- | --- |
| Origin fetch / branch comparison | No incoming commits; working branch matches upstream, 35 commits beyond main |
| Locked offline sync / dependencies | 114 resolved, 109 installed packages checked; compatibility passes |
| Ruff lint / format | Pass; 175 files formatted |
| Fast suite | 598 pass, 73 deselected, no selected skips; rounded combined host coverage 80%, 40.31 seconds |
| Rebuilt domain Compose stack | Ten services start; routing and actual training/three-trial tuning/version/monitoring/replay smoke pass |
| Ordinary integration | 63 pass, 608 deselected, no selected skips, 32.71 seconds; both integration flags enabled |
| Serial isolated recovery | Ten pass, 661 deselected, no selected skips, 326.99 seconds; disposable test stack cleaned up |
| Build | Builds succeed, wheel has 44 application modules; source hygiene check fails on one nested public `.env.example` under ignored `.tools/` |
| Source/evidence | All 51 recorded workstation source hashes match; 14 pre-existing ZIP archives pass CRC checks |
| API inventory | All 30 distinct operations match the API reference; 44 application modules |
| Exact baseline remote CI | All five jobs successful in [run 38681567923](https://github.com/JacobHermsmeyer21/ML-Pipeline-Pro/actions/runs/38681567923) |

The isolated Compose project is `mlpp-audit-20261018`, using `compose.yaml`,
`compose.services.yaml`, `compose.monitoring.yaml` and
`tests/integration/compose.validation.yaml`. Tests use API base
`http://127.0.0.1:18000/api/v1`, MongoDB 37017 and Redis 16379. Ordinary pytest
uses `MLPP_RUN_INTEGRATION=1` and `MLPP_RUN_WORKER_INTEGRATION=1`; recovery uses
only its separate `MLPP_RUN_RECOVERY_INTEGRATION=1` flag and a disposable stack.

The first ordinary attempt omitted `/api/v1` from the override: 13 cases fail
with missing-route responses and 50 pass. Both its log/JUnit and the corrected
full run are retained. The tests and assertions are unchanged. Temporary/cache
directories stay within the workspace. PowerShell renders successful native
stderr as `NativeCommandError` in some logs; command exit codes establish results.
The build emits the existing cache-inside-source warning. Inspection finds
`.tools/midterm-clean/.env.example` in the source archive; its bytes equal the
public root `.env.example`. No private `.env`, model weights or cache contents
are present. This is a source-package hygiene finding, not a passing exclusion check.

`laptop-training-timings.json` derives durations from timestamps in the retained
October 14 laptop archive's `walkthrough/backend.json`: five-epoch training takes
0.887 seconds after worker start / 1.641 seconds including queueing; three-trial
tuning takes 1.574 seconds including queueing/final evaluation. Services were
already running. This is historical classifier evidence, not a new laptop run
or a timing claim about Qwen inference.

The smoke's telemetry is explicitly synthetic. No new actual-inference producer,
live-model quality gate, laptop run, local kind deployment, independent review,
security-advisory scan or general performance benchmark is claimed. Current
remote CI covers kind rollout and isolated recovery, but not real-model quality.
The [earlier workstation run](../2026-10-14-rx9070-walkthrough/README.md) and
[laptop failure](../2026-10-14-post-reboot-validation/README.md) remain separate.
