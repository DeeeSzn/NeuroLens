"use client";

import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TimelineData, Insight } from "@/lib/api";
import { REGION_COLORS, REGION_LABELS, REGION_SHORT_LABELS, modalityLabel } from "@/lib/constants";

interface TimelineChartProps {
  data: TimelineData;
  visibleRegions: readonly string[];
  mediaType: string;
  insights?: Insight[];
  currentTime: number;
  onSeek: (timeSec: number) => void;
  height?: number;
}

/**
 * Activation-over-time chart that doubles as a scrubber: click anywhere to
 * seek the video + brain to that moment. The legend is interactive so eight
 * overlapping series can be isolated one at a time.
 */
export default function TimelineChart({
  data,
  visibleRegions,
  mediaType,
  insights = [],
  currentTime,
  onSeek,
  height = 200,
}: TimelineChartProps) {
  const [hidden, setHidden] = useState<Set<string>>(new Set());

  const chartData = useMemo(
    () =>
      data.times.map((t, i) =>
        visibleRegions.reduce<Record<string, number>>(
          (acc, r) => {
            const series = data[r as keyof typeof data] as number[] | undefined;
            acc[r] = series?.[i] ?? 0;
            return acc;
          },
          { time: t },
        ),
      ),
    [data, visibleRegions],
  );

  const toggle = (r: string) =>
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(r)) next.delete(r);
      else next.add(r);
      return next;
    });

  const shown = visibleRegions.filter((r) => !hidden.has(r));
  const summary = `Activation timeline over ${data.times.length} timesteps for ${shown.length} of ${visibleRegions.length} regions.`;

  return (
    <div className="nl-card overflow-hidden">
      <div className="nl-card-header flex-wrap">
        <h3 className="text-xs font-semibold text-ink">
          Activation timeline
        </h3>
        <p className="text-[10px] text-dim">Click to scrub</p>
      </div>

      {/* Interactive legend = series filter */}
      <ul className="flex flex-wrap gap-1.5 px-4 pt-3">
        {visibleRegions.map((r) => {
          const off = hidden.has(r);
          return (
            <li key={r}>
              <button
                type="button"
                aria-pressed={!off}
                onClick={() => toggle(r)}
                title={`${REGION_LABELS[r]} — driven by ${modalityLabel(r, mediaType)}`}
                className={`flex items-center gap-1.5 rounded-full border px-2 py-1 text-[10px] font-medium transition-colors ${
                  off
                    ? "border-line text-dim hover:text-muted"
                    : "border-line-strong bg-surface-2 text-muted hover:text-ink"
                }`}
              >
                <span
                  aria-hidden
                  className="h-1.5 w-1.5 flex-shrink-0 rounded-full transition-opacity"
                  style={{
                    backgroundColor: REGION_COLORS[r],
                    opacity: off ? 0.3 : 1,
                  }}
                />
                {REGION_SHORT_LABELS[r] ?? REGION_LABELS[r]}
              </button>
            </li>
          );
        })}
      </ul>

      <div className="px-2 pb-2 pt-3" role="img" aria-label={summary}>
        <ResponsiveContainer width="100%" height={height}>
          <LineChart
            data={chartData}
            margin={{ top: 4, right: 12, left: 0, bottom: 0 }}
            onClick={(e) => {
              if (e?.activeLabel != null) onSeek(Number(e.activeLabel));
            }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#1d1d26" vertical={false} />
            <XAxis
              dataKey="time"
              tick={{ fill: "#67677a", fontSize: 10 }}
              tickFormatter={(v) => `${v}s`}
              stroke="#1d1d26"
              minTickGap={18}
            />
            <YAxis
              tick={{ fill: "#67677a", fontSize: 10 }}
              stroke="#1d1d26"
              width={40}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#15151c",
                border: "1px solid #2b2b38",
                borderRadius: "10px",
                fontSize: 11,
                padding: "8px 10px",
              }}
              labelStyle={{ color: "#9d9dab", marginBottom: 4 }}
              labelFormatter={(v) => `t = ${v}s`}
              formatter={(value, key) => [
                Number(value).toFixed(3),
                REGION_LABELS[String(key)] ?? String(key),
              ]}
              itemSorter={(item) => -Number(item.value)}
            />

            {insights.map((ins, i) => (
              <ReferenceLine
                key={`ins-${i}`}
                x={ins.time_start}
                stroke={ins.type === "attention_response_low" ? "#f87171" : "#34d399"}
                strokeWidth={1}
                strokeDasharray="2 3"
                strokeOpacity={0.5}
              />
            ))}

            {shown.map((r) => (
              <Line
                key={r}
                type="monotone"
                dataKey={r}
                stroke={REGION_COLORS[r]}
                strokeWidth={1.75}
                dot={false}
                activeDot={{ r: 3, strokeWidth: 0 }}
                isAnimationActive={false}
              />
            ))}

            <ReferenceLine x={currentTime} stroke="#f3f3f7" strokeWidth={1.5} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
