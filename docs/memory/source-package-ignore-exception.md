# Source packaging includes a nested example that Git ignores

October 18 audit of `cb67bb8`: `uv build --offline` succeeds, but archive inspection
finds `.tools/midterm-clean/.env.example` in the source distribution. It is identical
to the public root `.env.example`; no private `.env`, weights or cache contents
were found. The wheel contains the expected 44 canonical application modules.

`git check-ignore -v --no-index .tools/midterm-clean/.env.example` reports the
`.tools/` exclusion. Why Hatch's source selection nevertheless includes this
example is unresolved; the global `!.env.example` exception is a hypothesis, not
a diagnosed cause. A clean checkout without the ignored nested file cannot
reproduce its inclusion. The cache-inside-source warning alone does not prove
exclusion; inspect actual paths when building from an existing workspace.

Retain this as an unresolved packaging-hygiene finding. Evaluate explicit source
build exclusions or a root-scoped example exception before distributing an sdist;
inspect actual archive paths after any correction. No packaging behavior changed
in the audit. [Evidence](../evidence/2026-10-18-repo-audit/README.md) retains the
package hashes and unexpected path, without packaging binaries or private files.
