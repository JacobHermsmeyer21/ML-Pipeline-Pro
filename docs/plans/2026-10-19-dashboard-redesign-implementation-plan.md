# Dashboard Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the `/dashboard/` markup and styling as an Astro + React-islands
project with a bright, restrained, responsive design and subtle depth. Every
existing workflow keeps working.

**Architecture:** An Astro project in `frontend/dashboard/` renders static markup
from components and bundles the existing behavior modules unchanged in logic.
React islands add tilt and empty-state visuals only. `astro build` writes into
`src/ml_pipeline_pro/dashboard/`, which is committed and served by the existing
`DashboardFiles`, with build-generated CSP hashes.

**Tech Stack:** Astro 7.4, `@astrojs/react` 7.1, React 19.3, TypeScript,
`@fontsource-variable/inter`, Playwright, `@axe-core/playwright`, Node 24,
FastAPI/pytest (existing).

**Spec:** [`docs/plans/2026-10-19-dashboard-redesign-plan.md`](2026-10-19-dashboard-redesign-plan.md)

## Global Constraints

- No change to `/api/v1` requests, headers, `Idempotency-Key` use, `sessionStorage` keys (`mlpp:<project>:*`, `mlpp:active-project`) or generation fencing.
- Every element ID listed under "Owned IDs" in Task 1 exists exactly once in the built page.
- Every class name the behavior modules generate keeps its name and gets a style: `action-buttons action-card assistant chat-message check-field column-choice detail-metric detail-metrics empty-state encoding-card encoding-category-list encoding-heading encoding-labels error-text fact facts-list form-footer grafana-card graph-placeholder hash-text key-values loading-text message-label muted-note panel-title record-actions record-card record-meta secondary snippet-card status-dot teal-text text-button user status-badge notice status-chip danger-button active nav-item view-section`.
- CSP header never contains `unsafe-inline`, `unsafe-eval` or `unsafe-hashes`; the built HTML has no `style="` attribute.
- `/dashboard/example.csv` is byte-identical to `examples/data/classification.csv`.
- The "Pipeline agent" heading text stays.
- Light theme only; canvas `#f7f8fa`, surface `#ffffff`, one indigo accent; Inter Variable self-hosted.
- No sparkle icon, glow, gradient text, all-caps kicker labels or slogan headlines ("Your next model starts here", "Let's build something useful", "Built to experiment").
- Motion transforms are disabled under `prefers-reduced-motion: reduce`.
- No horizontal page scroll at 360, 390, 768, 1024 or 1440 px.
- Node is pinned to 24 via `.nvmrc` and `engines`; `package-lock.json` is committed and installed with `npm ci`.

## Review Focus

- A 80-character dataset or model name must wrap or truncate with a title, not widen the page at 360 px. Pinned in Task 3.
- 100 experiment rows at 360 px scroll inside the table panel, not the page. Pinned in Task 3.
- A column dialog with 40 columns fits the viewport with its own scroll, and the save buttons stay reachable at 390 × 700. Pinned in Task 3.
- The mobile nav drawer opens and closes with the keyboard (Enter, Escape) and returns focus to its toggle. Pinned in Task 3.
- A long error notice with a 36-character correlation ID wraps inside its notice at 360 px. Pinned in Task 3.

---

### Task 1: Astro scaffold that reproduces the current dashboard

**Files:**
- Create: `frontend/dashboard/{package.json,package-lock.json,astro.config.mjs,tsconfig.json,.nvmrc}`
- Create: `frontend/dashboard/src/pages/index.astro` (current `index.html` body, verbatim)
- Create: `frontend/dashboard/src/styles/legacy.css` (current `styles.css`, moved)
- Move: `src/ml_pipeline_pro/dashboard/*.js` → `frontend/dashboard/src/lib/*.js` (`git mv`, no logic edits)
- Move: `src/ml_pipeline_pro/dashboard/example.csv` → `frontend/dashboard/public/example.csv`
- Create: `frontend/dashboard/scripts/postbuild.mjs`
- Modify: `tests/test_dashboard.py`, `.gitignore`
- Output (committed): `src/ml_pipeline_pro/dashboard/**`

**Interfaces:**
- Produces: `npm run build` → `astro build && node scripts/postbuild.mjs`; output `src/ml_pipeline_pro/dashboard/index.html`, `_astro/*.js|css`, `example.csv`, `csp-hashes.json` shaped `{"script-src": string[], "style-src": string[]}` (each entry `'sha256-<base64>'`; empty lists now).
- Owned IDs: every `$("…")` ID in the current modules (see the spec's source list), plus `view-runs`, `view-datasets`, `workspace`.

- [ ] **Step 1: Write failing tests in `tests/test_dashboard.py`**

```python
def test_dashboard_references_only_served_local_assets(client):
    html = client.get("/dashboard/").text
    refs = re.findall(r'(?:src|href)="(/dashboard/[^"#]+)"', html)
    assert any(r.endswith(".js") for r in refs) and any(r.endswith(".css") for r in refs)
    for ref in refs:
        assert client.get(ref).status_code == 200, ref
    assert "style=" not in html


def test_dashboard_has_no_unhashed_inline_code():
    root = Path("src/ml_pipeline_pro/dashboard")
    html = (root / "index.html").read_text()
    hashes = json.loads((root / "csp-hashes.json").read_text())
    for tag, directive in (("script", "script-src"), ("style", "style-src")):
        for body in re.findall(rf"<{tag}(?![^>]*\bsrc=)[^>]*>(.*?)</{tag}>", html, re.S):
            digest = base64.b64encode(hashlib.sha256(body.encode()).digest()).decode()
            assert f"'sha256-{digest}'" in hashes[directive]
```

Remove `"app.js", "styles.css"` from the fixed-asset loop in the existing CSP test (keep `example.csv`). Reason: Astro emits hashed filenames; the new test checks that every referenced asset is served, which is the requirement the old assertion stood for.

- [ ] **Step 2:** Run `uv run --locked pytest tests/test_dashboard.py -v`. Expected: the new tests FAIL (no `csp-hashes.json`, no `/dashboard/_astro` refs).
- [ ] **Step 3: Scaffold.** `astro.config.mjs`: `outDir: "../../src/ml_pipeline_pro/dashboard"`, `base: "/dashboard/"`, `build: { format: "file", inlineStylesheets: "never", assets: "_astro" }`, `vite.build.assetsInlineLimit: 0`, `integrations: [react()]`. `index.astro` imports `legacy.css` in frontmatter and loads the modules with one `<script>import "../lib/app.js";</script>`. The `.astro` `<script>` is bundled and external. `postbuild.mjs` hashes every inline `<script>`/`<style>` body in `index.html` and writes `csp-hashes.json`. Check that Astro 7's `security.csp` option exists; if it does, it may compute the hashes instead, but the output file contract stays the same. `.gitignore`: add `frontend/dashboard/node_modules/`, `frontend/dashboard/.astro/`, `frontend/dashboard/test-results/`, `frontend/dashboard/playwright-report/`.
- [ ] **Step 4:** Run `cd frontend/dashboard && npm ci && npm run build`, then `uv run --locked pytest tests/test_dashboard.py -v`. Expected: PASS, including the packaged `example.csv` test.
- [ ] **Step 5:** Start uvicorn and open `/dashboard/` in Playwright MCP. Expected: it looks the same as before the move, with zero console errors other than the expected 503s.
- [ ] **Step 6:** Run the fast gates (`ruff check`, `ruff format --check`, `pytest -m "not integration" --cov`). Commit "Build dashboard from Astro without visual change".

### Task 2: Playwright regression net with a mocked API

**Files:**
- Create: `frontend/dashboard/playwright.config.ts`, `frontend/dashboard/tests/fixtures/api.ts`, `frontend/dashboard/tests/workflows.spec.ts`
- Modify: `frontend/dashboard/package.json` (`"test:e2e": "playwright test"`)

**Interfaces:**
- Consumes: the built page from Task 1.
- Produces: `mockApi(page: Page, overrides?: Partial<ApiState>): Promise<ApiLog>`, where `ApiLog.requests` is an array of `{method, path, headers, body}`. Fixtures `dataset`, `model`, `experimentCompleted`, `experimentRunning`, `conversationTurn`, `actionProposal` are built from the Pydantic response models in `src/ml_pipeline_pro/` (field names copied, not invented).
- `webServer`: `uv run --locked uvicorn ml_pipeline_pro.main:create_app --factory --port 8123`, run from the repo root with `MLPP_DATASET_UPLOAD_ENABLED=true` and `MLPP_CHAT_ENABLED=true`. All `/api/v1/**` requests are served by `page.route`.

- [ ] **Step 1: Write the workflow specs.** Each one asserts on `ApiLog`:
  - `connects with project and key`: after the connection dialog, every request carries `X-Project-ID: alpha` and `X-API-Key`.
  - `review-then-train submits once`: double-clicking "Start training" leads to exactly one `POST /experiments` with an `Idempotency-Key` header.
  - `pending training survives reload`: if the POST stalls, reloading shows `#training-recovery` visible.
  - `upload preview then prepare`: choosing `example.csv` previews, and saving leads to one `POST /datasets/prepare`.
  - `column edit saves new version`: one `POST /datasets/{id}/columns`.
  - `model delete shows scope first`: a preview `GET` comes before any `DELETE`.
  - `chat approve and reject`: reject sends no experiment POST; approve sends exactly one.
  - `monitoring empty state`: `#monitor-summary` shows the no-observations text.
- [ ] **Step 2:** Run `npm run test:e2e`. Expected: PASS against the Task 1 page. If a spec fails, fix the spec's fixture shape against source, never the behavior module.
- [ ] **Step 3:** Commit "Add mocked-API browser regression tests for the dashboard".

### Task 3: Visual system and responsive layout

**Files:**
- Create: `frontend/dashboard/src/styles/{tokens.css,base.css,layout.css,components.css}` (replacing `legacy.css`, which is deleted)
- Create: `frontend/dashboard/src/components/{Icon.astro,IconSprite.astro,Sidebar.astro,Topbar.astro,StatsGrid.astro,LaunchPanel.astro,RunsPanel.astro,DatasetsView.astro,MonitoringView.astro,AgentPanel.astro}` and `src/components/dialogs/{Connection,Model,Models,Review,Column}Dialog.astro`
- Create: `frontend/dashboard/src/lib/nav-drawer.js`
- Modify: `frontend/dashboard/src/pages/index.astro`
- Test: `frontend/dashboard/tests/layout.spec.ts`

**Interfaces:**
- Consumes: Owned IDs and the class list from Global Constraints; `mockApi` from Task 2.
- Produces: tokens `--canvas --surface --surface-sunken --border --text --text-muted --accent --accent-strong --success --warning --danger --radius-sm(8px) --radius-md(12px) --elev-1 --elev-2 --elev-3 --space-1…--space-8 (4px steps)`; `initNavDrawer(): void` (toggle `#nav-toggle`, closes on Escape and on nav click, restores focus).

- [ ] **Step 1: Write `layout.spec.ts`** for viewports 360, 390, 768, 1024 and 1440:
  - `document.documentElement.scrollWidth <= innerWidth`
  - Review Focus cases: an 80-character name; 100 experiment rows (the table's wrapper scrolls, the page doesn't); 40 columns in `#column-dialog` at 390 × 700 with `#column-save` reachable by scrolling the dialog; drawer opens with Enter, closes with Escape and focus returns to `#nav-toggle`; a long error notice keeps `notice.scrollWidth <= notice.clientWidth`.
  - Banned copy is absent from the page text.
  - The page has no `use[href="#i-spark"]`.
  - `@axe-core/playwright` reports no serious or critical violations.
  - Full-page screenshots are saved to `test-results/screens/<width>.png`.
- [ ] **Step 2:** Run it. Expected: FAIL (banned copy present, overflow cases).
- [ ] **Step 3: Implement the components and styles.** Below 900 px, the sidebar becomes an off-canvas drawer with `#nav-toggle` in the topbar. The workspace grid goes from main + 360 px agent column (≥1200 px) to a single column, with the agent panel after the main content. Tables sit in `.table-scroll` with `overflow-x:auto`, and dialogs use `max-height: calc(100dvh - 32px); overflow:auto`. Rewrite the copy to plain product language; keep "Pipeline agent". Use the elevation tokens in place of borders-only cards, and make hover lift `translateY(-1px)` + `--elev-2`. Style every class in the Global Constraints list; `teal-text` becomes the accent color.
- [ ] **Step 4:** Run `npm run build && npm run test:e2e`, then the pytest dashboard tests. Expected: all PASS. Read each screenshot and fix anything misaligned.
- [ ] **Step 5:** Commit "Redesign dashboard layout and visual system".

### Task 4: React depth islands and CSP hashes in the header

**Files:**
- Create: `frontend/dashboard/src/islands/{DepthCard.tsx,EmptyState.tsx}`
- Modify: `StatsGrid.astro`, `RunsPanel.astro`, `AgentPanel.astro`
- Modify: `src/ml_pipeline_pro/dashboard_api.py`
- Test: `tests/test_dashboard.py`, `frontend/dashboard/tests/depth.spec.ts`

**Interfaces:**
- Produces: `DepthCard({children, maxTilt = 4}: {children: ReactNode; maxTilt?: number})`. It sets `transform` via a ref on pointer move and resets on leave, and does nothing when `matchMedia("(prefers-reduced-motion: reduce)")` matches. `EmptyState({variant}: {variant: "runs" | "chat"})` is SVG only. Both are used with `client:visible`, and the owned IDs stay in Astro slot children.
- Produces: `load_csp_hashes(directory: Path) -> dict[str, list[str]]` in `dashboard_api.py`, read once in `install_dashboard`. A missing file gives empty lists.

- [ ] **Step 1: Write failing tests.**
  - pytest `test_csp_header_includes_build_hashes`: every hash in `csp-hashes.json` appears in the `script-src` or `style-src` header, and no `unsafe-` token appears anywhere.
  - Playwright `depth.spec.ts`:
    - moving the pointer over `#stat-runs`' card changes its computed `transform`
    - with `reducedMotion: "reduce"` the transform stays `none`
    - zero `console` messages containing "Content Security Policy"
    - after `mockApi` sets 3 experiments, `#stat-runs` shows `3`, which proves hydration did not replace owned nodes
- [ ] **Step 2:** Run both suites. Expected: FAIL.
- [ ] **Step 3: Implement** the islands and the header extension (`script-src 'self' <hashes>; style-src 'self' <hashes>`), leaving all other directives unchanged.
- [ ] **Step 4:** Run `npm run build`, `npm run test:e2e` and the full fast gates. Expected: PASS.
- [ ] **Step 5:** Commit "Add depth islands and hash-based CSP for Astro inline code".

### Task 5: CI, docs, packaging check and plan outcome

**Files:**
- Modify: `.github/workflows/ci.yml` (new `dashboard-build` job), `README.md`, `docs/guides/dashboard.md`
- Modify: `docs/plans/2026-10-19-dashboard-redesign-plan.md` (Implementation outcome)

- [ ] **Step 1: Add the CI job.** It runs `actions/setup-node` with `node-version-file: frontend/dashboard/.nvmrc` and `astral-sh/setup-uv`, then:
  1. `uv sync --locked`
  2. `npm ci`
  3. `npx astro check`
  4. `npm run build`
  5. `git diff --exit-code -- src/ml_pipeline_pro/dashboard`
  6. `npx playwright install --with-deps chromium`
  7. `npm run test:e2e`
- [ ] **Step 2: Update the docs.** Add a "Develop the dashboard" section (`npm ci`, `npm run dev` with a proxy to `:8000`, `npm run build` before commit). Replace current-state mentions of `app.js`/`styles.css`, and leave evidence files alone.
- [ ] **Step 3:** Run `uv build`, then `unzip -l dist/*.whl | grep dashboard/`. Expected: `index.html`, `_astro/` assets, `csp-hashes.json` and `example.csv` are listed. Run `git diff --check` and validate the new doc links.
- [ ] **Step 4:** Request a code review with superpowers:requesting-code-review, scoped to the CSP, build and DOM-ownership changes. It is same-vendor and disclosed as such. Record the findings and resolutions in the spec's Implementation outcome, along with commands, results, screenshots and the real-service gap (no Docker on this machine).
- [ ] **Step 5:** Fetch `origin`, integrate any incoming commits and rerun the affected checks. Commit "Document dashboard build and record redesign outcome" and push.
