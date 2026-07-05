"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "../lib/api";

const links = [
  { href: "/", label: "Dashboard" },
  { href: "/create", label: "Create" },
  { href: "/history", label: "History" },
  { href: "/settings", label: "Settings" },
];

export default function Nav() {
  const pathname = usePathname();
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);
  const authPage = pathname === "/login" || pathname === "/register";

  useEffect(() => {
    if (authPage) return;
    api.get("/auth/me").then((u) => setEmail(u.email)).catch(() => router.push("/login"));
  }, [pathname, authPage, router]);

  if (authPage) return null;

  return (
    <header className="sticky top-0 z-20 border-b border-neutral-800 bg-black/80 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3.5">
        <div className="flex items-center gap-8">
          <Link href="/" className="flex items-center gap-2.5 text-sm font-bold tracking-tight text-white">
            <span className="logo-pulse inline-block h-3.5 w-3.5 rounded-full bg-[#39ff14]" />
            Social&nbsp;Poster
          </Link>
          <nav className="flex gap-1">
            {links.map((l) => (
              <Link key={l.href} href={l.href}
                className={`rounded-full px-4 py-1.5 text-sm font-semibold transition ${
                  pathname === l.href
                    ? "bg-[#39ff14] text-black shadow-[0_0_16px_rgba(57,255,20,0.5)]"
                    : "text-neutral-400 hover:bg-neutral-800 hover:text-white"}`}>
                {l.label}
              </Link>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-3">
          {email && (
            <span className="hidden rounded-full bg-neutral-800 px-3 py-1 text-xs font-medium text-[#39ff14] md:inline">
              {email}
            </span>
          )}
          {email && (
            <button className="btn-ghost !px-3 !py-1.5 text-xs"
              onClick={async () => { await api.post("/auth/logout"); router.push("/login"); }}>
              Sign out
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
