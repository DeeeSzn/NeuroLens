"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import { motion } from "motion/react";
import { FileText, Braces, Plus } from "lucide-react";
import {
  api,
  exportUrls,
  type AnalysisResult,
  type InsightsResponse,
  type TimelineData,
  type TimestepData,
  type RegionActivation,
} from "@/lib/api";
import { usePlaybackSync } from "@/lib/hooks";
import { prettyFilename, formatDuration } from "@/lib/format";
import InsightsPanel from "@/components/InsightsPanel";
import VideoPlayer from "@/components/VideoPlayer";
import TimelineChart from "@/components/TimelineChart";
import AppNav from "@/components/AppNav";
import Atmosphere from "@/components/Atmosphere";
import ActivityColorbar from "@/components/ActivityColorbar";
import BrainControls, {
  type SurfaceMode,
  type BrainMode,
} from "@/components/BrainControls";
import {
  REGION_COLORS,
  REGION_LABELS,
  REGION_SHORT_LABELS,
  REGION_MODALITIES,
  REGIONS,
  modalityInitials,
  modalityLabel,
} from "@/lib/constants";
import type {
  MeshType,
  RegionClickInfo,
} from "@/components/BrainVisualization";

const BrainVisualization = dynamic(
  () => import("@/components/BrainVisualization"),
  { ssr: false, loading: () => <div className="absolute inset-0 bg-canvas" /> },
);

/** ROIs where V-JEPA-2 patch averaging makes early visual areas unreliable. */
const VJEPA_CAVEAT_ROIS = ["V1", "V2", "V3", "V4", "V3A", "V3B", "V3CD", "V6", "V7"];
const AUDIO_REGIONS = REGIONS.filter((region) => REGION_MODALITIES[region].some((modality) => modality !== "video"));

/**
 * Map a playback time to a timestep index using the model-provided
 * `timesteps[i].time_sec` — never `t / tr_seconds`, because empty windows are
 * dropped server-side so the row index is not a linear function of time.
 */
function timestepForTime(timesteps: TimestepData[], t: number): number {
  if (!timesteps.length) return 0;
  let idx = 0;
  for (let i = 0; i < timesteps.length; i++) {
    if (timesteps[i].time_sec <= t + 1e-6) idx = i;
    else break;
  }
  return idx;
}

export default function AnalysisPage() {
  const { jobId } = useParams<{ jobId: string }>();

  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [insights, setInsights] = useState<InsightsResponse | null>(null);
  const [timeline, setTimeline] = useState<TimelineData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [surfaceMode, setSurfaceMode] = useState<SurfaceMode>("inflated");
  const [brainMode, setBrainMode] = useState<BrainMode>("close");
  const [resetSignal, setResetSignal] = useState(0);
  const [regionInfo, setRegionInfo] = useState<RegionClickInfo | null>(null);

  const meshType: MeshType = surfaceMode;

  const { currentTime, seekTo, setCurrentTime } = usePlaybackSync(
    result?.tr_seconds,
  );

  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;
    // Timeline is a progressive enhancement — a failure must not blank the page.
    Promise.all([
      api.getResult(jobId),
      api.getInsights(jobId),
      api.getTimeline(jobId).catch(() => null),
    ])
      .then(([r, i, t]) => {
        if (cancelled) return;
        setResult(r);
        setInsights(i);
        setTimeline(t);
      })
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  const ts = useMemo(() => {
    if (!result) return 0;
    const raw = timestepForTime(result.timesteps, currentTime);
    return Math.max(0, Math.min(raw, result.n_timesteps - 1));
  }, [result, currentTime]);

  if (loading) return <LoadingState />;
  if (error || !result) return <ErrorState message={error} />;

  const regions = result.timesteps[ts]?.regions;
  const visibleRegions = result.media_type === "audio" ? AUDIO_REGIONS : REGIONS;
  const values = visibleRegions.map((region) => regionValue(regions, region));
  const peak = Math.max(...values, 0);

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-canvas lg:flex-row">
      {/* ══ Brain panel ══════════════════════════════════════════════════ */}
      <section className="relative h-[44vh] min-w-0 flex-shrink-0 overflow-hidden bg-[#050507] lg:h-full lg:flex-[3]">
        <Atmosphere />
        <div className="pointer-events-none absolute inset-x-0 top-0 z-20 flex items-start justify-between gap-3 p-3 sm:p-4">
          <AppNav className="pointer-events-auto" />
          <ActivityColorbar />
        </div>

        <div className="absolute inset-0 z-10">
          <BrainVisualization
            jobId={jobId}
            timestep={ts}
            meshType={meshType}
            isOpen={brainMode === "open"}
            onRegionClick={setRegionInfo}
            resetSignal={resetSignal}
          />
        </div>

        {regionInfo && (
          <RegionCard info={regionInfo} onClose={() => setRegionInfo(null)} />
        )}

        <div className="absolute inset-x-0 bottom-0 z-20 flex flex-wrap items-center justify-center gap-2 p-3 sm:p-4">
          <BrainControls
            surface={surfaceMode}
            onSurface={setSurfaceMode}
            brain={brainMode}
            onBrain={setBrainMode}
            onReset={() => setResetSignal((s) => s + 1)}
          />
        </div>
      </section>

      <div className="h-px w-full flex-shrink-0 bg-line lg:h-full lg:w-px" />

      {/* ══ Detail panel ═════════════════════════════════════════════════ */}
      <section className="relative flex min-h-0 min-w-0 flex-1 flex-col bg-surface lg:flex-[2]">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-36 opacity-60"
          style={{
            background:
              "radial-gradient(80% 100% at 50% 0%, rgba(79,141,255,0.10), transparent 70%)",
          }}
        />
        <motion.header
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
          className="relative flex flex-shrink-0 items-start justify-between gap-3 border-b border-line px-5 py-5 sm:px-6"
        >
          <div className="min-w-0">
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-accent">
              Response analysis
            </p>
            <h1 className="font-display truncate text-lg font-semibold leading-tight text-ink">
              {prettyFilename(result.filename, result.media_type)}
            </h1>
            <p className="mt-0.5 text-[11px] text-muted">
              {result.media_type} · {formatDuration(result.duration_sec)} ·{" "}
              {result.n_timesteps} timesteps
            </p>
          </div>
          <div className="flex flex-shrink-0 items-center gap-1">
            <a
              href={exportUrls.report(jobId)}
              className="flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-[11px] font-medium text-dim transition-colors hover:bg-surface-2 hover:text-ink"
              title="Download Markdown report"
            >
              <FileText size={13} strokeWidth={1.75} aria-hidden />
              <span className="hidden sm:inline">Report</span>
            </a>
            <a
              href={exportUrls.json(jobId)}
              className="flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-[11px] font-medium text-dim transition-colors hover:bg-surface-2 hover:text-ink"
              title="Download raw JSON"
            >
              <Braces size={13} strokeWidth={1.75} aria-hidden />
              <span className="hidden sm:inline">JSON</span>
            </a>
            <Link
              href="/"
              className="nl-glass ml-1 flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[11px] font-medium text-muted transition-colors hover:text-ink"
            >
              <Plus size={13} strokeWidth={2} aria-hidden />
              New
            </Link>
          </div>
        </motion.header>

        <RegionStrip regions={regions} peak={peak} visibleRegions={visibleRegions} mediaType={result.media_type} />

        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, delay: 0.08, ease: [0.22, 1, 0.36, 1] }}
          className="relative min-h-0 min-w-0 flex-1 space-y-4 overflow-y-auto p-4 sm:p-5"
        >
          {result.media_type === "video" ? (
            <VideoPlayer
              src={`/api/jobs/${jobId}/video`}
              currentTime={currentTime}
              onTimeUpdate={setCurrentTime}
            />
          ) : (
            <AudioCard
              filename={prettyFilename(result.filename, result.media_type)}
              duration={result.duration_sec}
              currentTime={currentTime}
              timestep={ts}
              nTimesteps={result.n_timesteps}
            />
          )}

          {timeline && (
            <TimelineChart
              data={timeline}
              visibleRegions={visibleRegions}
              mediaType={result.media_type}
              insights={insights?.insights ?? []}
              currentTime={currentTime}
              onSeek={seekTo}
            />
          )}

          <InsightsPanel insights={insights?.insights ?? []} referenceStatus={insights?.reference_status ?? "unavailable"} onSeek={seekTo} />

          <p className="px-1 pb-1 text-[10px] leading-relaxed text-dim">
            t = <span className="tnum">{currentTime.toFixed(1)}s</span> ·
            timestep <span className="tnum">{ts}</span> /{" "}
            {result.n_timesteps - 1} · TR{" "}
            <span className="tnum">{result.tr_seconds}s</span>
          </p>
        </motion.div>
      </section>
    </div>
  );
}

/** Read a region's activation without widening the strongly-typed payload. */
function regionValue(
  regions: RegionActivation | undefined,
  key: string,
): number {
  if (!regions) return 0;
  return (regions as unknown as Record<string, number>)[key] ?? 0;
}

/* ── Region activation strip ────────────────────────────────────────────── */

function RegionStrip({
  regions,
  peak,
  visibleRegions,
  mediaType,
}: {
  regions: RegionActivation | undefined;
  peak: number;
  visibleRegions: readonly string[];
  mediaType: string;
}) {
  return (
    <div className="relative flex-shrink-0 overflow-x-auto border-b border-line bg-surface-2/25 px-3 py-3 sm:px-5">
      <ul className="flex min-w-max gap-1 sm:min-w-0">
        {visibleRegions.map((r) => {
          const v = regionValue(regions, r);
          const isPeak = v > 0 && v === peak;
          const color = REGION_COLORS[r];
          return (
            <li key={r} className="w-14 shrink-0 sm:w-auto sm:min-w-0 sm:flex-1">
              <div
                className="group flex flex-col items-center gap-1"
                title={`${REGION_LABELS[r]}: ${v.toFixed(2)} normalized — driven by ${modalityLabel(r, mediaType)}`}
              >
                <span
                  className="tnum text-[11px] font-semibold leading-none"
                  style={{ color: v > 0 ? color : "#67677a" }}
                >
                  {v.toFixed(2)}
                </span>
                <div className="h-8 w-full overflow-hidden rounded-md border border-white/[0.03] bg-surface-2">
                  <div
                    className="w-full rounded-sm transition-all duration-500"
                    style={{
                      height: `${Math.min(1, Math.max(0.02, v)) * 100}%`,
                      marginTop: `${(1 - Math.min(1, Math.max(0.02, v))) * 100}%`,
                      backgroundColor: color,
                      opacity: isPeak ? 1 : 0.75,
                    }}
                  />
                </div>
                <span
                  className={`w-full truncate text-center text-[10px] leading-tight transition-colors sm:text-[9px] ${
                    isPeak ? "text-muted" : "text-dim group-hover:text-muted"
                  }`}
                >
                  {REGION_SHORT_LABELS[r] ?? r}{" "}
                  <span className="text-dim/60">{modalityInitials(r, mediaType)}</span>
                </span>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/* ── Brain region info card ─────────────────────────────────────────────── */

function categoryLabel(c: string): string {
  if (!c || c === "other") return "Uncategorized";
  return c.charAt(0).toUpperCase() + c.slice(1);
}

function RegionCard({
  info,
  onClose,
}: {
  info: RegionClickInfo;
  onClose: () => void;
}) {
  const name =
    info.fullName && info.fullName !== info.roi
      ? info.fullName
      : `Region ${info.roi}`;
  const hasValue = !Number.isNaN(info.activation);

  return (
    <div className="animate-in absolute right-3 top-16 z-30 w-60 rounded-xl border border-line-strong bg-surface/95 p-3.5 shadow-2xl backdrop-blur-md">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[13px] font-semibold leading-snug text-ink">
          {name}
        </p>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close region details"
          className="-mr-1 -mt-0.5 rounded-md p-1 text-dim transition-colors hover:bg-surface-2 hover:text-ink"
        >
          <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden>
            <path
              d="M2 2l8 8M10 2l-8 8"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
            />
          </svg>
        </button>
      </div>

      <p className="mt-1 text-[10px] uppercase tracking-wide text-dim">
        {info.roi} · {info.hemi === "lh" ? "Left" : "Right"} ·{" "}
        {categoryLabel(info.category)}
      </p>

      {hasValue && (
        <div className="mt-2.5 flex items-baseline gap-1.5">
          <span className="tnum text-lg font-semibold leading-none text-ink">
            {info.activation.toFixed(3)}
          </span>
          <span className="text-[10px] text-dim">activation</span>
        </div>
      )}

      {VJEPA_CAVEAT_ROIS.includes(info.roi) && (
        <p className="mt-3 border-t border-line pt-2.5 text-[10px] leading-relaxed text-warn/80">
          V-JEPA-2 spatially averages patch tokens, so early visual areas
          (V1–V4) may be systematically underpredicted.
        </p>
      )}
    </div>
  );
}

/* ── Audio (no video preview) ───────────────────────────────────────────── */

function AudioCard({
  filename,
  duration,
  currentTime,
  timestep,
  nTimesteps,
}: {
  filename: string;
  duration: number;
  currentTime: number;
  timestep: number;
  nTimesteps: number;
}) {
  const pct = duration > 0 ? Math.min(100, (currentTime / duration) * 100) : 0;
  return (
    <div className="nl-card p-4">
      <h3 className="text-xs font-semibold text-ink">Audio content</h3>
      <p className="mt-1 truncate text-[11px] text-muted">{filename}</p>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-surface-3">
        <div
          className="h-full rounded-full bg-gradient-to-r from-accent to-accent-soft transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="mt-2 flex items-center justify-between text-[10px] text-dim">
        <span className="tnum">{currentTime.toFixed(1)}s</span>
        <span className="tnum">
          timestep {timestep} / {nTimesteps - 1}
        </span>
        <span className="tnum">{duration.toFixed(1)}s</span>
      </div>
    </div>
  );
}

/* ── Page states ────────────────────────────────────────────────────────── */

function LoadingState() {
  return (
    <div className="flex h-screen items-center justify-center bg-canvas">
      <div className="flex flex-col items-center gap-3">
        <div
          className="h-8 w-8 rounded-full border-2 border-line border-t-accent animate-spin"
          aria-hidden
        />
        <p className="text-xs text-muted" role="status">
          Loading analysis…
        </p>
      </div>
    </div>
  );
}

function ErrorState({ message }: { message: string | null }) {
  return (
    <div className="flex h-screen items-center justify-center bg-canvas px-6">
      <div
        role="alert"
        className="w-full max-w-sm rounded-xl border border-bad/25 bg-bad/10 p-5 text-center"
      >
        <p className="text-sm font-semibold text-bad">
          Couldn’t load this analysis
        </p>
        <p className="mt-1.5 text-xs leading-relaxed text-bad/80">
          {message ?? "The result may have been deleted or the job failed."}
        </p>
        <Link
          href="/"
          className="mt-4 inline-block rounded-lg border border-line px-4 py-2 text-xs font-medium text-muted transition-colors hover:text-ink"
        >
          Back to uploads
        </Link>
      </div>
    </div>
  );
}
