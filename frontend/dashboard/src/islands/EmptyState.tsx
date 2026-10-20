// A small drawing of an untouched training curve for empty lists.
export default function EmptyState({ variant }: { variant: "runs" | "chat" }) {
  const label = variant === "runs" ? "Empty experiment chart" : "Empty conversation";
  return (
    <svg className="empty-illustration" viewBox="0 0 120 72" role="img" aria-label={label}>
      <rect x="1" y="1" width="118" height="70" rx="10" className="empty-frame" />
      <path d="M14 56h92M14 56V14" className="empty-axis" />
      <path d="M18 50c14-2 20-18 34-20s20 6 30-4 16-12 22-14" className="empty-curve" />
      <circle cx="104" cy="12" r="3.5" className="empty-dot" />
    </svg>
  );
}
