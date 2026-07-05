"use client";
/**
 * Playful interaction kit — patterns adapted from award-winning sites
 * (cursor-reactive glow, 3D tilt cards, magnetic buttons à la Linear/Rive/Lusion).
 * Dependency-free, GPU-friendly transforms only, and fully disabled when the
 * user prefers reduced motion.
 */
import { useCallback, useEffect, useRef, useState } from "react";

export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const fn = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener("change", fn);
    return () => mq.removeEventListener("change", fn);
  }, []);
  return reduced;
}

/** Soft neon glow that follows the cursor across the whole page. */
export function Spotlight() {
  const ref = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  useEffect(() => {
    if (reduced) return;
    let raf = 0;
    const move = (e: MouseEvent) => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        ref.current?.style.setProperty("--spot-x", `${e.clientX}px`);
        ref.current?.style.setProperty("--spot-y", `${e.clientY}px`);
      });
    };
    window.addEventListener("mousemove", move);
    return () => { window.removeEventListener("mousemove", move); cancelAnimationFrame(raf); };
  }, [reduced]);
  if (reduced) return null;
  return <div ref={ref} className="spotlight" aria-hidden />;
}

/** 3D tilt on hover — cards lean toward the cursor. */
export function Tilt({ children, max = 8, className = "" }:
  { children: React.ReactNode; max?: number; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();

  const onMove = useCallback((e: React.MouseEvent) => {
    const el = ref.current;
    if (!el || reduced) return;
    const r = el.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width - 0.5;
    const py = (e.clientY - r.top) / r.height - 0.5;
    el.style.transform = `perspective(700px) rotateY(${px * max}deg) rotateX(${-py * max}deg) translateZ(0)`;
  }, [max, reduced]);

  const onLeave = useCallback(() => {
    if (ref.current) ref.current.style.transform = "perspective(700px) rotateY(0) rotateX(0)";
  }, []);

  return (
    <div ref={ref} className={`tilt ${className}`} onMouseMove={onMove} onMouseLeave={onLeave}>
      {children}
    </div>
  );
}

/** Buttons that gently pull toward the cursor. */
export function Magnetic({ children, strength = 10 }:
  { children: React.ReactNode; strength?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const reduced = useReducedMotion();

  const onMove = useCallback((e: React.MouseEvent) => {
    const el = ref.current;
    if (!el || reduced) return;
    const r = el.getBoundingClientRect();
    const x = ((e.clientX - r.left) / r.width - 0.5) * strength;
    const y = ((e.clientY - r.top) / r.height - 0.5) * strength;
    el.style.transform = `translate(${x}px, ${y}px)`;
  }, [strength, reduced]);

  const onLeave = useCallback(() => {
    if (ref.current) ref.current.style.transform = "translate(0, 0)";
  }, []);

  return (
    <span ref={ref} className="magnetic" onMouseMove={onMove} onMouseLeave={onLeave}>
      {children}
    </span>
  );
}

/** One-shot emoji burst (e.g. when a post goes live). */
export function EmojiBurst({ emojis = ["🎉", "⚡", "🚀", "✨", "💚"] }: { emojis?: string[] }) {
  const reduced = useReducedMotion();
  if (reduced) return null;
  const parts = Array.from({ length: 14 }, (_, i) => ({
    e: emojis[i % emojis.length],
    left: `${8 + ((i * 61) % 84)}%`,
    delay: `${(i % 7) * 0.1}s`,
    duration: `${1.6 + (i % 4) * 0.35}s`,
  }));
  return (
    <>
      {parts.map((p, i) => (
        <span key={i} className="emoji-burst" style={{ left: p.left, animationDelay: p.delay, animationDuration: p.duration }}>
          {p.e}
        </span>
      ))}
    </>
  );
}
