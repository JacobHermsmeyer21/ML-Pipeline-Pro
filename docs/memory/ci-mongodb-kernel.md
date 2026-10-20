# Hosted runner kernels can prevent MongoDB startup

October 19, 2026, baseline `96c652c`: the
[retained Actions diagnosis](../evidence/2026-10-19-ci-mongodb-kernel/README.md)
confirms `compose-smoke` fails before application tests because MongoDB explicitly
refuses its host kernel. The failing Ubuntu 24.04 runner image is
`20261018.339.1`; a passing domain job in the same run uses `20261012.334.1`.
Do not infer an application regression or a universal success from another job
during a hosted-image rollout.

Containers share the host kernel; an Ubuntu user-space image or unchanged
`mongo:8.0` tag does not establish compatible kernel behavior. MongoDB's
[Ubuntu detection issue](https://jira.mongodb.org/browse/SERVER-136848) affects
8.0.32. Check the actual failure and published/runtime kernel before upgrading
images, changing timeouts, or weakening gates.

Jacob approved the [plan](../plans/2026-10-19-ci-mongodb-kernel-plan.md) on October 19.
It pins `ubuntu-22.04` for all three MongoDB-dependent CI jobs and adds explicit
kernel logging. Fix `e300412` was pushed; [its run](https://github.com/JacobHermsmeyer21/ML-Pipeline-Pro/actions/runs/39362498397)
passes Compose startup, 104 ordinary and ten serial recovery tests on measured
kernel `6.8.0-1064-azure`. Domain smoke and 104 integration tests pass on
`6.8.0-1070-azure`. A later Kubernetes dataset POST returns storage 503 after
rollout/readiness; the underlying exception is unavailable. The evidence-only
[follow-up run](https://github.com/JacobHermsmeyer21/ML-Pipeline-Pro/actions/runs/39363463858)
repeats all those Compose/domain passes and the Kubernetes first-dataset 503.
Full five-job acceptance and attribution of that later failure remain open.
Warm-server and newly started local MongoDB admission probes pass without
reproducing it. Keep that failure separate from the confirmed kernel rejection;
another retry alone does not diagnose or repair the storage boundary.

Later October 19, [isolated startup diagnosis](mongodb-preinit-sessions.md)
identifies that storage failure as a direct connection opened before replica-set
initialization retaining unsupported-session handshake state. The new finding
supersedes the unavailable-attribution status above; its separate configuration
repair still requires review and hosted acceptance.

Revisit when MongoDB/kernel compatibility is demonstrated on a newer supported
runner, and before Ubuntu 22.04's April 2027 runner retirement. The healthy local
WSL kernel is a separate environment.
