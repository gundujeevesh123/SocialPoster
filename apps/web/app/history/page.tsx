"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import StatusBadge from "../../components/StatusBadge";
import { PLATFORM_ORDER, meta } from "../../lib/platforms";

export default function History() {
  const [rows, setRows] = useState<any[]>([]);
  const [platform, setPlatform] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    const q = new URLSearchParams();
    if (platform) q.set("platform", platform);
    if (status) q.set("status", status);
    api.get(`/posts?${q}`).then(setRows).catch(() => {});
  }, [platform, status]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-3xl font-extrabold tracking-tight text-white">History</h1>
        <div className="flex gap-2">
          <select className="input !w-auto" value={platform} onChange={(e) => setPlatform(e.target.value)}>
            <option value="">All platforms</option>
            {PLATFORM_ORDER.map((p) => <option key={p} value={p}>{meta(p).label}</option>)}
          </select>
          <select className="input !w-auto" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option>
            {["published", "scheduled", "queued", "publishing", "failed", "requires_action", "draft"].map((s) => <option key={s}>{s}</option>)}
          </select>
        </div>
      </div>

      {rows.length === 0 ? (
        <div className="card text-center text-sm text-neutral-400">
          <p className="text-3xl">🗂️</p>
          <p className="mt-2">Nothing matches these filters — try clearing them, or go make history.</p>
          <Link href="/create" className="btn mt-4 !px-6 !py-2 text-xs">Create a post</Link>
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-neutral-800 bg-neutral-900/80 shadow-lg shadow-black/40">
          <table className="w-full text-sm">
            <thead className="border-b border-neutral-800 bg-black/40 text-left text-xs font-bold uppercase tracking-wide text-neutral-500">
              <tr>
                <th className="px-4 py-3">Platform</th>
                <th className="px-4 py-3">Caption</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Scheduled</th>
                <th className="px-4 py-3">Link</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((t) => (
                <tr key={t.id} className="border-t border-neutral-800/70 transition hover:bg-[#39ff14]/5">
                  <td className="px-4 py-3">
                    <span className="flex items-center gap-2 font-semibold text-white">
                      <span className={`h-2.5 w-2.5 rounded-full ${meta(t.platform).dot}`} />
                      {meta(t.platform).label}
                    </span>
                  </td>
                  <td className="max-w-xs truncate px-4 py-3 text-neutral-400">
                    <Link className="hover:text-[#39ff14] hover:underline" href={`/status/${t.post_draft_id}`}>
                      {t.caption || t.master_caption || "—"}
                    </Link>
                  </td>
                  <td className="px-4 py-3"><StatusBadge status={t.status} /></td>
                  <td className="px-4 py-3 text-neutral-500">{t.scheduled_at ? new Date(t.scheduled_at).toLocaleString() : "—"}</td>
                  <td className="px-4 py-3">
                    {t.job?.external_url
                      ? <a className="font-semibold text-[#39ff14] underline" target="_blank" href={t.job.external_url}>open ↗</a>
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
