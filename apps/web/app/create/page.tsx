"use client";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api, errText } from "../../lib/api";
import { Magnetic } from "../../components/Fx";
import { meta } from "../../lib/platforms";

type PlatformInfo = { platform: string; mode: "real" | "mock"; limits: { caption_max: number; photos_max?: number } };
type Uploaded = { id: string; mime_type: string; original_name: string; bytes: number; exif_stripped?: boolean };

export default function CreatePost() {
  const router = useRouter();
  const photoRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLInputElement>(null);
  const [platforms, setPlatforms] = useState<PlatformInfo[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set(["linkedin"]));
  const [master, setMaster] = useState("");
  const [captions, setCaptions] = useState<Record<string, { caption: string; title: string }>>({});
  const [photos, setPhotos] = useState<Uploaded[]>([]);
  const [video, setVideo] = useState<Uploaded | null>(null);
  const [uploading, setUploading] = useState(0);       // number of in-flight uploads
  const [dragOver, setDragOver] = useState<"photo" | "video" | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [launching, setLaunching] = useState(false);
  const [scheduleAt, setScheduleAt] = useState("");

  useEffect(() => { api.get("/platforms").then(setPlatforms).catch(() => {}); }, []);

  function toggle(p: string) {
    const next = new Set(selected);
    next.has(p) ? next.delete(p) : next.add(p);
    setSelected(next);
  }

  async function addPhotos(list: FileList | File[] | null | undefined) {
    if (!list) return;
    const files = [...list].filter((f) => ["image/jpeg", "image/png"].includes(f.type));
    if (files.length === 0) { setError("Photos must be JPG or PNG 🙂"); return; }
    if (photos.length + files.length > 9) { setError("Up to 9 photos per post"); return; }
    setError("");
    setUploading((n) => n + files.length);
    for (const f of files) {
      try { const up = await api.upload(f); setPhotos((prev) => [...prev, up]); }
      catch (e) { setError(errText(e)); }
      finally { setUploading((n) => n - 1); }
    }
  }

  async function setVideoFile(f: File | null | undefined) {
    if (!f) return;
    if (f.type !== "video/mp4") { setError("Video must be MP4 🙂"); return; }
    setError("");
    setUploading((n) => n + 1);
    try { setVideo(await api.upload(f)); }
    catch (e) { setError(errText(e)); }
    finally { setUploading((n) => n - 1); }
  }

  async function generate() {
    setError("");
    try {
      const res = await api.post("/captions/generate", { master_caption: master, platforms: [...selected] });
      setCaptions((prev) => ({ ...prev, ...res }));
    } catch (e) { setError(errText(e)); }
  }

  async function submit(now: boolean) {
    if (selected.size === 0) { setError("Pick at least one platform below 🙂"); return; }
    setBusy(true); setError("");
    if (now) setLaunching(true);
    const t0 = Date.now();
    try {
      const draft = await api.post("/posts", {
        master_caption: master,
        media_asset_ids: photos.map((p) => p.id),
        video_asset_id: video?.id ?? null,
        platforms: [...selected],
      });
      for (const t of draft.targets) {
        const edit = captions[t.platform];
        if (edit && (edit.caption !== t.caption || edit.title !== t.title)) {
          await api.patch(`/posts/targets/${t.id}`, { caption: edit.caption, title: edit.title });
        }
      }
      const body: any = {};
      if (!now) {
        if (!scheduleAt) { setError("Pick a date & time for the schedule 🙂"); setBusy(false); setLaunching(false); return; }
        body.schedule_at = new Date(scheduleAt).toISOString();
        body.timezone_name = Intl.DateTimeFormat().resolvedOptions().timeZone;
      }
      const key = (crypto as any).randomUUID ? crypto.randomUUID() : String(Date.now());
      await api.post(`/posts/${draft.id}/publish`, body, { "Idempotency-Key": key });
      if (now) {
        const wait = Math.max(0, 1400 - (Date.now() - t0));   // let the rocket fly 🚀
        setTimeout(() => router.push(`/status/${draft.id}`), wait);
      } else {
        router.push("/history");
      }
    } catch (e) { setError(errText(e)); setLaunching(false); setBusy(false); }
  }

  const previews = [...selected];

  return (
    <div className="space-y-8">
      {launching && (
        <div className="launch-overlay">
          <div className="launch-rocket">🚀</div>
          <p className="launch-text">Launching your post…</p>
        </div>
      )}

      <div className="animate-pop">
        <h1 className="text-3xl font-extrabold tracking-tight text-white">
          Create a <span className="neon-text">post</span>
        </h1>
        <p className="mt-1 text-sm text-neutral-400">Four easy steps — you'll be live in under a minute.</p>
      </div>

      {/* step 1: photos + video, separate sections */}
      <section className="space-y-3 animate-pop stagger-1">
        <div className="flex items-center gap-3">
          <span className="step">1</span>
          <h2 className="font-bold text-white">Add your media <span className="ml-1 text-sm font-normal text-neutral-500">(optional for text posts)</span></h2>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          {/* photos */}
          <div
            className={`card cursor-pointer border-2 border-dashed text-center transition ${
              dragOver === "photo" ? "border-[#39ff14] bg-[#39ff14]/5 scale-[1.01]" : "border-neutral-700 hover:border-[#39ff14]/50"}`}
            onClick={() => photoRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragOver("photo"); }}
            onDragLeave={() => setDragOver(null)}
            onDrop={(e) => { e.preventDefault(); setDragOver(null); addPhotos(e.dataTransfer.files); }}
          >
            <input ref={photoRef} type="file" accept="image/jpeg,image/png" multiple hidden
                   onChange={(e) => { addPhotos(e.target.files); e.target.value = ""; }} />
            <p className="text-3xl">📸</p>
            <p className="mt-2 text-sm font-bold text-white">Photos</p>
            <p className="mt-1 text-xs text-neutral-500">JPG / PNG · up to 9 · drop several at once</p>
            {photos.length > 0 && (
              <div className="mt-4 grid grid-cols-3 gap-2">
                {photos.map((p, i) => (
                  <div key={p.id} className="thumb-pop group relative" style={{ animationDelay: `${i * 60}ms` }}>
                    <img src={`/api/v1/media/${encodeURIComponent(p.id)}/file`} alt=""
                         className="h-20 w-full rounded-lg object-cover ring-1 ring-neutral-700" />
                    <button
                      className="absolute -right-1.5 -top-1.5 hidden h-5 w-5 items-center justify-center rounded-full bg-rose-500 text-xs font-bold text-white group-hover:flex"
                      onClick={(e) => { e.stopPropagation(); setPhotos(photos.filter((x) => x.id !== p.id)); }}>
                      ×
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* video */}
          <div
            className={`card cursor-pointer border-2 border-dashed text-center transition ${
              dragOver === "video" ? "border-[#39ff14] bg-[#39ff14]/5 scale-[1.01]" : "border-neutral-700 hover:border-[#39ff14]/50"}`}
            onClick={() => videoRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragOver("video"); }}
            onDragLeave={() => setDragOver(null)}
            onDrop={(e) => { e.preventDefault(); setDragOver(null); setVideoFile(e.dataTransfer.files?.[0]); }}
          >
            <input ref={videoRef} type="file" accept="video/mp4" hidden
                   onChange={(e) => { setVideoFile(e.target.files?.[0]); e.target.value = ""; }} />
            <p className="text-3xl">🎬</p>
            <p className="mt-2 text-sm font-bold text-white">Video</p>
            <p className="mt-1 text-xs text-neutral-500">MP4 · one per post (YouTube needs this)</p>
            {video && (
              <div className="thumb-pop mt-4 flex items-center justify-between rounded-lg bg-black/50 px-3 py-2 ring-1 ring-neutral-700">
                <span className="truncate text-xs text-neutral-300">🎬 {video.original_name} · {(video.bytes / 1024 / 1024).toFixed(1)} MB</span>
                <button className="ml-2 text-xs font-bold text-rose-400"
                        onClick={(e) => { e.stopPropagation(); setVideo(null); }}>remove</button>
              </div>
            )}
          </div>
        </div>
        {uploading > 0 && (
          <p className="flex items-center gap-2 text-sm text-[#39ff14]">
            <span className="spinner" /> Uploading {uploading} file{uploading > 1 ? "s" : ""}…
          </p>
        )}
      </section>

      {/* step 2 */}
      <section className="space-y-3 animate-pop stagger-2">
        <div className="flex items-center gap-3">
          <span className="step">2</span>
          <h2 className="font-bold text-white">Write it once, pick your platforms</h2>
        </div>
        <div className="card space-y-4">
          <textarea className="input min-h-28" value={master} onChange={(e) => setMaster(e.target.value)}
                    placeholder="What do you want the world to know? Write it once — we'll shape it for each platform. ✨" />
          <div className="flex flex-wrap items-center gap-3">
            {platforms.map((p) => {
              const m = meta(p.platform);
              const on = selected.has(p.platform);
              return (
                <button key={p.platform} onClick={() => toggle(p.platform)}
                  className={`hover-wiggle rounded-full border px-4 py-2 text-sm font-semibold transition active:scale-95 ${on ? m.chip : m.chipIdle}`}>
                  {m.emoji} {m.label}{p.mode === "mock" && <span className="ml-1.5 text-xs opacity-70">(demo)</span>}
                </button>
              );
            })}
            <button className="btn-ghost ml-auto" onClick={generate}>🪄 Generate captions</button>
          </div>
        </div>
      </section>

      {/* step 3 */}
      {previews.length > 0 && (
        <section className="space-y-3 animate-pop stagger-3">
          <div className="flex items-center gap-3">
            <span className="step">3</span>
            <h2 className="font-bold text-white">Make each platform shine <span className="ml-1 text-sm font-normal text-neutral-500">(edit freely)</span></h2>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {previews.map((p) => {
              const info = platforms.find((x) => x.platform === p);
              const m = meta(p);
              const c = captions[p] ?? { caption: master, title: "" };
              const over = info ? c.caption.length > info.limits.caption_max : false;
              return (
                <div key={p} className={`card space-y-3 ${m.ring}`}>
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-2 text-sm font-bold text-white">
                      <span className={`h-2.5 w-2.5 rounded-full ${m.dot}`} /> {m.label}
                    </span>
                    <span className={`text-xs font-semibold ${over ? "text-rose-400" : "text-neutral-500"}`}>
                      {c.caption.length}{info ? ` / ${info.limits.caption_max}` : ""}
                    </span>
                  </div>
                  {p === "youtube" && (
                    <input className="input" placeholder="Video title (required)"
                           value={c.title}
                           onChange={(e) => setCaptions({ ...captions, [p]: { ...c, title: e.target.value } })} />
                  )}
                  <textarea className="input min-h-24" value={c.caption}
                            onChange={(e) => setCaptions({ ...captions, [p]: { ...c, caption: e.target.value } })} />
                </div>
              );
            })}
          </div>
        </section>
      )}

      {error && (
        <div className="card !p-4 border-rose-500/40 bg-rose-500/10 text-sm font-medium text-rose-300 whitespace-pre-wrap animate-pop">{error}</div>
      )}

      {/* step 4 */}
      <section className="space-y-3 animate-pop stagger-4">
        <div className="flex items-center gap-3">
          <span className="step">4</span>
          <h2 className="font-bold text-white">Launch 🚀</h2>
        </div>
        <div className="card flex flex-wrap items-center gap-4">
          <Magnetic strength={14}>
            <button className="btn !px-8" disabled={busy || uploading > 0} onClick={() => submit(true)}>
              {busy ? <><span className="spinner" /> Working…</> : "⚡ Post now"}
            </button>
          </Magnetic>
          <div className="flex items-center gap-2">
            <input type="datetime-local" className="input !w-auto" value={scheduleAt}
                   onChange={(e) => setScheduleAt(e.target.value)} />
            <button className="btn-ghost" disabled={busy || uploading > 0 || !scheduleAt} onClick={() => submit(false)}>
              🕐 Schedule instead
            </button>
          </div>
          <p className="ml-auto text-xs text-neutral-500">Post now = instantly live. Schedule = we handle it while you sleep.</p>
        </div>
      </section>
    </div>
  );
}
