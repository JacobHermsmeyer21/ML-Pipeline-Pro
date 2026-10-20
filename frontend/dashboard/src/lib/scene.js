// Experiment space: a small 3D plot of the runs already held in `state`. Floor
// position is learning rate (log10) by hidden units (log2); height is validation F1.
// It only draws. Opening a run goes through `state.openRun`, owned by workspace.js.
import { animate } from "motion";
import { $, state, activeRuns, modelName, number } from "./core.js";

const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
const TAU = Math.PI * 2;
const view = { yaw: -0.65, pitch: 0.42, spin: 0 };
const rise = new Map(); // run id -> 0..1, so points grow out of the floor once
let canvas, ctx, tip, label, colors, size = { w: 0, h: 0, dpr: 1 };
let points = [], hovered = null, drag = null, frame = 0, visible = true, lastTime = 0;

const log = (value, base) => Math.log(value) / Math.log(base);
const clamp = (value, low, high) => Math.min(high, Math.max(low, value));
const mix = (a, b, t) => a.map((channel, index) => Math.round(channel + (b[index] - channel) * t));
const hex = (value) => { const n = parseInt(value.trim().slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; };
const rgb = (c, alpha = 1) => `rgb(${c[0]} ${c[1]} ${c[2]} / ${alpha})`;
// Same configuration, same spot: a stable offset from the ID keeps stacked runs apart.
const jitter = (id, salt) => { let h = salt; for (const ch of id) h = (h * 31 + ch.charCodeAt(0)) | 0; return ((h & 1023) / 1023 - 0.5) * 0.09; };

function extent(values, pad, fallback) {
  if (!values.length) return fallback;
  const low = Math.min(...values), high = Math.max(...values);
  return low === high ? [low - pad, high + pad] : [low - (high - low) * 0.12, high + (high - low) * 0.12];
}

function layout() {
  const runs = state.experiments.filter((run) => run.config?.learning_rate > 0 && run.config?.hidden_units > 0);
  const lr = extent(runs.map((run) => log(run.config.learning_rate, 10)), 1, [-3, -1]);
  const hu = extent(runs.map((run) => log(run.config.hidden_units, 2)), 1, [3, 6]);
  const range = (values, fallback) => (values.length ? [Math.min(...values), Math.max(...values)] : fallback);
  return { lr, hu, lrRange: range(runs.map((run) => run.config.learning_rate), [0.001, 0.1]),
    huRange: range(runs.map((run) => run.config.hidden_units), [8, 64]), runs: runs.map((run) => {
    const f1 = run.status === "succeeded" && Number.isFinite(run.metrics?.validation_f1) ? run.metrics.validation_f1 : null;
    return {
      run, f1, kind: f1 !== null ? "done" : activeRuns.has(run.status) ? "active" : "idle",
      x: clamp(((log(run.config.learning_rate, 10) - lr[0]) / (lr[1] - lr[0])) * 2 - 1 + jitter(run.id, 7), -1, 1),
      z: clamp(((log(run.config.hidden_units, 2) - hu[0]) / (hu[1] - hu[0])) * 2 - 1 + jitter(run.id, 13), -1, 1),
    };
  }) };
}

function project(x, y, z) {
  const yaw = view.yaw + view.spin, cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(view.pitch), sp = Math.sin(view.pitch);
  const x1 = x * cy - z * sy, z1 = x * sy + z * cy, y0 = y - 0.42;
  const y2 = y0 * cp - z1 * sp, z2 = y0 * sp + z1 * cp + 4;
  const f = Math.min(size.w * 1.15, size.h * 2.1), scale = f / z2;
  return { x: size.w / 2 + x1 * scale, y: size.h * 0.56 - y2 * scale, depth: z2, scale: scale / (f / 4) };
}

function line(a, b, style, width = 1) { ctx.strokeStyle = style; ctx.lineWidth = width; ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke(); }
// Labels stay inside the canvas whichever way the view has turned.
function text(value, at, style, align = "center") {
  const half = ctx.measureText(value).width / 2, x = align === "center" ? clamp(at.x, half + 6, size.w - half - 6) : at.x;
  ctx.fillStyle = style; ctx.textAlign = align; ctx.fillText(value, x, clamp(at.y, 10, size.h - 10));
}

function draw(time) {
  const { lrRange, huRange, runs } = layout();
  ctx.setTransform(size.dpr, 0, 0, size.dpr, 0, 0);
  ctx.clearRect(0, 0, size.w, size.h);
  ctx.font = "500 11px 'IBM Plex Sans', system-ui, sans-serif"; ctx.textBaseline = "middle";

  // Floor: a tray with a grid, then the F1 axis rising from the back corner.
  const corners = [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([x, z]) => project(x, 0, z));
  const floor = ctx.createLinearGradient(0, Math.min(...corners.map((c) => c.y)), 0, Math.max(...corners.map((c) => c.y)));
  floor.addColorStop(0, rgb(colors.accent, 0.03)); floor.addColorStop(1, rgb(colors.accent, 0.1));
  ctx.fillStyle = floor; ctx.beginPath(); corners.forEach((c, i) => (i ? ctx.lineTo(c.x, c.y) : ctx.moveTo(c.x, c.y))); ctx.closePath(); ctx.fill();
  for (let i = 0; i <= 8; i += 1) {
    const t = (i / 8) * 2 - 1, edge = i === 0 || i === 8;
    line(project(t, 0, -1), project(t, 0, 1), rgb(colors.grid, edge ? 0.9 : 0.45));
    line(project(-1, 0, t), project(1, 0, t), rgb(colors.grid, edge ? 0.9 : 0.45));
  }
  const back = [[-1, -1], [1, -1], [1, 1], [-1, 1]].reduce((far, [x, z]) => (project(x, 0, z).depth > project(far[0], 0, far[1]).depth ? [x, z] : far));
  for (const tick of [0, 0.5, 1]) {
    const at = project(back[0], tick, back[1]);
    if (tick) line(project(back[0], tick, back[1]), project(-back[0], tick, back[1]), rgb(colors.grid, 0.35));
    text(tick.toFixed(1), { x: at.x - 8, y: at.y }, rgb(colors.muted), "right");
  }
  line(project(back[0], 0, back[1]), project(back[0], 1.05, back[1]), rgb(colors.muted, 0.8), 1.2);
  text("F1", project(back[0], 1.14, back[1]), rgb(colors.text));
  const lrLabel = project(0, 0, 1.3), huLabel = project(1.3, 0, 0);
  text(`Learning rate ${lrRange[0]} to ${lrRange[1]}`, lrLabel, rgb(colors.muted));
  text(`Hidden units ${huRange[0]} to ${huRange[1]}`, huLabel, rgb(colors.muted));

  // Runs, far to near so closer points overlap farther ones.
  const pulse = reduced.matches ? 0.5 : (Math.sin(time / 380) + 1) / 2;
  points = runs.map((item) => {
    if (!rise.has(item.run.id)) { rise.set(item.run.id, reduced.matches ? 1 : 0); if (!reduced.matches) grow(item.run.id); }
    const height = (item.f1 ?? 0) * rise.get(item.run.id);
    return { ...item, base: project(item.x, 0, item.z), top: project(item.x, height, item.z) };
  }).sort((a, b) => b.top.depth - a.top.depth);
  for (const point of points) {
    const { base, top, kind } = point, active = hovered === point.run.id;
    ctx.fillStyle = rgb(colors.text, 0.12);
    ctx.beginPath(); ctx.ellipse(base.x, base.y, 9 * base.scale, 3.5 * base.scale, 0, 0, TAU); ctx.fill();
    if (kind === "active") {
      ctx.strokeStyle = rgb(colors.warning, 0.9 - pulse * 0.6); ctx.lineWidth = 2;
      ctx.beginPath(); ctx.ellipse(base.x, base.y, (8 + pulse * 14) * base.scale, (3 + pulse * 5) * base.scale, 0, 0, TAU); ctx.stroke();
      ctx.fillStyle = rgb(colors.warning); ctx.beginPath(); ctx.arc(base.x, base.y, 4 * base.scale, 0, TAU); ctx.fill();
      point.hit = base; continue;
    }
    if (kind === "idle") { ctx.fillStyle = rgb(colors.muted, 0.6); ctx.beginPath(); ctx.arc(base.x, base.y, 4 * base.scale, 0, TAU); ctx.fill(); point.hit = base; continue; }
    const tone = mix(colors.low, colors.high, clamp(point.f1, 0, 1));
    line(base, top, rgb(tone, 0.55), 2 * top.scale);
    const radius = (active ? 11 : 8) * top.scale;
    const sphere = ctx.createRadialGradient(top.x - radius * 0.35, top.y - radius * 0.4, radius * 0.1, top.x, top.y, radius);
    sphere.addColorStop(0, rgb(mix(tone, [255, 255, 255], 0.75))); sphere.addColorStop(0.45, rgb(tone)); sphere.addColorStop(1, rgb(mix(tone, [0, 0, 0], 0.35)));
    if (active) { ctx.fillStyle = rgb(tone, 0.18); ctx.beginPath(); ctx.arc(top.x, top.y, radius * 2, 0, TAU); ctx.fill(); }
    ctx.fillStyle = sphere; ctx.beginPath(); ctx.arc(top.x, top.y, radius, 0, TAU); ctx.fill();
    point.hit = top;
  }
  $("scene-empty").hidden = runs.length > 0;
}

function grow(id) {
  animate(0, 1, { type: "spring", stiffness: 120, damping: 14, delay: 0.15 + Math.random() * 0.25, onUpdate: (value) => { rise.set(id, value); request(); } });
}

// Idle spin and the running-run pulse are ambient motion, so reduced motion stops them.
function animating() {
  if (drag || view.velocity) return true;
  return !reduced.matches && (autoSpin() || points.some((point) => point.kind === "active"));
}
const autoSpin = () => !drag && !hovered && !document.hidden && Date.now() - (view.touched ?? 0) > 2500;
// Idle spin resumes a moment after the last interaction.
function touch() { view.touched = Date.now(); clearTimeout(view.resume); view.resume = setTimeout(request, 2600); }

function loop(time) {
  frame = 0;
  const step = Math.min(64, time - (lastTime || time)); lastTime = time;
  if (!drag && view.velocity) { view.yaw += view.velocity * step; view.velocity *= 0.92; if (Math.abs(view.velocity) < 0.0002) view.velocity = 0; }
  if (!reduced.matches && autoSpin()) view.spin += step * 0.00012;
  draw(time);
  if (visible && animating()) frame = requestAnimationFrame(loop); else lastTime = 0;
}
export function request() { if (!frame && visible && ctx) frame = requestAnimationFrame(loop); }

function resize() {
  const box = canvas.getBoundingClientRect();
  size = { w: box.width, h: box.height, dpr: Math.min(2, window.devicePixelRatio || 1) };
  canvas.width = Math.round(box.width * size.dpr); canvas.height = Math.round(box.height * size.dpr);
  request();
}

function nearest(event) {
  const box = canvas.getBoundingClientRect(), x = event.clientX - box.left, y = event.clientY - box.top;
  let best = null, distance = 18;
  for (const point of points) { const d = Math.hypot(point.hit.x - x, point.hit.y - y); if (d < distance) { best = point; distance = d; } }
  return best;
}

function showTip(point) {
  hovered = point?.run.id ?? null;
  canvas.style.cursor = drag ? "grabbing" : point ? "pointer" : "grab";
  tip.hidden = !point;
  if (!point) return;
  const { run } = point;
  tip.replaceChildren();
  const name = document.createElement("strong"); name.textContent = modelName(run.model_id);
  const detail = document.createElement("span");
  detail.textContent = point.f1 !== null ? `F1 ${number(point.f1)} · lr ${run.config.learning_rate} · ${run.config.hidden_units} units` : `${run.status.replace(/_/g, " ")} · lr ${run.config.learning_rate} · ${run.config.hidden_units} units`;
  tip.append(name, detail);
  const x = clamp(point.hit.x, 90, size.w - 90), y = point.hit.y - 18;
  tip.style.transform = `translate(${x}px, ${y}px) translate(-50%, -100%)`;
}

function describeScene() {
  const done = state.experiments.filter((run) => run.status === "succeeded").length;
  label.textContent = state.experiments.length
    ? `${state.experiments.length} experiments plotted, ${done} finished. Arrow keys turn the view; Enter opens the best run.`
    : "No experiments to plot yet.";
}

export function initScene() {
  canvas = $("scene-canvas"); tip = $("scene-tip"); label = $("scene-label");
  if (!canvas) return;
  ctx = canvas.getContext("2d");
  const css = getComputedStyle(document.documentElement), token = (name) => hex(css.getPropertyValue(name));
  colors = { accent: token("--accent"), grid: token("--border-strong"), muted: token("--text-faint"), text: token("--text"),
    warning: token("--scene-active"), low: token("--scene-low"), high: token("--scene-high") };
  new ResizeObserver(resize).observe(canvas);
  new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; if (visible) request(); }).observe(canvas);
  document.addEventListener("visibilitychange", request);
  reduced.addEventListener("change", request);

  canvas.addEventListener("pointerdown", (event) => {
    drag = { x: event.clientX, y: event.clientY, moved: 0, velocity: 0, time: event.timeStamp, start: nearest(event) };
    canvas.setPointerCapture(event.pointerId); view.velocity = 0; request();
  });
  canvas.addEventListener("pointermove", (event) => {
    if (!drag) { showTip(nearest(event)); request(); return; }
    const dx = event.clientX - drag.x, dy = event.clientY - drag.y, dt = Math.max(1, event.timeStamp - drag.time);
    drag.moved += Math.abs(dx) + Math.abs(dy); drag.x = event.clientX; drag.y = event.clientY; drag.time = event.timeStamp;
    view.yaw += dx * 0.008; view.pitch = clamp(view.pitch + dy * 0.005, 0.12, 1.2); drag.velocity = (dx * 0.008) / dt;
    touch(); showTip(null); request();
  });
  const release = (event) => {
    if (!drag) return;
    const clicked = drag.moved < 6 && drag.start;
    view.velocity = reduced.matches ? 0 : drag.velocity; drag = null; touch();
    if (clicked && event.type === "pointerup") state.openRun?.(clicked.run.id);
    showTip(event.type === "pointerup" ? nearest(event) : null); request();
  };
  canvas.addEventListener("pointerup", release);
  canvas.addEventListener("pointercancel", release);
  canvas.addEventListener("pointerleave", () => { if (!drag) { showTip(null); touch(); request(); } });
  canvas.addEventListener("keydown", (event) => {
    const turn = { ArrowLeft: [-0.15, 0], ArrowRight: [0.15, 0], ArrowUp: [0, -0.08], ArrowDown: [0, 0.08] }[event.key];
    if (turn) {
      event.preventDefault(); touch();
      if (reduced.matches) { view.yaw += turn[0]; view.pitch = clamp(view.pitch + turn[1], 0.12, 1.2); request(); return; }
      const from = { yaw: view.yaw, pitch: view.pitch };
      animate(0, 1, { type: "spring", stiffness: 260, damping: 26, onUpdate: (t) => {
        view.yaw = from.yaw + turn[0] * t; view.pitch = clamp(from.pitch + turn[1] * t, 0.12, 1.2); request();
      } });
    } else if (event.key === "Enter") {
      const best = points.filter((point) => point.f1 !== null).sort((a, b) => b.f1 - a.f1)[0];
      if (best) state.openRun?.(best.run.id);
    }
  });
  state.onWorkspaceRender = () => { describeScene(); request(); };
  describeScene(); resize();
}
