// Motion that answers the user: views swing in, changed readouts pop, the nav
// highlight slides, panels catch a light under the pointer and cards tilt.
// Everything observes the DOM the behavior modules own and never writes content.
import { animate } from "motion";

const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
const fine = window.matchMedia("(hover: hover) and (pointer: fine)");
const settle = { type: "spring", stiffness: 220, damping: 24 };

function viewTransitions() {
  const observer = new MutationObserver((records) => {
    for (const { target } of records) {
      if (target.hidden || reduced.matches) continue;
      animate(target, { opacity: [0, 1], transform: ["perspective(1400px) rotateX(7deg) translateY(18px)", "perspective(1400px) rotateX(0deg) translateY(0px)"] }, settle)
        .then(() => { target.style.transform = ""; target.style.opacity = ""; });
    }
  });
  document.querySelectorAll(".view-section").forEach((node) => observer.observe(node, { attributes: true, attributeFilter: ["hidden"] }));
}

function readoutPops() {
  for (const value of document.querySelectorAll(".plate strong")) {
    let previous = value.textContent;
    new MutationObserver(() => {
      if (value.textContent === previous) return;
      previous = value.textContent;
      if (reduced.matches) return;
      animate(value, { transform: ["translateZ(0px) scale(1.22)", "translateZ(0px) scale(1)"] }, { type: "spring", stiffness: 400, damping: 15 });
    }).observe(value, { childList: true, characterData: true, subtree: true });
  }
}

function navIndicator() {
  const nav = document.querySelector(".sidebar nav"), mark = document.createElement("span");
  mark.className = "nav-indicator"; mark.setAttribute("aria-hidden", "true"); nav.prepend(mark);
  let placed = false;
  const place = () => {
    const active = nav.querySelector(".nav-item.active");
    mark.hidden = !active || !active.offsetHeight;
    if (mark.hidden) return;
    const target = { transform: `translateY(${active.offsetTop}px)`, height: `${active.offsetHeight}px` };
    if (!placed || reduced.matches) { Object.assign(mark.style, target); placed = true; return; }
    animate(mark, target, { type: "spring", stiffness: 420, damping: 32 });
  };
  new MutationObserver(place).observe(nav, { subtree: true, attributes: true, attributeFilter: ["class"] });
  new ResizeObserver(place).observe(nav);
  place();
}

// One delegated listener drives the specular light and the card tilt.
function pointerDepth() {
  let lit = null, tilted = null;
  const clear = () => {
    lit?.classList.remove("lit"); lit = null;
    if (tilted) { tilted.style.removeProperty("--rx"); tilted.style.removeProperty("--ry"); tilted = null; }
  };
  document.addEventListener("pointermove", (event) => {
    if (event.pointerType !== "mouse" || !fine.matches) return;
    const surface = event.target.closest?.(".panel, .plate, .grafana-card");
    if (surface !== lit) { lit?.classList.remove("lit"); lit = surface; surface?.classList.add("lit"); }
    if (surface) {
      const box = surface.getBoundingClientRect();
      surface.style.setProperty("--mx", `${event.clientX - box.left}px`); surface.style.setProperty("--my", `${event.clientY - box.top}px`);
    }
    const card = reduced.matches ? null : event.target.closest?.(".record-card, .prompt-starters button");
    if (card !== tilted && tilted) { tilted.style.removeProperty("--rx"); tilted.style.removeProperty("--ry"); }
    tilted = card;
    if (card) {
      const box = card.getBoundingClientRect(), x = (event.clientX - box.left) / box.width - 0.5, y = (event.clientY - box.top) / box.height - 0.5;
      card.style.setProperty("--rx", `${(-y * 5).toFixed(2)}deg`); card.style.setProperty("--ry", `${(x * 5).toFixed(2)}deg`);
    }
  }, { passive: true });
  document.addEventListener("pointerleave", clear);
  reduced.addEventListener("change", clear);
}

export function initMotion() {
  viewTransitions(); readoutPops(); navIndicator(); pointerDepth();
}
