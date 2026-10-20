# Dashboard 3D depth, motion and interaction

- Status: approved to proceed; implementation in progress
- Date: 2026-10-20
- Source baseline: `d259343` on `dashboard-redesign`; work branch `dashboard-3d`
- Request: "make the UI very 3D, Motion One and then very responsive, interactive,
  very cool UI", designed as an experienced product designer would
- Human reviewer/approval: repository owner (lama9811), October 20, in chat. Offered
  clarifying questions, they answered "DO IT", which approves proceeding on the
  implementer's design without further questions. They did not review this
  document before implementation. The design is shown with screenshots at handoff.
- Independent review: not needed. There are no concurrency, state-machine or
  rate/size changes. The reviewer was a self-review, disclosed as such.

## Proposed behavior and purpose

This plan supersedes the "subtle depth rather than heavy 3D" decision in the
[October 19 redesign plan](2026-10-19-dashboard-redesign-plan.md). Every workflow,
ID, request and the light theme stay as they are. The overview gains one
signature 3D element and a consistent physical interaction language.

## Design (implementer's calls)

- **Experiment space** (signature element). A canvas 3D plot sits beside the
  readouts. Each experiment is placed on the floor by learning rate (log scale) and
  hidden units (log2 scale), and its height is its validation F1. Drag, or use the
  arrow keys, to orbit. Idle auto-rotation runs only without reduced motion. Hover
  shows the run in a tooltip. Click or Enter opens its detail through the existing
  `showRun`. Running runs pulse on the floor, and failed runs lie flat in grey. The
  data comes from the `state` the behavior modules already own; the scene draws
  only. Runs with the same configuration get a small deterministic floor offset so
  they stay visible. The legend says so. The table stays the accessible record.
- **Readout plates.** The stat strip becomes separate plates at different
  `translateZ` depths inside the existing tilting `DepthCard`. Changed values pop
  forward briefly.
- **Physical controls.** Primary and secondary buttons are keycaps with an extruded
  base that press down. Panels carry a soft specular highlight that follows the
  pointer (CSS variables written at runtime). Record cards tilt slightly.
- **Motion** (`motion` 13.5.1, pinned; released October 2, more than two weeks
  before install). There is one orchestrated page-load sequence: plates rise from
  depth with a stagger, then panels settle in. Switching views swings the incoming
  section in from a slight `rotateX`. Dialogs open with a 3D CSS keyframe.
  Everything is disabled under `prefers-reduced-motion`.
- **Background.** A receding perspective grid floor behind the hero.

## Constraints

- No `/api/v1`, idempotency, storage-key or ID changes. Behavior-module edits are
  limited to one render hook (`state.onWorkspaceRender`) and exporting `showRun`.
- CSP: no inline styles in the built HTML. Runtime `element.style` and WAAPI are
  allowed. All code is bundled.
- Responsive from 360 px: the scene stacks under the readouts below 900 px, and no
  horizontal page scroll is introduced.

## Acceptance and verification

`npm run check`, `npm run build` (output committed), and `npm run test:e2e`, with
new tests for the scene: it renders and labels the run count, clicking a point
opens the run detail, reduced motion stops auto-rotation, and there are no CSP
console errors. The existing overflow, axe and tilt tests must still pass
unchanged. Also run the `uv` fast gates from `AGENTS.md`, and capture screenshots
at 390 and 1440 px.

## Risks and rollback

Risks are GPU and CPU cost on low-end laptops and visual noise. Mitigations: the
scene renders only while visible and animating, and caps DPR at 2. Rollback is a
revert. No stored data is affected.

## Implementation outcome

- Scope: `frontend/dashboard/src/lib/scene.js` and `motion.js` (new),
  `styles/depth.css` (new), and the readout tray and keycap buttons in
  `components.css`. `ExperimentSpace.astro` is new, and `StatsGrid.astro` and
  `DepthCard.tsx` changed (perspective moved to the hero). The behavior-module edits
  are two lines in `workspace.js` (`state.onWorkspaceRender`, `state.openRun`).
  Dependency: `motion` 13.5.1. The committed build is regenerated.
- Results (October 20, macOS, Node 24): `npm run check` reports 0 errors. Playwright
  gives 30 passed, including 4 new tests in `tests/scene.spec.ts`. `ruff check` and
  `ruff format --check` pass. `pytest -m "not integration"` gives 743 passed and 114
  deselected. `uv pip check` passes.
- Gap: real-service integration gates were not run, because nothing touches MongoDB,
  queues or workers.
