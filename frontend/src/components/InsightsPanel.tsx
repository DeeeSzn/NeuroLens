"use client";

import type { Insight } from "@/lib/api";
import { INSIGHT_TYPE_COLORS, INSIGHT_TYPE_LABELS } from "@/lib/constants";

interface InsightsPanelProps {
  insights: Insight[];
  referenceStatus: "exploratory" | "unavailable";
  onSeek: (timeSec: number) => void;
}

function typeLabel(type: string): string {
  return INSIGHT_TYPE_LABELS[type] ?? type.replace(/_/g, " ");
}

/**
 * The backend description repeats the time window that is already shown in the
 * row header ("Seconds 4.5–6.0: …"). Strip it so the text earns its space.
 */
function stripTimePrefix(desc: string): string {
  return desc.replace(/^\s*Seconds?\s*[\d.]+(?:\s*[–-]\s*[\d.]+)?\s*:\s*/i, "");
}

export default function InsightsPanel({ insights, referenceStatus, onSeek }: InsightsPanelProps) {
  return (
    <section className="nl-card overflow-hidden">
      <div className="nl-card-header">
        <h3 className="text-xs font-semibold text-ink">
          Predicted response findings
        </h3>
        <span className="tnum text-[10px] text-dim">
          {insights.length} {insights.length === 1 ? "moment" : "moments"}
        </span>
      </div>

      <p className="border-b border-line px-4 py-2 text-[11px] leading-relaxed text-muted">
        {referenceStatus === "unavailable"
          ? "No reference for this media type yet. Benchmarked findings are unavailable."
          : "Exploratory reference from a small set of independent clips. These are model predictions, not measured audience responses or validated ad outcomes."}
      </p>

      {insights.length === 0 ? (
        <p className="px-4 py-5 text-xs leading-relaxed text-dim">
          {referenceStatus === "unavailable"
            ? "Add independent reference clips to enable comparisons."
            : "No sustained response exceeded the reference threshold."}
        </p>
      ) : (
        <ul className="divide-y divide-line">
          {insights.map((ins, i) => {
            const color = INSIGHT_TYPE_COLORS[ins.type] ?? "#9d9dab";
            return (
              <li key={i}>
                <button
                  type="button"
                  onClick={() => onSeek(ins.time_start)}
                  aria-label={`Seek to ${ins.time_start} seconds: ${typeLabel(
                    ins.type,
                  )}`}
                  className="group w-full px-4 py-3 text-left transition-colors hover:bg-surface-2"
                >
                  <div className="flex items-center gap-2">
                    <span
                      className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide"
                      style={{ color }}
                    >
                      <span
                        aria-hidden
                        className="h-1.5 w-1.5 rounded-full"
                        style={{ backgroundColor: color }}
                      />
                      {typeLabel(ins.type)}
                    </span>
                    <span className="tnum text-[10px] text-dim">
                      {ins.time_start}s–{ins.time_end}s
                    </span>
                    <span className="ml-auto text-[10px] font-medium text-dim opacity-0 transition-opacity group-hover:opacity-100">
                      Seek →
                    </span>
                  </div>

                  <p className="mt-1.5 text-xs leading-relaxed text-muted">{stripTimePrefix(ins.description)}</p>
                  {ins.reference && ins.z != null && ins.value != null && (
                    <p className="tnum mt-2 text-[11px] text-dim">
                      Predicted {ins.value.toFixed(3)} · Reference {ins.reference.mean.toFixed(3)} ± {ins.reference.std.toFixed(3)}
                      {` · z ${ins.z > 0 ? "+" : ""}${ins.z.toFixed(2)} · ${ins.reference.n_clips} other clips`}
                    </p>
                  )}
                  {ins.caveat && <p className="mt-1 text-[10px] leading-relaxed text-dim">{ins.caveat}</p>}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
