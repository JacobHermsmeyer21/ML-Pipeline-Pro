# OpenAI SDK headers and observer metadata need explicit isolation

October 20, 2026; [approved plan](../plans/2026-10-20-openai-agent-provider-plan.md)
and [retained evidence](../evidence/2026-10-20-openai-provider/README.md).

Locked OpenAI SDK 2.54.0 merges ambient `OPENAI_CUSTOM_HEADERS` over configured
authentication. Separate review reproduced the override through an actual SDK
transport with fixture credentials. Clearing headers also removes HTTP Host/body
framing and the `X-Stainless-Raw-Response` control needed by LangChain 1.7.0;
without the latter, its Responses path receives a parsed object lacking `.parse`.

The [provider adapter](../../src/ml_pipeline_pro/conversation_openai.py) clears SDK
custom headers and rebuilds the final request headers with configured auth,
Host/content length and the required raw-response control. It counts the same
normalized model/input/tool/format fields before sending generation. Construction
and replay stay offline; timestamps belong to each request, not a shared last reply.

Provider usage metadata can also include arbitrary unknown fields. A separate
review probe put a configured secret in a nested unknown usage field and confirmed
that a raw observer would retain it. Observer evidence now allowlists only finite
nonnegative integer input/output/total token counters. The
[SDK regressions](../../tests/test_conversation_openai.py) exercise header isolation,
malformed envelopes, count/send equality, byte/token bounds, overlap, cancellation,
secret-free observation and missing-key replay through application HTTP routes.

The token-counting endpoint has no confirmed separate tariff in the fetched
documentation. Jacob approved estimated reservations under the unchanged $2 test
authorization; the [ledger](../../src/ml_pipeline_pro/openai_test_budget.py) retains
uncertain/completed reservations and stops estimates at $1.90. This is not an
account-wide billing guarantee. Revisit SDK upgrades, new message modalities,
tracing/callback changes and any attempt to rely on the estimates as actual bills.
