# Generated snippets need exact API shape and independent acceptance

Recorded October 10, 2026 during approved A2 implementation. Scope: four Python
integration profiles, local LangChain/Ollama inference, and saved drafts.

[The A2 outcome](../plans/2026-10-08-person-a-snippet-generation-plan.md#implementation-outcome)
links retained runs and limits. Generation uses one additional call within the
original turn budget; it bypasses domain dispatch and never executes Python.
The host checks a closed AST grammar, configured environment placeholders and
exact canonical method/path/query/body. Accepted output still requires review.
Known secrets cause rejection instead of accepted rewritten Python.

The initial seven-case evaluation failed all scenarios. A separate diagnostic
retained Python with `with` after a semicolon, which is invalid syntax, and a
submission header on GET. The initial instructions described imports with
semicolons and only described the client block inline. Actual SDK requests also
show that an untyped `inputs` object supplies no nested config/limit guidance.
Multiline format examples plus typed schemas in the SDK-retained `$defs` and an
explicit nested-input description were added within the approved design. The
combined changes passed five scenarios; they do not isolate one change's effect.

The next run supplied a POST/JSON comparison instead of the required GET/query
shape. Missing parent objects produced broad `inputs.config`/`inputs.limits`
locations. Explicit GET comparison guidance and expansion of missing parent
objects to their required leaf paths produced six of seven passes. The remaining
training draft omitted `Idempotency-Key` and was correctly rejected. Training
passed in the previous run; these observations do not establish reliability.
No validation assertion, scenario or budget was weakened, and no output was
repaired or executed. A2/C7 acceptance remains open.

The first evaluation retained turns and usage, but omitted rejected raw code;
the separate diagnostic and later evaluations retain redacted model steps for
failure inspection. Record that evidence limitation rather than infer missing
outputs. Keep the A2 suite separate from the still-failing original A1 gate.
Revisit after reviewed model/runtime/protocol changes; independent review,
human usefulness review and clean-checkout onboarding remain outstanding.
