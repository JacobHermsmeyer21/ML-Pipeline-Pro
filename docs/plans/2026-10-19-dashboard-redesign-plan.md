# Dashboard visual redesign with Astro and React islands

- Status: approved; implementation in progress
- Date: 2026-10-19
- Source baseline: `8746d81` on `main`
- Request: make the dashboard look professional, neat and responsive rather than
  "AI-made", with 3D depth, using a modern framework such as React or Astro
- Human decisions (October 19, in chat): Astro with React islands; subtle depth
  rather than heavy 3D; a bright (light) theme
- Human reviewer/approval: repository owner (lama9811), October 19, in chat ("approved, go ahead"); scope below
- Independent review: different-vendor reviewer unavailable; planned same-vendor
  subagent review of the CSP/build changes, disclosed as such

## Proposed behavior and purpose

`http://127.0.0.1:8000/dashboard/` keeps every current workflow (connection,
upload/preview/prepare, column editing, model create/manage, review-then-train,
experiment detail and downloads, tuning, monitoring/Grafana, agent chat with
explicit approvals, permanent deletion, refresh recovery) but gets a new visual
system: a bright, restrained, product-grade interface with subtle physical depth,
built from Astro components with React islands. The user should be unable to tell
it was generated: no sparkle motifs, glow, slogan copy or uniform card stamping.

## Clarification and critique

Decided by the user: Astro + React islands; subtle depth; bright theme only.

Facts from source: the dashboard is static files served by
[`dashboard_api.py`](../../src/ml_pipeline_pro/dashboard_api.py) under a CSP of
`script-src 'self'; style-src 'self'` with no `unsafe-inline`. The behavior layer
is ~1,040 dense lines across seven ES modules that implement idempotent submission
keys, `sessionStorage` recovery of pending training/chat/deletion, stale-request
generation fencing and project scoping. The Docker image, `uv build` and CI have
no Node toolchain. [`tests/test_dashboard.py`](../../tests/test_dashboard.py)
asserts the CSP, `app.js`/`styles.css` and the packaged example CSV.

Case against: the "AI-made" look comes from styling and copy (sparkle icons, teal
glow on near-black, marketing headlines, all-caps kickers, identical cards), not
from the framework. A framework adds a Node build, a second lockfile and an inline
hydration script that collides with the CSP. A full React port of the behavior
layer risks regressions in idempotency, recovery and deletion safety that this
machine cannot verify end to end (no Docker/MongoDB/Redis installed).

Why the chosen approach survives: the user chose Astro + React. To contain risk,
**phase 1 (this plan)** uses Astro components for all markup and layout and React
islands for the presentational/interactive surfaces that benefit from them, while
the proven behavior modules are kept, typed lightly where touched, and bundled by
Astro's Vite pipeline unchanged in logic. A full port of the behavior layer to
React state is **phase 2, out of scope**, and needs its own plan.

Questions still requiring the user: none blocking. Defaults chosen by the
implementer are marked "(implementer's call)" below and can be overridden at review.

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | All existing workflows and element behaviors still work; no API route, payload, header or idempotency behavior changes. | Playwright suite against mocked `/api/v1` covering each workflow; diff shows no change to request construction in behavior modules; full-stack walkthrough when Docker is available. |
| F2 | Functional | New light visual system: neutral palette, one restrained accent, real typographic hierarchy, plain product copy, no sparkle/glow motifs. | Screenshots at 1440, 1024, 768 and 390 px reviewed by the user. |
| F3 | Functional | Subtle depth: layered elevation tokens, hover lift, gentle pointer tilt on stat cards, disabled under `prefers-reduced-motion`. | Screenshot/hover check; reduced-motion emulation shows no transforms. |
| N1 | Non-functional | Responsive with no horizontal page scroll from 360 px up; sidebar collapses to a top/drawer nav under 900 px; tables scroll inside their panel. | Playwright viewport checks assert `scrollWidth <= innerWidth`. |
| N2 | Non-functional | CSP stays free of `unsafe-inline`/`unsafe-eval`; any inline script Astro emits is allowed only by its build-time SHA-256 hash. | Updated `test_dashboard.py`; browser console shows zero CSP violations. |
| N3 | Non-functional | Python packaging, Docker and existing CI keep working without Node at runtime/image build. | `uv build` wheel contains the built dashboard; `docker compose ... config` unchanged. |
| N4 | Non-functional | Frontend dependencies are locked and the committed build matches the source. | `npm ci && npm run build` then `git diff --exit-code` on the output directory, in CI. |
| N5 | Non-functional | Accessibility does not regress: landmarks, labels, skip link, focus rings, dialog focus, AA contrast. | axe-core run in Playwright with no serious/critical violations. |

## Constraints and scope

Unchanged: `/api/v1` schemas and headers, `X-Project-ID`/`X-API-Key` handling,
idempotency keys, `sessionStorage` key names (`mlpp:<project>:*`), stale-generation
fencing, Grafana origin `http://127.0.0.1:3000`, `/dashboard/config.json`, the
dashboard being mounted only on the model service, and the packaged
`example.csv` fixture. No backend behavior change beyond serving the new build
and extending the CSP with hashes. Dark mode, new features, and a full React port
of the behavior layer are excluded.

## Design

**Layout.** New source project at `frontend/dashboard/` (implementer's call):
Astro 7, `@astrojs/react`, React 19, TypeScript, `package-lock.json` committed.
`astro build` writes to `src/ml_pipeline_pro/dashboard/` with `build.format:
"file"`, `inlineStylesheets: "never"`, `assetsInlineLimit: 0`, and `base:
"/dashboard/"`. The built output is committed so Docker, `uv build` and the
Python tests need no Node (implementer's call; the alternative multi-stage Docker
build was rejected because it adds Node to CI image builds and host development).
Astro empties `outDir` on each build, so `example.csv` moves to
`frontend/dashboard/public/` and is copied into the output; the existing test keeps
asserting that the packaged copy equals `examples/data/classification.csv`. Node is
pinned (`.nvmrc` and `engines`, Node 24) so the CI diff-check compares like with like.
The wheel's file list is inspected to confirm `_astro/` assets are packaged and not
excluded by new `.gitignore` rules.

**Markup.** `index.astro` composes Astro components: `Sidebar`, `Topbar`,
`StatsGrid`, `LaunchPanel`, `RunsPanel`, `DatasetsView`, `MonitoringView`,
`AgentPanel`, and one component per `<dialog>`. Every element ID the behavior
modules use is preserved, so the modules bind exactly as today.

**React islands** (`client:visible`): `DepthCard` wraps the stat tiles and adds
pointer tilt; `EmptyState` renders the empty-state illustrations. Islands never
call the API and never render or re-render a node the behavior modules own. Owned
IDs such as `stat-datasets` stay in Astro-rendered slot HTML, which hydration
passes through as static markup. The behavior modules remain the single owner of
requests, state and every ID they write. Icons become a plain Astro SVG sprite
with the sparkle motif removed.

**Behavior modules.** The seven `.js` files move to `frontend/dashboard/src/lib/`
and are imported by a single `<script>` in `index.astro`, which Astro bundles to an
external hashed file. Logic edits are limited to class names/markup strings that
the redesign renames; each such edit is listed in the implementation outcome.

**Visual system.** CSS custom properties in `tokens.css`: neutral slate scale on
an off-white `#f7f8fa` canvas, white surfaces, one indigo accent (implementer's
call), semantic success/warning/danger; 4 px spacing scale; radii 8/12; three
elevation levels built from layered low-opacity shadows plus a 1 px hairline.
Typeface: Inter Variable self-hosted via `@fontsource-variable/inter`
(implementer's call; `font-src 'self'` forbids a CDN). Copy is rewritten to plain
product language (for example "Overview" and "Start an experiment"). The
"Pipeline agent" heading stays because `test_dashboard.py` checks it and it is
already plain wording.

**CSP.** Astro's island loader is emitted inline. The response header policy is
enforced alongside any `<meta>` policy, so the header itself must allow those blocks.
Astro's built-in `security.csp` is used to compute hashes if the pinned version
supports it; otherwise a post-build script does. Either way the build writes
`csp-hashes.json` (SHA-256 of every inline `<script>`/`<style>` block), and
`DashboardFiles` reads it at startup and appends the `'sha256-…'` tokens to
`script-src`/`style-src`. Inline `style="…"` attributes are not allowed in built
HTML (they would need `'unsafe-hashes'`); runtime `element.style` writes are
unaffected. A test asserts the built HTML has no `style=` attribute. If an inline
block is unhashed, the browser blocks it and the Playwright CSP check catches it.

**Coupled updates.** `tests/test_dashboard.py`: replace the fixed `app.js`/
`styles.css` assertion with "every asset referenced by `index.html` returns 200",
because Astro emits hashed filenames; the CSP and fixture assertions stay.
CI: add a `dashboard-build` job (Node 24 plus Python/uv, because Playwright serves
the page through FastAPI; `npm ci`, `astro check`, build, diff-check, Playwright).
Docs: `docs/guides/dashboard.md` and the README gain a "Develop the dashboard"
section, and current-state references to `app.js`/`styles.css` are updated.
Historical evidence files are left unchanged. `.gitignore`: `node_modules/`, Playwright output.

## Acceptance and verification

Fast gates: the four `uv` commands from `AGENTS.md`, `uv build`, plus
`npm ci`, `npm run check`, `npm run build`, `git diff --exit-code
src/ml_pipeline_pro/dashboard`, and `npx playwright test`.

Playwright suite (new, under `frontend/dashboard/tests/`) runs the real built page
served by the FastAPI app with `/api/v1` routes mocked from recorded response
shapes. It covers connection, upload/preview/prepare, column edit, model
create/delete preview, review-then-train (asserting one POST with an
`Idempotency-Key`), refresh recovery of a pending training request, chat send and
action approve/reject, monitoring empty state, viewport overflow at 360/390/768/
1024/1440 px, reduced motion, axe and zero console CSP errors.

Known gap: this machine has no Docker, MongoDB or Redis, so the real-service
browser walkthrough and ordinary integration gates cannot run here; they are
recorded as gaps until run on a machine with Docker or in CI.

## Risks and rollback

Risks: renamed classes break a behavior-module selector (mitigated by preserved
IDs and Playwright coverage); CSP hash drift (mitigated by build-generated
hashes and a test); committed build drifting from source (CI diff-check); larger
JS payload from React (islands only, measured in the build report). Rollback:
revert the commit; no stored records, artifacts or API contracts are affected.

## Human review and approval

- October 19: the repository owner approved this plan in chat ("approved, go ahead").
- Later the same session, the owner said the dashboard will be deployed on Vercel
  (dashboard only on Vercel, not at FastAPI `/dashboard/`), with the Claude API for
  chat. They then asked for "first do the ui changes". Approved scope for this plan
  is therefore the visual redesign as written. The build stays packaged with
  FastAPI so the local/Docker demo keeps working. The Vercel deployment, the
  configurable API origin/CORS, removing the FastAPI-served dashboard, hosting the
  backend, and switching chat to the Claude API are deferred to a separate
  deployment plan that needs its own review. Claude chat also conflicts with the
  course's local-model target and must be reconciled in that plan.

## Implementation outcome

- Source revision and changed scope: branch `dashboard-redesign`, commits `3c343db`
  through `b944cb7` on base `8de4a93`. The changes cover the Astro project in
  `frontend/dashboard/`, the committed build in `src/ml_pipeline_pro/dashboard/`,
  CSP hashes in `dashboard_api.py`, `tests/test_dashboard.py`, the CI
  `dashboard-build` job, the dashboard guide, the README and a memory note.
  Task list: [implementation plan](2026-10-19-dashboard-redesign-implementation-plan.md).
- Environment and tools: macOS (Darwin 25.5), Node 24.14.1, Python 3.11.15, Astro
  7.4.1, `@astrojs/react` 7.1.0, React 19.3.1, TypeScript 6.0.3, Playwright 1.64.1
  (Chromium headless shell 156), `@axe-core/playwright` 4.14.0 and IBM Plex 5.3.0.
- Results:
  - Fast gates: `ruff check` and `ruff format --check` pass. `pytest -m "not
    integration" --cov` gives 743 passed and 114 deselected, with 79% total
    coverage. `uv pip check` passes.
  - `npm run check` reports 0 errors, and `npm run test:e2e` gives 26 passed.
  - A fresh `npm ci && npm run build` reproduced the committed output. The `uv
    build` wheel lists `index.html`, `_astro/*`, `csp-hashes.json` and `example.csv`.
- Acceptance mapping:
  - F1 is covered by `workflows.spec.ts`. It checks connection headers, a single
    training POST with an `Idempotency-Key`, refresh recovery, preview/prepare,
    column save, deletion preview before `DELETE`, one chat decision per choice,
    and the monitoring empty state.
  - F2/N1/N5 are covered by `layout.spec.ts`. It runs at five widths and covers
    the Review Focus cases, banned copy, axe (no serious or critical findings),
    hidden closed dialogs, truncation titles and drawer focus.
  - F3/N2 are covered by `depth.spec.ts` (tilt, reduced motion, hydration keeps
    owned values, no CSP console messages) and by the pytest hash and header checks.
  - N3/N4 are covered by the wheel listing and the reproducible-build diff.
- Not verified: the real-service browser walkthrough and the ordinary and recovery
  integration gates. This machine has no Docker, MongoDB or Redis. The new CI job
  and the existing Compose jobs run them after the push.
- Raw evidence: local runs only. The screenshots are under
  `frontend/dashboard/test-results/screens/` (gitignored, not retained).
- Test changes and justification:
  - The fixed `app.js`/`styles.css` asset check now checks that every asset
    `index.html` references is served, because Astro emits hashed names.
  - New tests were added for the inline-code hashes, the header hashes and no
    `style=` attributes. No assertion was weakened.
- Review: a same-vendor subagent review (Claude, a fresh context, not
  independent) of `8de4a93..1941157` found no critical issues.
  - Important, fixed in `b944cb7`: truncated names had no title; drawer focus
    dropped after a choice (re-graded up from minor). Both were fixed RED to GREEN
    with new Playwright tests.
  - Deferred minors: no stricter focus trap beyond `inert`; weaker 100-row and
    correlation-ID assertions; the inline-code regex is duplicated in pytest; the
    static "Project: demo" text flashes before the JS runs; the CI diff misses
    untracked build files; Playwright reuses a local server on port 8123.
- Deviations: the rulings are listed in the implementation plan ledger summary
  below. The main ones:
  - IBM Plex and an oxide-green accent replace Inter and indigo.
  - One readout strip replaces four stat cards.
  - Astro's `security.csp` is not used.
  - `EmptyState` renders server-only.
  - Darker muted text meets AA contrast.
  All of these sit within items the plan marked as the implementer's call.
- Durable findings: [dashboard Astro CSP](../memory/dashboard-astro-csp.md).
- Completion commit and push: recorded in the session report.
