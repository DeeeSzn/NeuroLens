"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { motion } from "motion/react";
import { ChevronDown, ArrowLeftRight, Upload, Sparkles } from "lucide-react";
import {
  api,
  type JobStatus,
  type ComparisonResult,
  type TimelineData,
} from "@/lib/api";
import { prettyFilename } from "@/lib/format";
import {
  REGION_COLORS,
  REGION_LABELS,
  REGIONS,
} from "@/lib/constants";
import RegionLegend from "@/components/RegionLegend";
import AppNav from "@/components/AppNav";
import Atmosphere from "@/components/Atmosphere";
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

export default function ComparePage() {
  const [jobs, setJobs] = useState<JobStatus[] | null>(null);
  const [jobA, setJobA] = useState("");
  const [jobB, setJobB] = useState("");
  const [comparison, setComparison] = useState<ComparisonResult | null>(null);
  const [timelinesA, setTimelineA] = useState<TimelineData | null>(null);
  const [timelinesB, setTimelineB] = useState<TimelineData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listJobs()
      .then((j) => setJobs(j.filter((x) => x.status === "complete")))
      .catch(() => setJobs([]));
  }, []);

  const runComparison = async () => {
    if (!jobA || !jobB) return;
    setLoading(true);
    setError(null);
    try {
      const [comp, tA, tB] = await Promise.all([
        api.compare(jobA, jobB),
        api.getTimeline(jobA),
        api.getTimeline(jobB),
      ]);
      setComparison(comp);
      setTimelineA(tA);
      setTimelineB(tB);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Comparison failed");
    } finally {
      setLoading(false);
    }
  };

  const swap = () => {
    setJobA(jobB);
    setJobB(jobA);
    setComparison(null);
  };

  const ready = jobA && jobB && jobA !== jobB;

  return (
    <div className="relative min-h-screen overflow-hidden bg-canvas">
      <Atmosphere ember={false} />
      <div className="sticky top-0 z-20 border-b border-line bg-canvas/75 backdrop-blur-xl">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-5 py-3 sm:px-6">
          <AppNav />
          <h1 className="hidden text-xs font-medium uppercase tracking-[0.14em] text-dim sm:block">
            Comparison studio
          </h1>
        </div>
      </div>

      <main className="relative z-10 mx-auto max-w-5xl px-5 py-10 sm:px-6 sm:py-14">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          className="mb-8 max-w-2xl"
        >
          <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface/60 px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.16em] text-muted">
            <Sparkles size={11} className="text-accent" aria-hidden />
            Version intelligence
          </span>
          <h1 className="mt-3 font-display text-4xl font-semibold leading-[1.02] text-ink sm:text-5xl">
            See what changed in the
            <span className="nl-gradient-text"> brain response.</span>
          </h1>
          <p className="mt-4 max-w-xl text-sm leading-relaxed text-muted">
            Pair two completed analyses to trace where their predicted cortical
            activation converges and diverges over time.
          </p>
        </motion.div>

        {jobs !== null && jobs.length < 2 ? (
          <EmptyState count={jobs.length} />
        ) : (
          <>
            {/* ── Selectors ── */}
            <motion.section
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, delay: 0.08, ease: [0.22, 1, 0.36, 1] }}
              className="nl-card p-4 sm:p-5"
            >
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <h2 className="font-display text-lg font-semibold text-ink">
                    Choose two analyses
                  </h2>
                  <p className="mt-0.5 text-xs text-muted">
                    Compare finished jobs side by side.
                  </p>
                </div>
                <span className="hidden rounded-full border border-line bg-surface-2 px-2 py-1 font-mono text-[10px] text-dim sm:block">
                  A / B
                </span>
              </div>
              <div className="grid gap-3 sm:grid-cols-[1fr_auto_1fr] sm:items-end">
              <JobSelect
                label="Version A"
                value={jobA}
                onChange={(v) => {
                  setJobA(v);
                  setComparison(null);
                }}
                jobs={jobs ?? []}
                exclude={jobB}
              />
              <button
                type="button"
                onClick={swap}
                disabled={!jobA && !jobB}
                aria-label="Swap versions"
                className="nl-glass mx-auto hidden h-9 w-9 items-center justify-center rounded-full text-dim transition-colors hover:text-ink disabled:opacity-40 sm:flex"
              >
                <ArrowLeftRight size={14} strokeWidth={1.75} />
              </button>
              <JobSelect
                label="Version B"
                value={jobB}
                onChange={(v) => {
                  setJobB(v);
                  setComparison(null);
                }}
                jobs={jobs ?? []}
                exclude={jobA}
              />
              </div>

              <button
                type="button"
                onClick={runComparison}
                disabled={!ready || loading}
                className="nl-btn-primary mt-5 text-xs"
              >
                <ArrowLeftRight size={14} strokeWidth={1.8} aria-hidden />
                {loading ? "Comparing…" : "Compare responses"}
              </button>
            </motion.section>

            {error && (
              <div
                role="alert"
                className="mt-5 rounded-2xl border border-bad/25 bg-bad/10 p-4 text-xs text-bad"
              >
                {error}
              </div>
            )}

            {comparison && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
                className="mt-6 space-y-5"
              >
                <section className="nl-card p-4">
                  <h2 className="text-xs font-semibold text-ink">Summary</h2>
                  <p className="mt-1.5 text-xs leading-relaxed text-muted">
                    {comparison.summary}
                  </p>
                </section>

                {timelinesA && timelinesB && (
                  <div className="grid gap-4 lg:grid-cols-2">
                    <MiniTimeline title="Version A" data={timelinesA} />
                    <MiniTimeline title="Version B" data={timelinesB} />
                  </div>
                )}

                <DeltaChart data={comparison.deltas} />

                {comparison.insights.length > 0 && (
                  <section className="nl-card overflow-hidden">
                    <div className="nl-card-header">
                      <h2 className="text-xs font-semibold text-ink">
                        Key differences
                      </h2>
                    </div>
                    <ul className="divide-y divide-line">
                      {comparison.insights.map((ins, i) => (
                        <li
                          key={i}
                          className="px-4 py-3 text-xs leading-relaxed text-muted"
                        >
                          {ins}
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
              </motion.div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

/* ── Selectors ──────────────────────────────────────────────────────────── */

function JobSelect({
  label,
  value,
  onChange,
  jobs,
  exclude,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  jobs: JobStatus[];
  exclude: string;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[10px] font-semibold uppercase tracking-[0.14em] text-dim">
        {label}
      </span>
      <span className="relative block">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full appearance-none rounded-xl border border-line bg-surface-2/50 px-3 py-3 pr-9 text-xs text-ink shadow-[inset_0_1px_0_rgba(255,255,255,0.03)] transition-colors hover:border-line-strong focus:border-accent"
        >
          <option value="">Select an analysis…</option>
          {jobs
            .filter((j) => j.job_id !== exclude)
            .map((j) => (
              <option key={j.job_id} value={j.job_id}>
                {prettyFilename(j.filename, j.media_type)}
              </option>
            ))}
        </select>
        <ChevronDown
          size={14}
          strokeWidth={1.75}
          aria-hidden
          className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-dim"
        />
      </span>
    </label>
  );
}

/* ── Charts ─────────────────────────────────────────────────────────────── */

function buildSeries(data: TimelineData) {
  return data.times.map((t, i) =>
    REGIONS.reduce<Record<string, number>>(
      (acc, r) => {
        const series = data[r as keyof typeof data] as number[] | undefined;
        acc[r] = series?.[i] ?? 0;
        return acc;
      },
      { time: t },
    ),
  );
}

const TOOLTIP_STYLE = {
  backgroundColor: "#15151c",
  border: "1px solid #2b2b38",
  borderRadius: "10px",
  fontSize: 11,
  padding: "8px 10px",
} as const;

function MiniTimeline({ title, data }: { title: string; data: TimelineData }) {
  const chartData = useMemo(() => buildSeries(data), [data]);
  return (
    <section className="nl-card overflow-hidden">
      <div className="nl-card-header">
        <h2 className="text-xs font-semibold text-ink">{title}</h2>
      </div>
      <div className="px-2 pb-2 pt-3">
        <ResponsiveContainer width="100%" height={170}>
          <LineChart
            data={chartData}
            margin={{ top: 4, right: 12, left: 0, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#1d1d26" vertical={false} />
            <XAxis
              dataKey="time"
              tick={{ fill: "#67677a", fontSize: 10 }}
              tickFormatter={(v) => `${v}s`}
              stroke="#1d1d26"
              minTickGap={18}
            />
            <YAxis tick={{ fill: "#67677a", fontSize: 10 }} stroke="#1d1d26" width={40} />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              labelStyle={{ color: "#9d9dab", marginBottom: 4 }}
              labelFormatter={(v) => `t = ${v}s`}
              formatter={(value, key) => [
                Number(value).toFixed(3),
                REGION_LABELS[String(key)] ?? String(key),
              ]}
              itemSorter={(item) => -Number(item.value)}
            />
            {REGIONS.map((r) => (
              <Line
                key={r}
                type="monotone"
                dataKey={r}
                stroke={REGION_COLORS[r]}
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

function DeltaChart({
  data,
}: {
  data: ComparisonResult["deltas"];
}) {
  const maxAbs = useMemo(() => {
    let m = 0;
    for (const d of data) {
      for (const r of REGIONS) {
        const v = (d as Record<string, number>)[`${r}_delta`] ?? 0;
        m = Math.max(m, Math.abs(v));
      }
    }
    // Floor the domain so an all-zero delta still reads as "no difference"
    // rather than stretching to an arbitrary auto-scaled range.
    return Math.max(0.05, m * 1.15);
  }, [data]);

  const anyDifference = useMemo(
    () =>
      data.some((d) =>
        REGIONS.some(
          (r) => Math.abs((d as Record<string, number>)[`${r}_delta`] ?? 0) > 1e-6,
        ),
      ),
    [data],
  );

  return (
    <section className="nl-card overflow-hidden">
      <div className="nl-card-header flex-wrap">
        <h2 className="text-xs font-semibold text-ink">
          Activation difference{" "}
          <span className="font-normal text-dim">(B − A)</span>
        </h2>
        {!anyDifference && (
          <span className="text-[10px] text-dim">
            No measurable difference
          </span>
        )}
      </div>

      <div className="px-4 pt-3">
        <RegionLegend />
      </div>

      <div className="px-2 pb-2 pt-3">
        <ResponsiveContainer width="100%" height={200}>
          <LineChart
            data={data}
            margin={{ top: 4, right: 12, left: 0, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#1d1d26" vertical={false} />
            <XAxis
              dataKey="time_sec"
              tick={{ fill: "#67677a", fontSize: 10 }}
              tickFormatter={(v) => `${v}s`}
              stroke="#1d1d26"
              minTickGap={18}
            />
            <YAxis
              tick={{ fill: "#67677a", fontSize: 10 }}
              stroke="#1d1d26"
              width={48}
              domain={[-maxAbs, maxAbs]}
              tickFormatter={(v) => Number(v).toFixed(2)}
            />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              labelStyle={{ color: "#9d9dab", marginBottom: 4 }}
              labelFormatter={(v) => `t = ${v}s`}
              formatter={(value, key) => [
                Number(value).toFixed(3),
                REGION_LABELS[String(key).replace(/_delta$/, "")] ??
                  String(key),
              ]}
              itemSorter={(item) => -Math.abs(Number(item.value))}
            />
            <ReferenceLine y={0} stroke="#2b2b38" />
            {REGIONS.map((r) => (
              <Line
                key={r}
                type="monotone"
                dataKey={`${r}_delta`}
                stroke={REGION_COLORS[r]}
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

/* ── Empty state ────────────────────────────────────────────────────────── */

function EmptyState({ count }: { count: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay: 0.08, ease: [0.22, 1, 0.36, 1] }}
      className="nl-card flex flex-col items-center px-6 py-14 text-center"
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-line bg-surface-2 text-accent shadow-[0_0_28px_-10px_rgba(139,92,255,0.9)]">
        <ArrowLeftRight size={18} strokeWidth={1.6} />
      </div>
      <p className="mt-4 text-sm font-medium text-ink">
        {count === 0
          ? "No completed analyses yet"
          : "You need one more analysis"}
      </p>
      <p className="mt-1.5 max-w-xs text-xs leading-relaxed text-muted">
        Comparisons run against two finished analyses. Upload another clip to
        unlock side-by-side results.
      </p>
      <Link
        href="/"
        className="nl-btn-primary mt-5 text-xs"
      >
        <Upload size={13} strokeWidth={1.75} aria-hidden />
        Upload content
      </Link>
    </motion.div>
  );
}
