# Logistic regression implementation evidence

Jacob approved the [plan](../../plans/2026-10-20-logistic-regression-plan.md) in chat
on October 20, 2026. Approval record `10e9f37` is published on `origin/main`.
Application verification uses that revision plus the implementation
working tree; final source fingerprints and completion commits are recorded below.

## Scope and test justification

The implementation adds immutable logistic model definitions, a strict tagged
config, explicit worker dispatch, linear binary/multiclass training, weight-only
L2, checkpoint reconstruction, dashboard controls and unsupported AI/tuning guards.
Existing MLP configuration serialization and defaults remain unchanged. Ownership,
leases, cancellation, concurrency, resource bounds and dependencies are unchanged.
No course requirement is closed by this baseline algorithm.

New tests cover the plan's F1–F5/N1 boundaries: legacy payload/hash serialization,
same-key replay before reference checks, mismatched admission without dispatch,
host rejection before proposal persistence, stale/direct tool rejection, worker
algorithm checks, binary/multiclass metrics independently calculated with
scikit-learn, selected in-memory versus reloaded predictions, training-only scaling,
test-label isolation, exact L2 gradients including unpenalized bias, malformed
checkpoint tags/dimensions, artifact downloads and registration. The ordinary
queued-worker test is parameterized for both algorithms with its existing success,
isolation, replay and artifact assertions preserved. New recovery cases kill the
logistic worker and hold a logistic minibatch past its runtime budget.

Three existing action/transport test fixtures now answer the required model GET
before their original mutation boundary. Their POST count/key, malformed response,
storage-loss and optional-refresh assertions are preserved. No assertions were
weakened, gates lowered or skips added.

Initial targeted runs found a duplicate model preflight read and two fixtures
that did not support model reads; both were corrected. The first synthetic binary
fixture added a holdout offset to a constant feature, which training-only scaling
amplified by its `1e-6` floor. Varying that feature within every split produces the
intended separable fixture; the accuracy threshold remains unchanged. The first
browser script forgot to reopen collapsed settings after its deliberate reload;
the corrected walkthrough passes without an application change.

## Automated verification

Final retained results and provenance are populated after the fresh-image gates.
Local raw logs/JUnit are under `artifacts/logistic-validation/` and
`artifacts/logistic-*.log`; selected portable evidence is retained here.

Implementation checkpoint: locked sync, Ruff lint/format and dependency checks
pass; 822 fast cases pass with coverage (118 integration cases deselected,
zero selected skips). `uv build` succeeds and the wheel contains the new selector
and classifier. Ordinary integration passes 106 cases on the first implementation
image. The initial browser walkthrough passes three runs, comparison, registration
and immutable retry/reload. Fresh-image reruns remain necessary because explicit
checkpoint feature-count metadata and final guard wording were added after that
first image was built. The fresh build is downloading unchanged locked dependencies;
its twelve-case serial recovery gate is pending. These initial results do not
substitute for final-source service acceptance.

## Review and remaining limits

Implementing assistant self-review covers legacy serialization, architecture
dispatch, checkpoint loading, artifact publication, unsupported-action guards and
the final diff. This is not independent review. No concurrency, state machine or
rate/size arithmetic was changed; independent review is unavailable in this
session. Human usefulness review of the completed selector/comparison flow remains
open. No live AI understanding or generated-logistic-snippet acceptance is claimed.
Only fixed separable synthetic data and existing regression fixtures are tested;
no algorithm superiority or convergence/generalization claim follows.
