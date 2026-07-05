"use client";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { api, errText } from "../../lib/api";
import { meta } from "../../lib/platforms";

type LiConfig = { redirect_uri: string; client_id_configured: boolean; secret_configured: boolean };

// mirror of the server-side exclusion rules (server re-checks everything)
const EXCLUDED_DIRS = new Set([".git", "node_modules", ".next", "__pycache__", ".venv", "venv",
  "data", "storage", ".pytest_cache", ".mypy_cache", ".claude", "dist", "build", "out"]);
const MAX_FILE = 5 * 1024 * 1024;

// href allowlist: only ever link to real GitHub URLs (blocks javascript: & friends).
// The URL is parsed and REBUILT from validated parts — the raw input never reaches href.
function ghUrl(u: unknown): string {
  if (typeof u !== "string") return "";
  try {
    const parsed = new URL(u);
    if (parsed.protocol !== "https:" || parsed.hostname !== "github.com") return "";
    return "https://github.com" + encodeURI(decodeURI(parsed.pathname));
  } catch {
    return "";
  }
}

function excludedReason(path: string, size: number): string | null {
  const parts = path.split("/");
  const name = parts[parts.length - 1];
  if (parts.slice(0, -1).some((p) => EXCLUDED_DIRS.has(p))) return "folder excluded";
  if (name.startsWith(".env")) return "secret file";
  if ([".pyc", ".log", ".sqlite", ".db", ".DS_Store", ".tsbuildinfo"].some((s) => name.endsWith(s))) return "temp file";
  if (size > MAX_FILE) return "too large";
  return null;
}

function SettingsInner() {
  const params = useSearchParams();
  const folderRef = useRef<HTMLInputElement>(null);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [cfg, setCfg] = useState<LiConfig | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  // github state
  const [ghToken, setGhToken] = useState("");
  const [ghBusy, setGhBusy] = useState(false);
  const [repoName, setRepoName] = useState("social-posting-automation");
  const [privateRepo, setPrivateRepo] = useState(true);
  const [folder, setFolder] = useState<{ files: File[]; paths: string[]; skipped: number } | null>(null);
  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadResult, setUploadResult] = useState<any>(null);

  const connected = params.get("connected");
  const oauthError = params.get("error");

  const load = () => api.get("/connected-accounts").then(setAccounts).catch(() => {});
  useEffect(() => {
    load();
    api.get("/oauth/linkedin/config").then(setCfg).catch(() => {});
  }, []);

  async function connectLinkedIn() {
    setError("");
    try {
      const { authorize_url } = await api.post("/oauth/linkedin/start");
      window.location.href = authorize_url;
    } catch (e) { setError(errText(e)); }
  }

  async function disconnect(id: string) {
    await api.del(`/connected-accounts/${id}`);
    load();
  }

  async function connectGitHub() {
    setGhBusy(true); setError("");
    try {
      await api.post("/github/token", { token: ghToken });
      setGhToken("");
      load();
    } catch (e) { setError(errText(e)); } finally { setGhBusy(false); }
  }

  function pickFolder(list: FileList | null) {
    if (!list || list.length === 0) return;
    const files: File[] = []; const paths: string[] = []; let skipped = 0;
    for (const f of [...list]) {
      const rel = (f as any).webkitRelativePath || f.name;
      if (excludedReason(rel, f.size)) { skipped++; continue; }
      files.push(f); paths.push(rel);
    }
    setFolder({ files, paths, skipped });
    setUploadResult(null);
  }

  async function uploadFolder() {
    if (!folder) return;
    if (folder.files.length === 0) { setError("Everything was filtered out — nothing to upload"); return; }
    if (folder.files.length > 400) { setError("More than 400 files after filtering — trim the folder"); return; }
    setUploadBusy(true); setError(""); setUploadResult(null);
    try {
      const fd = new FormData();
      fd.append("repo", repoName);
      fd.append("private", String(privateRepo));
      fd.append("commit_message", "Upload via Social Poster");
      fd.append("paths", JSON.stringify(folder.paths));
      for (const f of folder.files) fd.append("files", f, f.name);
      const res = await fetch("/api/v1/github/upload", { method: "POST", credentials: "include", body: fd });
      const body = await res.json();
      if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail));
      setUploadResult(body);
      setFolder(null);
    } catch (e) { setError(e instanceof Error ? e.message : "upload failed"); }
    finally { setUploadBusy(false); }
  }

  const linkedin = accounts.find((a) => a.platform === "linkedin");
  const github = accounts.find((a) => a.platform === "github" && a.status === "active");
  const li = meta("linkedin");
  const gh = meta("github");
  const linkedinActive = linkedin?.status === "active";
  const links = {
    linkedin: process.env.NEXT_PUBLIC_LINKEDIN_URL || "",
    youtube: process.env.NEXT_PUBLIC_YOUTUBE_URL || "",
    github: ghUrl(uploadResult?.repo_url) || ghUrl(process.env.NEXT_PUBLIC_GITHUB_REPO_URL) || "",
  };

  return (
    <div className="space-y-8">
      <div className="animate-pop">
        <h1 className="text-3xl font-extrabold tracking-tight text-white">Settings</h1>
        <p className="mt-1 text-sm text-neutral-400">Connected accounts, project upload, and links.</p>
      </div>

      {connected && (
        <div className="card !p-4 flex items-center gap-3 border-[#39ff14]/40 bg-[#39ff14]/10 text-sm font-semibold text-[#39ff14] animate-pop">
          <span className="text-lg">🎉</span> {connected} connected — you're ready to post!
        </div>
      )}
      {oauthError && (
        <div className="card !p-4 border-rose-500/40 bg-rose-500/10 text-sm font-medium text-rose-300 animate-pop">
          Connection failed: {oauthError}. Check the setup checklist below, then try again.
        </div>
      )}
      {error && (
        <div className="card !p-4 border-rose-500/40 bg-rose-500/10 text-sm font-medium text-rose-300 animate-pop">{error}</div>
      )}

      <section className="space-y-4">
        {/* -------- LinkedIn -------- */}
        <div className={`card flex flex-wrap items-center justify-between gap-4 animate-pop stagger-1 ${li.ring}`}>
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#0A66C2]/15 text-xl">{li.emoji}</span>
            <div>
              <h2 className="font-bold text-white">LinkedIn</h2>
              {linkedin ? (
                <p className="text-sm text-neutral-400">
                  {linkedin.account_name} · <span className="capitalize">{linkedin.status}</span>
                  {linkedin.token_expires_at && ` · token expires ${new Date(linkedin.token_expires_at).toLocaleDateString()}`}
                </p>
              ) : (
                <p className="text-sm text-neutral-400">Post to your personal profile via the official Posts API.</p>
              )}
            </div>
          </div>
          {linkedin ? (
            <div className="flex gap-2">
              {linkedin.status !== "active" && <button className="btn" onClick={connectLinkedIn}>Reconnect</button>}
              <button className="btn-ghost" onClick={() => disconnect(linkedin.id)}>Disconnect</button>
            </div>
          ) : (
            <button className="btn" onClick={connectLinkedIn}>Connect</button>
          )}
        </div>

        {!linkedinActive && cfg && (
          <div className="card space-y-3 border-[#39ff14]/25 animate-pop">
            <h3 className="flex items-center gap-2 text-sm font-bold text-white">🧭 LinkedIn setup checklist</h3>
            <ol className="list-decimal space-y-2 pl-5 text-sm text-neutral-300">
              <li>
                In your LinkedIn app (developer.linkedin.com → <em>Auth</em> tab), register this exact redirect URL
                <div className="mt-2 flex items-center gap-2">
                  <code className="code-chip">{cfg.redirect_uri}</code>
                  <button className="btn-ghost !px-3 !py-1.5 text-xs shrink-0"
                          onClick={() => { navigator.clipboard.writeText(cfg.redirect_uri); setCopied(true); setTimeout(() => setCopied(false), 2000); }}>
                    {copied ? "✓ Copied" : "Copy"}
                  </button>
                </div>
                <span className="mt-1 block text-xs text-neutral-500">Character-for-character: no trailing slash, http not https. Click <em>Update</em> after adding it.</span>
              </li>
              <li>Products tab: add <strong>"Sign In with LinkedIn using OpenID Connect"</strong> and <strong>"Share on LinkedIn"</strong>.</li>
              <li>
                Credentials in <code className="rounded bg-black/60 px-1.5 py-0.5 font-mono text-xs text-[#39ff14]">apps/api/.env</code>:
                Client ID {cfg.client_id_configured ? <span className="text-[#39ff14]">✓ loaded</span> : <span className="text-rose-400">✗ missing</span>} ·
                Secret {cfg.secret_configured ? <span className="text-[#39ff14]">✓ loaded</span> : <span className="text-rose-400">✗ missing</span>}
              </li>
            </ol>
          </div>
        )}

        {/* -------- GitHub -------- */}
        <div className={`card space-y-4 animate-pop stagger-2 ${gh.ring}`}>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white/10 text-xl">{gh.emoji}</span>
              <div>
                <h2 className="font-bold text-white">GitHub</h2>
                {github ? (
                  <p className="text-sm text-neutral-400">@{github.external_account_id} · connected with API token</p>
                ) : (
                  <p className="text-sm text-neutral-400">Connect with an API token to upload your project — secrets & junk are filtered automatically.</p>
                )}
              </div>
            </div>
            {github && <button className="btn-ghost" onClick={() => disconnect(github.id)}>Disconnect</button>}
          </div>

          {!github ? (
            <div className="space-y-2 rounded-xl bg-black/40 p-4 ring-1 ring-neutral-800">
              <label className="label">GitHub API token (fine-grained, with repo read/write)</label>
              <div className="flex flex-wrap gap-2">
                <input className="input !w-auto flex-1" type="password" placeholder="github_pat_… or ghp_…"
                       value={ghToken} onChange={(e) => setGhToken(e.target.value)} />
                <button className="btn" disabled={ghBusy || ghToken.length < 20} onClick={connectGitHub}>
                  {ghBusy ? <><span className="spinner" /> Checking…</> : "Connect"}
                </button>
              </div>
              <p className="text-xs text-neutral-500">
                Create one at github.com → Settings → Developer settings → Personal access tokens.
                Stored AES-256-GCM encrypted, never shown again, never sent to the browser.
              </p>
            </div>
          ) : (
            <div className="space-y-3 rounded-xl bg-black/40 p-4 ring-1 ring-neutral-800">
              <h3 className="text-sm font-bold text-white">📦 Upload project folder</h3>
              <div className="flex flex-wrap items-center gap-3">
                <input className="input !w-auto" value={repoName} onChange={(e) => setRepoName(e.target.value)}
                       placeholder="repo-name" />
                <label className="flex items-center gap-2 text-sm text-neutral-300">
                  <input type="checkbox" checked={privateRepo} onChange={(e) => setPrivateRepo(e.target.checked)}
                         className="h-4 w-4 accent-[#39ff14]" />
                  Private repo
                </label>
                <button className="btn-ghost" onClick={() => folderRef.current?.click()}>📁 Choose folder</button>
                <input ref={folderRef} type="file" hidden multiple
                       {...({ webkitdirectory: "", directory: "" } as any)}
                       onChange={(e) => pickFolder(e.target.files)} />
              </div>
              {folder && (
                <div className="thumb-pop rounded-lg bg-neutral-900 px-3 py-2 text-sm text-neutral-300 ring-1 ring-neutral-700">
                  ✅ {folder.files.length} files ready · 🧹 {folder.skipped} filtered out (node_modules, .env, caches, builds…)
                </div>
              )}
              <button className="btn" disabled={!folder || uploadBusy} onClick={uploadFolder}>
                {uploadBusy ? <><span className="spinner" /> Uploading to GitHub…</> : "🚀 Upload to GitHub"}
              </button>
              {uploadBusy && <div className="progress-bar" />}
              {uploadResult && (
                <div className="animate-pop rounded-lg bg-[#39ff14]/10 px-3 py-2 text-sm font-semibold text-[#39ff14] ring-1 ring-[#39ff14]/25">
                  🎉 {uploadResult.files_uploaded} files pushed to{" "}
                  {ghUrl(uploadResult.repo_url)
                    ? <a className="underline" href={ghUrl(uploadResult.repo_url)} target="_blank" rel="noopener noreferrer">{ghUrl(uploadResult.repo_url)}</a>
                    : <span>your repo</span>}
                  {uploadResult.skipped?.length > 0 && ` · ${uploadResult.skipped.length} more filtered server-side`}
                </div>
              )}
            </div>
          )}
        </div>

        {/* -------- YouTube -------- */}
        {["facebook", "twitter", "youtube"].map((p) => {
          const m = meta(p);
          return (
            <div key={p} className={`card flex items-center justify-between gap-4 animate-pop stagger-3 ${m.ring}`}>
              <div className="flex items-center gap-3">
                <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-neutral-800 text-xl">{m.emoji}</span>
                <div>
                  <h2 className="font-bold text-white">{m.label}</h2>
                  <p className="text-sm text-neutral-400">Demo mode — publishing is simulated end-to-end. Real integration is the next milestone.</p>
                </div>
              </div>
              <span className="badge bg-violet-500/15 text-violet-300 ring-1 ring-violet-500/30">Demo</span>
            </div>
          );
        })}
      </section>

      {/* -------- links -------- */}
      <section className="card animate-pop stagger-4">
        <h3 className="mb-3 text-sm font-bold text-white">🔗 Your links</h3>
        <div className="flex flex-wrap gap-3">
          {links.github
            ? <a className="btn-ghost !py-2 text-sm" href={links.github} target="_blank" rel="noopener noreferrer">🐙 Project on GitHub</a>
            : <span className="btn-ghost !py-2 text-sm opacity-50 cursor-default">🐙 GitHub — upload above to get a link</span>}
          {links.linkedin
            ? <a className="btn-ghost !py-2 text-sm" href={links.linkedin} target="_blank">💼 LinkedIn profile</a>
            : <span className="btn-ghost !py-2 text-sm opacity-50 cursor-default">💼 LinkedIn — set NEXT_PUBLIC_LINKEDIN_URL</span>}
          {links.youtube
            ? <a className="btn-ghost !py-2 text-sm" href={links.youtube} target="_blank">▶️ YouTube channel</a>
            : <span className="btn-ghost !py-2 text-sm opacity-50 cursor-default">▶️ YouTube — set NEXT_PUBLIC_YOUTUBE_URL</span>}
        </div>
      </section>

      <section className="card text-xs leading-relaxed text-neutral-400">
        <p className="mb-1 font-bold text-neutral-200">🔒 Security notes</p>
        OAuth tokens and API keys are encrypted (AES-256-GCM) before storage and never sent to the browser.
        GitHub uploads always exclude .env files, dependency folders, caches, and databases — filtered in your
        browser for speed and re-checked on the server for trust. All actions land in the audit log.
      </section>
    </div>
  );
}

export default function Settings() {
  return <Suspense><SettingsInner /></Suspense>;
}
