export default function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    published: "bg-[#39ff14]/15 text-[#39ff14] ring-1 ring-[#39ff14]/30",
    publishing: "bg-cyan-500/15 text-cyan-300 ring-1 ring-cyan-500/30",
    queued: "bg-violet-500/15 text-violet-300 ring-1 ring-violet-500/30",
    scheduled: "bg-amber-500/10 text-amber-300 ring-1 ring-amber-500/30",
    failed: "bg-rose-500/15 text-rose-300 ring-1 ring-rose-500/30",
    requires_action: "bg-amber-500/20 text-amber-200 ring-1 ring-amber-400/40",
    draft: "bg-neutral-800 text-neutral-400 ring-1 ring-neutral-700",
    canceled: "bg-neutral-800 text-neutral-500 line-through ring-1 ring-neutral-700",
  };
  const icon: Record<string, string> = {
    published: "✓", publishing: "", queued: "•", scheduled: "🕐",
    failed: "✕", requires_action: "⚠", draft: "✎", canceled: "—",
  };
  return (
    <span className={`badge ${map[status] ?? "bg-neutral-800 text-neutral-400"}`}>
      {status === "publishing" ? <span className="spinner" /> : <span>{icon[status] ?? ""}</span>}
      {status.replaceAll("_", " ")}
    </span>
  );
}
