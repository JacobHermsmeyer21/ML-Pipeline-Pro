# Chat experiment-to-model reference correction

October 20, 2026; source baseline `729f0e7`. Jacob explicitly waived the written
plan in chat: "dont bother with the plan". The draft was discarded; no plan was
committed or pushed. This record describes implementation and measured checks.

## Failure and correction

Live conversation `c27`, revision 3, correlation
`ded7427efe68520da9c2e468606fc8e1`, failed after requesting `/api/v1/models/e8`.
The user referred to the model from experiment `e8`, but the proposed action used
the experiment alias as its model ID. Read-only logs and MongoDB public turns
confirmed `model_not_found`. Experiment `e8` had succeeded independently.

The chat host now resolves an experiment alias in a model-reference position
through scoped `get_experiment`, uses its saved `model_id`, and then performs the
existing model read and architecture checks. This covers direct `get_model`
calls and both training/tuning proposal paths. Saved proposals use canonical
model IDs; original chat requests and model steps are not modified. Extra reads
consume the existing host limits and retain current-turn evidence. Public model
API semantics, exact-action decisions and historical records are unchanged.

Model instructions explain the reference distinction and the continuing logistic
proposal limitation. Logistic requests now reach `unsupported_model_algorithm`
rather than failing model lookup. This does not implement logistic tuning or fix
the separate earlier unknown-citation failure.

## Verification

Windows, Python 3.11.5, repository-local uv 0.12.23 and locked training environment:

- Locked sync, Ruff lint/format and installed dependency compatibility pass.
- **855 fast tests pass**, 134 integration cases deselected, 79% coverage.
- **40 affected real-service integration tests pass**, no selected skips, with
  both `MLPP_RUN_INTEGRATION=1` and `MLPP_RUN_WORKER_INTEGRATION=1`.
- Six new integration cases exercise direct reads and both proposal types against
  real scoped HTTP records and transactional conversation storage, for MLP and
  logistic models. Saved turns replay after store restart without new reads.
- New host regressions cover canonical saved actions, unchanged runtime/trial
  limits, immutable model output, missing/foreign/mismatched experiment records,
  tool-budget exhaustion, successful evidence and replay. Existing canonical model
  input tests remain unchanged.

The first focused run passed 129 cases and failed one new assertion because its
expected limits omitted the existing `concurrency: 1` default. The assertion now
checks the complete expected limits including that default. The first integration
run passed 37 cases and failed three new logistic fixtures because they omitted
the required explicit algorithm; corrected the fixtures to honor that contract.
Neither correction changes application requirements or existing assertions.

Raw final fast/integration logs and JUnit XML are retained in [checks.zip](checks.zip),
with local originals under `artifacts/experiment-model-reference/`. Commands:
`uv run --locked --extra training pytest -m "not integration" --cov` and
`uv run --locked --extra training pytest tests/integration/test_conversation_service.py tests/integration/test_conversation_store.py tests/integration/test_conversation_actions.py -q`.
No worker/ownership/recovery mechanism changed; the destructive recovery suite was
not rerun. Verification used scripted inference; no paid inference call was made
and fresh real-model reliability is unmeasured. Review of this change was
self-review, not independent review.

## Local delivery

Built the existing Compose model API image and recreated only `model-api` in
`mlpp-rx9070-walkthrough-20261014` with its original five Compose files and existing
volumes. Docker reports healthy and the gateway readiness endpoint returns 200.
Read-only delivery checks confirm `e8` still succeeds and references model
`f9b5efe3-dc7b-4e8c-b5b0-07221fad1212`.

Deployed installed module hashes match tested source:

| Module | SHA-256 |
| --- | --- |
| conversation_service.py | bb2cd3646bb3569232df1f6c087fcdefc672c61af7b274c5dbd6a0cb4ea08e13 |
| conversation_model.py | c1a572cc49b27d88cc7e63bab46538b099379662276261e2276dd66dfa173fd7 |

Historical failed turns are retained; submit a fresh request to use the correction.
