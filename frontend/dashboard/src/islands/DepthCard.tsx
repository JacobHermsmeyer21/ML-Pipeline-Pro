import { useEffect, useRef, type ReactNode } from "react";

// Tilts its children toward the pointer inside the parent's perspective. The children are Astro-rendered
// markup owned by the behavior modules; this component never re-renders them.
export default function DepthCard({ children, maxTilt = 4 }: { children: ReactNode; maxTilt?: number }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = ref.current;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (!node) return;
    let frame = 0;
    const reset = () => { cancelAnimationFrame(frame); node.style.transform = ""; };
    const move = (event: PointerEvent) => {
      if (reduced.matches || event.pointerType !== "mouse") return;
      const box = node.getBoundingClientRect();
      const x = (event.clientX - box.left) / box.width - 0.5, y = (event.clientY - box.top) / box.height - 0.5;
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        node.style.transform = `rotateX(${(-y * maxTilt).toFixed(2)}deg) rotateY(${(x * maxTilt).toFixed(2)}deg)`;
      });
    };
    node.addEventListener("pointermove", move);
    node.addEventListener("pointerleave", reset);
    reduced.addEventListener("change", reset);
    return () => {
      node.removeEventListener("pointermove", move);
      node.removeEventListener("pointerleave", reset);
      reduced.removeEventListener("change", reset);
      reset();
    };
  }, [maxTilt]);

  return <div ref={ref} className="depth-card">{children}</div>;
}
