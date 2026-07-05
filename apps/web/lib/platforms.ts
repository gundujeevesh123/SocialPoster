// Platform identity — brand colors as full literal Tailwind classes (JIT-scannable).
export type PlatformMeta = {
  label: string;
  dot: string;
  chip: string;
  chipIdle: string;
  ring: string;
  emoji: string;
};

export const PLATFORMS: Record<string, PlatformMeta> = {
  linkedin: {
    label: "LinkedIn",
    dot: "bg-[#0A66C2] shadow-[0_0_8px_rgba(10,102,194,0.8)]",
    chip: "bg-[#0A66C2] border-[#0A66C2] text-white shadow-[0_0_18px_rgba(10,102,194,0.45)]",
    chipIdle: "border-neutral-700 text-neutral-300 hover:border-[#0A66C2] hover:text-[#5eb1ff] hover:bg-[#0A66C2]/10",
    ring: "border-t-4 border-t-[#0A66C2]",
    emoji: "💼",
  },
  facebook: {
    label: "Facebook",
    dot: "bg-[#1877F2] shadow-[0_0_8px_rgba(24,119,242,0.8)]",
    chip: "bg-[#1877F2] border-[#1877F2] text-white shadow-[0_0_18px_rgba(24,119,242,0.45)]",
    chipIdle: "border-neutral-700 text-neutral-300 hover:border-[#1877F2] hover:text-[#6db1ff] hover:bg-[#1877F2]/10",
    ring: "border-t-4 border-t-[#1877F2]",
    emoji: "👥",
  },
  twitter: {
    label: "Twitter",
    dot: "bg-[#1DA1F2] shadow-[0_0_8px_rgba(29,161,242,0.8)]",
    chip: "bg-[#1DA1F2] border-[#1DA1F2] text-white shadow-[0_0_18px_rgba(29,161,242,0.45)]",
    chipIdle: "border-neutral-700 text-neutral-300 hover:border-[#1DA1F2] hover:text-[#6cc4ff] hover:bg-[#1DA1F2]/10",
    ring: "border-t-4 border-t-[#1DA1F2]",
    emoji: "🐦",
  },
  github: {
    label: "GitHub",
    dot: "bg-white shadow-[0_0_8px_rgba(255,255,255,0.8)]",
    chip: "bg-white border-white text-black shadow-[0_0_18px_rgba(255,255,255,0.4)]",
    chipIdle: "border-neutral-700 text-neutral-300 hover:border-white hover:text-white hover:bg-white/10",
    ring: "border-t-4 border-t-white",
    emoji: "🐙",
  },
  youtube: {
    label: "YouTube",
    dot: "bg-[#FF0000] shadow-[0_0_8px_rgba(255,0,0,0.8)]",
    chip: "bg-[#FF0000] border-[#FF0000] text-white shadow-[0_0_18px_rgba(255,0,0,0.45)]",
    chipIdle: "border-neutral-700 text-neutral-300 hover:border-[#FF0000] hover:text-[#ff6b6b] hover:bg-[#FF0000]/10",
    ring: "border-t-4 border-t-[#FF0000]",
    emoji: "▶️",
  },
};

export const PLATFORM_ORDER = ["linkedin", "facebook", "twitter", "youtube"];

export function meta(p: string): PlatformMeta {
  return PLATFORMS[p] ?? {
    label: p, dot: "bg-neutral-500", chip: "bg-neutral-200 border-neutral-200 text-black",
    chipIdle: "border-neutral-700 text-neutral-300", ring: "border-t-4 border-t-neutral-500", emoji: "✨",
  };
}
