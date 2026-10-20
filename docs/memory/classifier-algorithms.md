# Algorithm variants must preserve historical MLP serialization

October 20, 2026: the approved [logistic regression plan](../plans/2026-10-20-logistic-regression-plan.md)
adds a required `algorithm: logistic_regression` config variant while leaving
`TrainingConfig` unchanged. Adding a default algorithm field to MLP configs would
change canonical submission hashes and break old-key replay. This is a compatibility
constraint, not a measured historical production incident.

Model architecture is immutable. Experiment admission checks the config variant
after existing same-key replay, and execution passes the saved model architecture
to training for another check. Logistic tuning and AI mutation proposals remain
unsupported; the host rejects new proposals and the tool dispatcher rechecks stale
actions. Read/list/compare tools accept both config variants.

Missing algorithm in checkpoints means historical MLP. Logistic checkpoints use
format version 1, explicit dimensions and a linear state; reconstruction verifies
config, dimensions, scaling and finite weights after artifact hash/size validation.
The shared training loop applies L2 to linear weights only and selects by validation.

Evidence: [compatibility/training tests](../../tests/test_logistic_regression.py),
[worker recovery cases](../../tests/integration/test_recovery.py) and the
[execution record](../evidence/2026-10-20-logistic-regression/README.md).
Revisit before adding algorithm tags to old configs, enabling logistic AI/tuning,
or changing the checkpoint format. Test old serialized payloads and replay first.
