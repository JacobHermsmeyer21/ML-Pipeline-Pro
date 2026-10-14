# Requested inspection fact boundary verification

Jacob approved the [correction plan](../../plans/2026-10-13-requested-inspection-facts-plan.md)
on October 14, 2026. This record covers scripted checks of the narrow guided
requested-reference guard. It does not close live-model/demo acceptance.

[Source/package provenance and service probes](results.json) identify the baseline
and exact application/test/lockfile hashes. [Raw checks](raw.zip) retain the initial
failed full run, final full run, JUnit, lint/format/dependency output and evidence
collection script. Python 3.11.17 and the unchanged lockfile were installed into a
fresh workspace environment with a workspace-local uv cache.

Commands: `uv sync --locked --extra training`,
`uv run --locked --extra training ruff check .`,
`uv run --locked --extra training ruff format --check .`,
`uv run --locked --extra training pytest -m "not integration" --cov`,
`uv pip check`, and `uv build`. Documentation verification checks local
links/anchors, walkthrough Python syntax and `git diff --check`. Distribution
inspection rejects workspace caches/private artifacts; the cache-inside-source
build warning does not mean those files were packaged.

Focused guidance checks pass 65 cases. The first full run passed 592 cases and
failed the new host omission test because its fixture used the reserved placeholder
ID `experiment`; the focused rerun then exposed dictionary-style saved error
access. The corrected test uses `run-selected` and asserts the same failure code,
no facts, no mutation and identical replay without another inference. Existing
assertions and ten/seven evaluation scenarios/budgets are unchanged.

Final full suite: **593 passed, 73 integration cases deselected**, 80% reported
coverage, 284.39 seconds. Lint, formatting (168 Python files), dependency
compatibility and package build pass. Deselected integration cases are not passes.

Unavailable acceptance: no Docker CLI, API, MongoDB, Redis or Ollama is available
on this checkout; the original saved failed demo is also absent. The nine affected
real-service cases, rebuilt-image inspection against that record, fresh full
walkthrough and original ten/seven local-model gates were not run. Separate boundary
review is unavailable; implementing-assistant inspection is self-review. Historical
October 13 passes do not verify this change. No model weights were downloaded,
generated Python executed, or original failed demo rewritten.

Subsequent authorized [prerequisite installation and live attempts](../2026-10-14-prerequisite-setup/README.md)
supersede the missing-software state above: all implementation CI jobs now pass,
including 63 real-service cases without skips. The pinned 7B laptop gates fail
(2/10 dialogue, 0/7 snippets), and Windows restart is required for local containers.
This follow-up does not convert the failed model gates into acceptance.
