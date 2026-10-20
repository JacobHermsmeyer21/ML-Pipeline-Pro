# Explicit source exclusions remove an ignored nested example

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

The original audit left packaging hygiene unresolved; the October 19 correction
below removes the observed nested file with explicit exclusions. The earlier
ignore-layer cause remains unconfirmed. No packaging behavior changed in that
audit. [Evidence](../evidence/2026-10-18-repo-audit/README.md) retains the
package hashes and unexpected path, without packaging binaries or private files.


October 19 dashboard build reproduced the ignored nested example. Explicit
sdist descendant exclusions (`/.tools/**`, plus workspace cache/artifact paths)
remove it in this same existing workspace. Directory-only patterns (`/.tools`)
did not remove the descendant. The corrected archive still contains the public
root `.env.example` and all seven dashboard assets; wheel assets match source
bytes. Keep inspecting actual distributions after packaging changes. This fixes
selection for the observed path without claiming the earlier ignore-layer cause
was established. See the [dashboard evidence](../evidence/2026-10-19-dashboard/README.md).
