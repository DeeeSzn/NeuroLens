"use client";

import { REGION_COLORS, REGION_LABELS, REGIONS, modalityLabel } from "@/lib/constants";

interface RegionLegendProps {
  /** Subset of regions to show; defaults to every region. */
  regions?: readonly string[];
  className?: string;
}

/**
 * The shared colour key for brain regions. Every chart that plots per-region
 * series renders this so the reader never has to guess what a colour means.
 */
export default function RegionLegend({
  regions = REGIONS,
  className = "",
}: RegionLegendProps) {
  return (
    <ul className={`flex flex-wrap items-center gap-x-3 gap-y-1.5 ${className}`}>
      {regions.map((r) => (
        <li
          key={r}
          className="flex items-center gap-1.5"
          title={`${REGION_LABELS[r]} — driven by ${modalityLabel(r)}`}
        >
          <span
            aria-hidden
            className="h-2 w-2 flex-shrink-0 rounded-full"
            style={{ backgroundColor: REGION_COLORS[r] }}
          />
          <span className="text-[11px] leading-none text-muted">
            {REGION_LABELS[r]}
          </span>
        </li>
      ))}
    </ul>
  );
}
