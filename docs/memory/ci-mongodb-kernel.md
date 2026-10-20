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

The [plan](../plans/2026-10-19-ci-mongodb-kernel-plan.md) proposes `ubuntu-22.04`
for MongoDB-dependent CI jobs and explicit kernel logging; approval and fresh
hosted acceptance are pending. Revisit when MongoDB/kernel compatibility is
demonstrated on a newer supported runner, and before Ubuntu 22.04's April 2027
runner retirement. The healthy local WSL kernel is a separate environment.
