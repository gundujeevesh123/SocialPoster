"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, errText } from "../../lib/api";

export default function Register() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      await api.post("/auth/register", { email, password });
      router.push("/");
    } catch (err) { setError(errText(err)); } finally { setBusy(false); }
  }

  return (
    <div className="mx-auto mt-16 max-w-sm">
      <div className="mb-8 text-center">
        <span className="mx-auto mb-4 block h-12 w-12 rounded-2xl bg-[#39ff14] shadow-[0_0_30px_rgba(57,255,20,0.6)]" />
        <h1 className="text-3xl font-extrabold tracking-tight text-white">
          Join <span className="neon-text">Social Poster</span>
        </h1>
        <p className="mt-2 text-sm text-neutral-400">One caption → LinkedIn, Facebook, Instagram & YouTube. 🚀</p>
      </div>
      <form onSubmit={submit} className="card space-y-4">
        <div>
          <label className="label">Email</label>
          <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div>
          <label className="label">Password <span className="normal-case">(min 10 characters)</span></label>
          <input className="input" type="password" minLength={10} value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        {error && <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-sm font-medium text-rose-300 ring-1 ring-rose-500/25">{error}</p>}
        <button className="btn w-full" disabled={busy}>{busy ? "Creating…" : "Create my account"}</button>
        <p className="text-center text-sm text-neutral-400">
          Already have one? <Link className="font-bold text-[#39ff14] hover:underline" href="/login">Sign in</Link>
        </p>
      </form>
    </div>
  );
}
