# Hosted CI MongoDB startup diagnosis

Date: October 19, 2026, America/New_York; raw CI timestamps below use UTC on
October 20. Source: `96c652c4a28845351912bd802d811e0b17861166`.

The [failed run](https://github.com/JacobHermsmeyer21/ML-Pipeline-Pro/actions/runs/39360388047)
passes both Python check jobs, domain Compose smoke and Kubernetes deployment.
Only [compatibility Compose smoke](https://github.com/JacobHermsmeyer21/ML-Pipeline-Pro/actions/runs/39360388047/job/118424959581)
fails, in `docker compose ... up --build --wait --wait-timeout 300`. Readiness,
ordinary integration and recovery steps are skipped because startup fails; they
are not passing checks for that job.

[Raw diagnostic excerpts](runner-and-startup.txt) preserve the runner-image identity,
service exit and MongoDB diagnostic. The failing image is Ubuntu 24.04
`20261018.339.1`; its [published software manifest](https://github.com/actions/runner-images/blob/ubuntu24/20261018.339/images/ubuntu/Ubuntu2404-Readme.md)
reports kernel `7.0.0-1017-azure`. The
[passing domain job](https://github.com/JacobHermsmeyer21/ML-Pipeline-Pro/actions/runs/39360388047/job/118425437272)
uses Ubuntu 24.04 `20261012.334.1`. The failed job does not print `uname -r`, so
the exact runtime kernel is inferred from the manifest, not directly measured.

MongoDB explicitly refuses startup for the kernel incompatibility tracked by
[SERVER-121912](https://jira.mongodb.org/browse/SERVER-121912).
[SERVER-136848](https://jira.mongodb.org/browse/SERVER-136848) separately records
8.0.32 rejecting Ubuntu's `7.0.0` release strings despite backported upstream fixes.
These sources support selecting a known compatible host rather than assuming an
arbitrary newer MongoDB tag fixes the condition.

The local comparison, obtained read-only with Docker 29.8.2 / Compose 5.5.1,
reports kernel `6.18.54.1-microsoft-standard-WSL2` and healthy MongoDB 8.0.32.
The local `mongo:8.0` digest is
`sha256:d0d926f94df099bff534b7ee5b5986458131a22489dfff8664509af0c1e2ca9c`.
This establishes local availability only, not hosted-runner acceptance.

Full downloaded logs and Actions job metadata are retained locally under ignored
`artifacts/ci-compose-diagnosis/`; the remote job links and tracked excerpts above
provide the retained diagnosis. GitHub access was read-only and explicitly
authorized by Jacob; no credentials or signed storage URLs were saved.

Jacob approved the [repair plan](../../plans/2026-10-19-ci-mongodb-kernel-plan.md)
on October 19. The three MongoDB-dependent jobs now select `ubuntu-22.04` and
print their kernel before startup. The diagnostic failure above remains retained.

Post-approval local checks pass on Windows/Python 3.11.5 with uv 0.12.23:
locked dependency sync, Ruff lint/format (264 files), 740 fast tests in 94.71
seconds (114 integration cases deselected, no selected skips), installed dependency
compatibility (116 packages), both CI Compose configurations, exact parsed workflow
scope comparison and 51 local documentation links/anchors. Raw local JUnit is
`artifacts/ci-compose-diagnosis/approved-unit.xml`; configuration comparison is
`implementation-config-checks.json` in that directory. No test assertions changed.

## Implementation run

Fix `e3004122ad11c23ba162e6e4b347551cd616829c` was successfully pushed to
`origin/main`. [Its CI run](https://github.com/JacobHermsmeyer21/ML-Pipeline-Pro/actions/runs/39362498397)
verifies the original Compose failure boundary. [Structured results](implementation-run.json)
and [raw excerpts](implementation-run.txt) retain the measured kernels and test
summaries; downloaded JUnit XML hashes identify the reports inspected locally.

| Job | Result | Runtime kernel / acceptance |
| --- | --- | --- |
| `compose-smoke` | Passed | `6.8.0-1064-azure`; healthy MongoDB, readiness, 104 ordinary integration and ten serial recovery tests |
| `checks (3.11)` | Passed | 740 fast tests and existing lint/format/dependency/audit gates |
| `checks (3.13)` | Passed | 740 fast tests and existing lint/format/dependency gates |
| `domain-compose-smoke` | Passed | `6.8.0-1070-azure`; routes, actual three-domain workflow and 104 integration tests |
| `kubernetes-deploy` | Failed after startup | `6.8.0-1064-azure`; rollout/readiness passed, first dataset POST returned storage 503 |

All five available JUnit reports have zero failures, errors or selected-case skips.
The recovery run takes 347.92 seconds; this is an execution observation, not a
performance comparison. The kernel log proves compatibility at the original
startup boundary. Full five-job CI acceptance remains open because of the later
Kubernetes smoke failure.

The [Kubernetes failure](https://github.com/JacobHermsmeyer21/ML-Pipeline-Pro/actions/runs/39362498397/job/118432214805)
has all eleven pods running/ready with zero restarts. Model API logs record a
36.73 ms dataset POST returning 503 with `Storage operation failed`; MongoDB logs
show creation of `project_lifecycle`, but the underlying exception is not logged.
Five sequential, uniquely named disposable databases on the local validation MongoDB
pass first dataset admission and are then removed. Their raw result is
`artifacts/ci-compose-diagnosis/fresh-database-probe.json`. These probes do not
reproduce the Kubernetes cause. No application fix, added retry or relaxed gate
is justified by this evidence. A clean CI run after this evidence-only commit
will check recurrence, retaining the failed run regardless of its outcome.
