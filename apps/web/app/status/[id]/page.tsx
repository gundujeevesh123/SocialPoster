"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";
import StatusBadge from "../../../components/StatusBadge";
import { EmojiBurst } from "../../../components/Fx";
import { meta } from "../../../lib/platforms";

type TargetStatus = {
  target_id: string; platform: string; status: string;
  attempts: number; error: string | null; external_url: string | null;
};

export default function LiveStatus() {
  const { id } = useParams<{ id: string }>();
  const [targets, setTargets] = useState<TargetStatus[]>([]);
  const [live, setLive] = useState(true);

  useEffect(() => {
    if (!id) return;
    const es = new EventSource(`/api/v1/posts/${id}/events`);
    es.onmessage = (e) => setTargets(JSON.parse(e.data));
    es.addEventListener("done", () => { setLive(false); es.close(); });
    es.onerror = () => {
      es.close();
      const t = setInterval(async () => {
        try {
          const st = await api.get(`/posts/${id}/status`);
          setTargets(st.targets.map((x: any) => ({
            target_id: x.id, platform: x.platform, status: x.status,
            attempts: x.job?.attempts ?? 0, error: x.job?.error ?? null,
            external_url: x.job?.external_url ?? null,
          })));
        } catch { clearInterval(t); }
      }, 2000);
      return () => clearInterval(t);
    };
    return () => es.close();
  }, [id]);

  async function retry(targetId: string) {
    await api.post(`/posts/${id}/publish`, { target_ids: [targetId] },
                   { "Idempotency-Key": crypto.randomUUID() });
  }

  const allLive = targets.length > 0 && targets.every((t) => t.status === "published");
  const confetti = allLive
    ? Array.from({ length: 44 }, (_, i) => ({
        left: `${(i * 137.5) % 100}%`,
        background: ["#39ff14", "#ffffff", "#0A66C2", "#FF0000", "#a78bfa"][i % 5],
        animationDuration: `${2.2 + (i % 5) * 0.5}s`,
        animationDelay: `${(i % 10) * 0.12}s`,
      }))
    : [];

  return (
    <div className="space-y-8">
      {allLive && confetti.map((c, i) => <span key={i} className="confetti" style={c} />)}
      {allLive && <EmojiBurst />}
      <div className="flex flex-wrap items-center justify-between gap-4 animate-pop">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white">
            Publish <span className="neon-text">status</span>
          </h1>
          <p className="mt-1 flex items-center gap-2 text-sm text-neutral-400">
            {live ? (<><span className="relative flex h-2.5 w-2.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#39ff14] opacity-60" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-[#39ff14]" />
            </span> Live — updates stream in as they happen.</>) : "Finished."}
          </p>
        </div>
        <Link href="/history" className="btn-ghost">History</Link>
      </div>

      {allLive && (
        <div className="hero !p-5 text-center text-lg font-bold text-white animate-pop">
          🎉 All live! Your post is out in the world.
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {targets.length === 0 && (
          <div className="card flex items-center gap-2 text-sm text-neutral-400">
            <span className="spinner text-[#39ff14]" /> Waiting for status…
          </div>
        )}
        {targets.map((t) => {
          const m = meta(t.platform);
          return (
            <div key={t.target_id} className={`card space-y-3 ${m.ring}`}>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-sm font-bold text-white">
                  <span className={`h-2.5 w-2.5 rounded-full ${m.dot}`} /> {m.emoji} {m.label}
                </span>
                <StatusBadge status={t.status} />
              </div>
              {t.status === "publishing" && <div className="progress-bar" />}
              {t.status === "publishing" && t.attempts > 1 && (
                <p className="text-xs text-cyan-300">attempt {t.attempts} — auto-retrying with backoff, hang tight</p>
              )}
              {t.external_url && (
                <a href={t.external_url} target="_blank"
                   className="block truncate rounded-lg bg-[#39ff14]/10 px-3 py-2 text-sm font-semibold text-[#39ff14] ring-1 ring-[#39ff14]/25 hover:underline">
                  🔗 {t.external_url}
                </a>
              )}
              {t.error && <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-300 ring-1 ring-rose-500/25 whitespace-pre-wrap">{t.error}</p>}
              {(t.status === "failed" || t.status === "requires_action") && (
                <button className="btn-ghost !py-1.5 text-xs" onClick={() => retry(t.target_id)}>↻ Try again</button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
