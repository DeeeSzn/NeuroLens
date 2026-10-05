"use client";

import { useRef, useId } from "react";
import { motion } from "motion/react";

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
}

interface SegmentedControlProps<T extends string> {
  label: string;
  options: SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  size?: "sm" | "md";
}

/**
 * A real segmented control: `radiogroup` semantics with roving tabindex, so
 * keyboard users get one tab stop and arrow keys to move between options
 * (rather than four separate tab stops like a row of plain buttons). The
 * selected thumb slides between options with a shared-layout spring.
 */
export default function SegmentedControl<T extends string>({
  label,
  options,
  value,
  onChange,
  size = "md",
}: SegmentedControlProps<T>) {
  const groupRef = useRef<HTMLDivElement>(null);
  const layoutId = useId();

  function handleKeyDown(e: React.KeyboardEvent) {
    const i = options.findIndex((o) => o.value === value);
    if (i < 0) return;
    let next = -1;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") {
      next = (i + 1) % options.length;
    } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
      next = (i - 1 + options.length) % options.length;
    }
    if (next < 0) return;
    e.preventDefault();
    onChange(options[next].value);
    const btns = groupRef.current?.querySelectorAll<HTMLButtonElement>(
      '[role="radio"]',
    );
    btns?.[next]?.focus();
  }

  const pad = size === "sm" ? "px-2.5 py-1 text-[11px]" : "px-3 py-1.5 text-xs";

  return (
    <div
      ref={groupRef}
      role="radiogroup"
      aria-label={label}
      onKeyDown={handleKeyDown}
      className="nl-glass inline-flex items-center gap-0.5 rounded-full p-0.5"
    >
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={active}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(o.value)}
            className={`relative rounded-full font-medium leading-none transition-colors duration-200 ${pad} ${
              active ? "text-ink" : "text-dim hover:text-muted"
            }`}
          >
            {active && (
              <motion.span
                layoutId={layoutId}
                aria-hidden
                className="absolute inset-0 rounded-full bg-surface-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]"
                transition={{ type: "spring", stiffness: 480, damping: 36 }}
              />
            )}
            <span className="relative z-10">{o.label}</span>
          </button>
        );
      })}
    </div>
  );
}
