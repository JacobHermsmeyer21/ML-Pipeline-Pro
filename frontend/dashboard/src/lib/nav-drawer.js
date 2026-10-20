// Off-canvas navigation below the desktop breakpoint; the sidebar is static above it.
const drawer = window.matchMedia("(max-width: 899px)");

export function initNavDrawer() {
  const toggle = document.getElementById("nav-toggle"), sidebar = document.getElementById("sidebar");
  const scrim = document.getElementById("nav-scrim"), close = document.getElementById("nav-close");
  const setOpen = (open, restoreFocus = false) => {
    sidebar.classList.toggle("open", open); scrim.hidden = !open;
    toggle.setAttribute("aria-expanded", String(open));
    if (open) sidebar.querySelector(".nav-item.active, .nav-item")?.focus();
    else if (restoreFocus) toggle.focus();
  };
  toggle.addEventListener("click", () => setOpen(!sidebar.classList.contains("open")));
  close.addEventListener("click", () => setOpen(false, true));
  scrim.addEventListener("click", () => setOpen(false, true));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && sidebar.classList.contains("open")) setOpen(false, true);
  });
  sidebar.querySelectorAll("[data-view]").forEach((node) => node.addEventListener("click", () => { if (drawer.matches) setOpen(false); }));
  drawer.addEventListener("change", () => setOpen(false));
}

initNavDrawer();
