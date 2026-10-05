"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "motion/react";

const LINKS = [
  { href: "/", label: "Analyze", match: ["/", "/analysis"] },
  { href: "/compare", label: "Compare", match: ["/compare"] },
];

/**
 * Persistent top-left navigation. Sits over the brain canvas on analysis
 * screens and doubles as the page header elsewhere, so every route is
 * reachable from every other route. The active pill slides between links via
 * a shared `layoutId` spring.
 */
export default function AppNav({ className = "" }: { className?: string }) {
  const pathname = usePathname();

  const isActive = (match: string[]) =>
    match.some((m) => (m === "/" ? pathname === "/" : pathname.startsWith(m)));

  return (
    <nav
      aria-label="Primary"
      className={`nl-glass flex flex-shrink-0 items-center gap-1 rounded-full p-1 pl-1.5 ${className}`}
    >
      <Link
        href="/"
        className="group flex items-center gap-2 rounded-full pr-1.5"
        aria-label="NeuroLens home"
      >
        <span
          aria-hidden
          className="relative flex h-6 w-6 flex-shrink-0 items-center justify-center overflow-hidden rounded-md text-[11px] font-bold text-white shadow-[0_2px_10px_-2px_rgba(139,92,255,0.8)]"
          style={{
            background:
              "linear-gradient(135deg, #8b5cff 0%, #4f8dff 60%, #38d0ff 100%)",
          }}
        >
          <span className="relative z-10 font-display">N</span>
          <span className="nl-shimmer absolute inset-0 opacity-60" />
        </span>
        <span className="hidden items-baseline gap-1.5 whitespace-nowrap sm:flex">
          <span className="font-display text-[13px] font-semibold leading-none text-ink transition-colors group-hover:text-white">
            NeuroLens
          </span>
          <span className="text-[10px] font-medium leading-none tracking-wide text-dim">
            TRIBE v2
          </span>
        </span>
      </Link>

      <span aria-hidden className="mx-0.5 h-4 w-px bg-line-strong" />

      {LINKS.map((l) => {
        const active = isActive(l.match);
        return (
          <Link
            key={l.href}
            href={l.href}
            aria-current={active ? "page" : undefined}
            className="relative rounded-full px-3 py-1.5 text-xs font-medium leading-none"
          >
            {active && (
              <motion.span
                layoutId="nav-pill"
                aria-hidden
                className="absolute inset-0 rounded-full bg-surface-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]"
                transition={{ type: "spring", stiffness: 420, damping: 34 }}
              />
            )}
            <span
              className={`relative z-10 transition-colors duration-200 ${
                active ? "text-ink" : "text-dim hover:text-ink"
              }`}
            >
              {l.label}
            </span>
          </Link>
        );
      })}
    </nav>
  );
}
