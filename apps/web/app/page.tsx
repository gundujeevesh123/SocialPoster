"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import StatusBadge from "../components/StatusBadge";
import { Magnetic, Tilt } from "../components/Fx";
import { PLATFORM_ORDER, meta } from "../lib/platforms";

type Account = { id: string; platform: string; account_name: string; status: string; token_expires_at: string | null };
type Notif = { id: string; type: string; payload: any; read: boolean; created_at: string };

export default function Dashboard() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [notifs, setNotifs] = useState<Notif[]>([]);
  const [recent, setRecent] = useState<any[]>([]);

  useEffect(() => {
    api.get("/connected-accounts").then(setAccounts).catch(() => {});
    api.get("/notifications?unread_only=true").then(setNotifs).catch(() => {});
    api.get("/posts").then((p) => setRecent(p.slice(0, 5))).catch(() => {});
  }, []);

  const connected = new Set(accounts.filter((a) => a.status === "active").map((a) => a.platform));

  return (
    <div className="space-y-10">
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight text-white">
          Hey there <span className="neon-text">👋</span>
        </h1>
        <p className="mt-1 text-sm text-neutral-400">Write once. Shine everywhere — through official APIs only.</p>
      </div>

      <section className="hero beam-card flex flex-wrap items-center justify-between gap-4 animate-pop stagger-1">
        <div>
          <h2 className="text-xl font-bold text-white">Ready to make some noise?</h2>
          <p className="mt-1 text-sm text-neutral-400">One upload, one caption → every platform at once.</p>
        </div>
        <Magnetic><Link href="/create" className="btn !px-7">⚡ New post</Link></Magnetic>
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-bold uppercase tracking-wide text-neutral-400">Your platforms</h2>
          <Link href="/settings" className="text-sm font-semibold text-[#39ff14] hover:underline">Manage →</Link>
        </div>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {PLATFORM_ORDER.map((p, i) => {
            const m = meta(p);
            return (
              <Tilt key={p} className={`card !p-4 animate-pop ${m.ring}`} max={10}>
                <div className="flex items-center gap-2">
                  <span className={`h-2.5 w-2.5 rounded-full ${m.dot}`} />
                  <span className="text-sm font-semibold text-white">{m.label}</span>
                </div>
                <div className={`badge mt-3 ${connected.has(p)
                  ? "bg-[#39ff14]/15 text-[#39ff14] ring-1 ring-[#39ff14]/30"
                  : p === "linkedin" ? "bg-neutral-800 text-neutral-400 ring-1 ring-neutral-700"
                  : "bg-violet-500/15 text-violet-300 ring-1 ring-violet-500/30"}`}>
                  {connected.has(p) ? "✓ Connected" : p === "linkedin" ? "Not connected" : "Demo mode"}
                </div>
              </Tilt>
            );
          })}
        </div>
        {!connected.has("linkedin") && (
          <p className="mt-3 text-sm text-neutral-400">
            👉 First step: <Link href="/settings" className="font-semibold text-[#39ff14] hover:underline">connect your LinkedIn</Link> — takes about 30 seconds.
          </p>
        )}
      </section>

      {notifs.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-neutral-400">Notifications</h2>
          <div className="space-y-2">
            {notifs.map((n) => (
              <div key={n.id} className="card !p-4 flex items-center justify-between gap-4">
                <div className="text-sm">
                  <span className="font-semibold capitalize text-white">{n.type.replaceAll("_", " ")}</span>
                  <span className="ml-2 text-neutral-400">
                    {n.payload?.platform ?? ""} {n.payload?.error ? `— ${String(n.payload.error).slice(0, 80)}` : ""}
                    {n.payload?.url ? <a className="ml-1 font-semibold text-[#39ff14] underline" href={n.payload.url} target="_blank">view post</a> : null}
                  </span>
                </div>
                <button className="btn-ghost !px-3 !py-1 text-xs shrink-0"
                        onClick={() => api.post(`/notifications/${n.id}/read`).then(() => setNotifs(notifs.filter(x => x.id !== n.id)))}>
                  Dismiss
                </button>
              </div>
            ))}
          </div>
        </section>
      )}

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-bold uppercase tracking-wide text-neutral-400">Recent activity</h2>
          <Link href="/history" className="text-sm font-semibold text-[#39ff14] hover:underline">All history →</Link>
        </div>
        {recent.length === 0 ? (
          <div className="card text-center text-sm text-neutral-400">
            <p className="text-3xl">🚀</p>
            <p className="mt-2">Nothing here yet — your first post is one click away.</p>
            <Link href="/create" className="btn mt-4 !px-6 !py-2 text-xs">Create it now</Link>
          </div>
        ) : (
          <div className="space-y-2">
            {recent.map((t) => (
              <Link key={t.id} href={`/status/${t.post_draft_id}`}
                    className="card !p-4 flex items-center justify-between gap-4 text-sm hover:border-[#39ff14]/40">
                <span className="flex items-center gap-2 font-semibold text-white">
                  <span className={`h-2.5 w-2.5 rounded-full ${meta(t.platform).dot}`} />
                  {meta(t.platform).label}
                </span>
                <span className="max-w-[45%] truncate text-neutral-400">{t.caption}</span>
                <StatusBadge status={t.status} />
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
