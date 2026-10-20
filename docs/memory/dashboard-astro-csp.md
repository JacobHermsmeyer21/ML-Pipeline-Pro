# Astro islands need hashed inline code under the dashboard CSP

- Date: 2026-10-19; plan: [dashboard redesign](../plans/2026-10-19-dashboard-redesign-plan.md)

The dashboard is built by Astro from `frontend/dashboard/` into the committed
package directory. Astro inlines its island loader (two `<script>` blocks and one
`<style>` block in the October 19 build), which the strict `script-src 'self'`
policy would block. `scripts/postbuild.mjs` writes `csp-hashes.json`, and
`dashboard_api.DashboardFiles` adds exactly those hashes to the header.

Rejected: Astro's `security.csp`. It emits a `<meta>` policy that does not list
external scripts by default. That policy is enforced alongside the header, so it
can block the bundled modules.

Constraints that are easy to rediscover:

- Inline `style="…"` attributes would need `'unsafe-hashes'`. The build rejects them,
  and runtime `element.style` writes (DepthCard tilt) are allowed.
- `agent.js` clones the chat welcome block, so no island may live inside it.
- Islands wrap Astro slot HTML only and never render behavior-owned IDs.
- A closed `<dialog>` stays hidden only if CSS sets `display` on `dialog[open]`, not on
  the ID.
- `ruff format --check` also formats Python code blocks inside Markdown plans.
