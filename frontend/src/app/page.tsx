"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { useDropzone } from "react-dropzone";
import { motion } from "motion/react";
import {
  Upload,
  Film,
  Music,
  ArrowUpRight,
  AlertCircle,
  Sparkles,
} from "lucide-react";
import { api, type JobStatus } from "@/lib/api";
import { useJobPoller, useAnimatedProgress } from "@/lib/hooks";
import { prettyFilename, relativeTime } from "@/lib/format";
import AppNav from "@/components/AppNav";
import Atmosphere from "@/components/Atmosphere";
import ActivityColorbar from "@/components/ActivityColorbar";
import BrainControls, {
  type SurfaceMode,
  type BrainMode,
} from "@/components/BrainControls";
import { StatusDot, jobStatusMeta } from "@/components/ui/JobStatus";
import type { MeshType } from "@/components/BrainVisualization";

const BrainVisualization = dynamic(
  () => import("@/components/BrainVisualization"),
  { ssr: false, loading: () => <div className="absolute inset-0 bg-canvas" /> },
);

const ACCEPT = {
  "video/*": [".mp4", ".avi", ".mov", ".mkv", ".webm"],
  "audio/*": [".mp3", ".wav", ".flac", ".ogg"],
};

export default function HomePage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<JobStatus[]>([]);
  const [uploading, setUploading] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [surfaceMode, setSurfaceMode] = useState<SurfaceMode>("inflated");
  const [brainMode, setBrainMode] = useState<BrainMode>("close");
  const [resetSignal, setResetSignal] = useState(0);

  const meshType: MeshType = surfaceMode;

  const polledJob = useJobPoller(activeJobId);
  const animatedProgress = useAnimatedProgress(
    polledJob?.progress ?? 0,
    polledJob?.status === "processing",
  );

  useEffect(() => {
    if (polledJob?.status === "complete") {
      router.push(`/analysis/${polledJob.job_id}`);
    }
    if (polledJob?.status === "failed") {
      setErrorMsg(
        polledJob.error_message || "Analysis failed — please try again.",
      );
      setUploading(false);
      setActiveJobId(null);
      setCancelling(false);
    }
  }, [polledJob, router]);

  useEffect(() => {
    api.listJobs().then(setJobs).catch(() => {});
  }, []);

  const onDrop = useCallback(async (accepted: File[]) => {
    if (!accepted.length) return;
    setUploading(true);
    setErrorMsg(null);
    try {
      const { job_id } = await api.uploadFile(accepted[0]);
      setActiveJobId(job_id);
    } catch (err) {
      setUploading(false);
      setErrorMsg(
        err instanceof Error ? err.message : "Upload failed — please try again.",
      );
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    accept: ACCEPT,
    maxFiles: 1,
    maxSize: 500 * 1024 * 1024,
    disabled: uploading || !!activeJobId,
    noKeyboard: true,
  });

  const isProcessing = uploading || !!activeJobId;

  const handleCancel = useCallback(async () => {
    if (!activeJobId) return;
    setCancelling(true);
    try {
      await api.cancelJob(activeJobId);
    } catch {
      setCancelling(false);
    }
  }, [activeJobId]);

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
            meshType={meshType}
            isOpen={brainMode === "open"}
            resetSignal={resetSignal}
          />
        </div>

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

      {/* ══ Upload panel ═════════════════════════════════════════════════ */}
      <section className="relative flex min-h-0 min-w-0 flex-1 flex-col bg-surface lg:flex-[2]">
        {/* top-lit glow behind the panel header */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-64 opacity-70"
          style={{
            background:
              "radial-gradient(80% 100% at 50% 0%, rgba(139,92,255,0.10), transparent 70%)",
          }}
        />

        <motion.header
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          className="relative flex-shrink-0 border-b border-line px-6 py-6 sm:px-7 sm:py-7"
        >
          <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface-2/60 px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.16em] text-muted">
            <Sparkles size={11} className="text-accent" aria-hidden />
            Neural response engine
          </span>
          <h1 className="mt-3 font-display text-3xl font-semibold leading-[1.05] tracking-tight text-ink sm:text-[2.1rem]">
            See what the
            <br />
            brain <span className="nl-gradient-text">responds</span> to.
          </h1>
          <p className="mt-3 max-w-md text-[13px] leading-relaxed text-muted">
            Upload a video or audio file — TRIBE v2 predicts whole-brain
            cortical activation, timestep by timestep.
          </p>
        </motion.header>

        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto">
          <div className="flex flex-1 items-center justify-center p-6 sm:p-7">
            {errorMsg && !isProcessing ? (
              <ErrorBanner
                message={errorMsg}
                onDismiss={() => setErrorMsg(null)}
              />
            ) : isProcessing ? (
              <ProcessingState
                filename={polledJob?.filename}
                status={polledJob?.status}
                progress={animatedProgress}
                cancelling={cancelling}
                onCancel={handleCancel}
              />
            ) : (
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.08, ease: [0.22, 1, 0.36, 1] }}
                className="w-full max-w-sm"
              >
                <div
                  {...getRootProps()}
                  role="button"
                  tabIndex={0}
                  aria-label="Upload a video or audio file"
                  aria-disabled={isProcessing}
                  data-active={isDragActive}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      open();
                    }
                  }}
                  className={`nl-ring-glow group relative cursor-pointer overflow-hidden rounded-3xl border p-9 text-center transition-all duration-300 sm:p-11 ${
                    isDragActive
                      ? "-translate-y-0.5 border-accent/60 bg-accent/10 shadow-[0_20px_60px_-24px_rgba(139,92,255,0.9)]"
                      : "border-dashed border-line-strong bg-surface-2/30 hover:-translate-y-0.5 hover:bg-surface-2/50 hover:shadow-[0_24px_60px_-30px_rgba(139,92,255,0.7)]"
                  }`}
                >
                  <input {...getInputProps()} />
                  <div
                    className={`mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-line bg-surface-2 text-muted transition-all duration-300 group-hover:scale-105 group-hover:text-white ${
                      isDragActive ? "scale-110 text-white" : ""
                    }`}
                    style={{
                      boxShadow: isDragActive
                        ? "0 0 30px -6px rgba(139,92,255,0.9)"
                        : undefined,
                    }}
                  >
                    <Upload
                      size={22}
                      strokeWidth={1.75}
                      className={`transition-transform duration-300 ${
                        isDragActive ? "-translate-y-0.5" : "group-hover:-translate-y-0.5"
                      }`}
                    />
                  </div>
                  <p className="mt-5 text-base font-medium text-ink">
                    {isDragActive ? "Drop to analyse" : "Drop a file to analyse"}
                  </p>
                  <p className="mt-2 text-[11px] leading-relaxed text-muted">
                    MP4, MOV, AVI, WebM, MP3, WAV, FLAC, OGG · up to 500 MB
                  </p>
                  <p className="mt-5 text-[11px] font-semibold text-accent">
                    Browse files
                    <span className="ml-1 font-normal text-dim">
                      or press Enter
                    </span>
                  </p>
                </div>
              </motion.div>
            )}
          </div>

          {!isProcessing && jobs.length > 0 && <RecentAnalyses jobs={jobs} />}
        </div>
      </section>
    </div>
  );
}

/* ── Processing ─────────────────────────────────────────────────────────── */

function ProcessingState({
  filename,
  status,
  progress,
  cancelling,
  onCancel,
}: {
  filename?: string;
  status?: string;
  progress: number;
  cancelling: boolean;
  onCancel: () => void;
}) {
  const pct = Math.round(progress * 100);
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      className="w-full max-w-xs space-y-6 text-center"
    >
      <div className="relative mx-auto h-16 w-16">
        <div
          className="absolute inset-0 rounded-full opacity-60 blur-xl"
          style={{ background: "rgba(139,92,255,0.5)" }}
          aria-hidden
        />
        <div
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Analysis progress"
          className="relative h-16 w-16 rounded-full border-[3px] border-line border-t-accent animate-spin"
        />
      </div>
      <div>
        <p className="text-sm font-medium text-ink" aria-live="polite">
          {status === "processing" ? "Analysing brain response…" : "Uploading…"}
        </p>
        <p className="mt-1 truncate text-[11px] text-muted">
          {filename ? prettyFilename(filename) : "Preparing"}
        </p>
      </div>
      <div>
        <div className="h-1.5 overflow-hidden rounded-full bg-surface-3">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${pct}%`,
              background: "linear-gradient(90deg, #8b5cff, #4f8dff, #38d0ff)",
            }}
          />
        </div>
        <div className="mt-2 flex items-center justify-between">
          <span className="tnum text-[11px] text-muted">{pct}%</span>
          <button
            type="button"
            onClick={onCancel}
            disabled={cancelling || status !== "processing"}
            className="rounded-md px-2 py-1 text-[11px] font-medium text-dim transition-colors hover:bg-surface-2 hover:text-ink disabled:cursor-not-allowed disabled:opacity-40"
          >
            {cancelling ? "Cancelling…" : "Cancel"}
          </button>
        </div>
      </div>
      <p className="text-[10px] leading-relaxed text-dim">
        Inference runs on the local GPU and can take a few minutes.
      </p>
    </motion.div>
  );
}

/* ── Error ──────────────────────────────────────────────────────────────── */

function ErrorBanner({
  message,
  onDismiss,
}: {
  message: string;
  onDismiss: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      role="alert"
      className="w-full max-w-sm rounded-2xl border border-bad/25 bg-bad/10 p-4"
    >
      <div className="flex items-start gap-2.5">
        <AlertCircle size={16} className="mt-0.5 flex-shrink-0 text-bad" />
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold text-bad">Analysis failed</p>
          <p className="mt-1 text-[11px] leading-relaxed text-bad/80">
            {message}
          </p>
        </div>
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss error"
          className="-mr-1 -mt-1 rounded-md p-1 text-bad/60 transition-colors hover:bg-bad/10 hover:text-bad"
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
    </motion.div>
  );
}

/* ── Recent analyses ────────────────────────────────────────────────────── */

function RecentAnalyses({ jobs }: { jobs: JobStatus[] }) {
  const recent = jobs.slice(0, 6);
  return (
    <div className="flex-shrink-0 border-t border-line px-5 pb-5 pt-4 sm:px-6">
      <h2 className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-dim">
        Recent analyses
      </h2>
      <ul className="space-y-0.5">
        {recent.map((job, i) => {
          const done = job.status === "complete";
          const meta = jobStatusMeta(job.status);
          const Icon = job.media_type === "video" ? Film : Music;
          const label = prettyFilename(job.filename, job.media_type);

          const inner = (
            <>
              <StatusDot status={job.status} />
              <Icon
                size={13}
                strokeWidth={1.75}
                className="flex-shrink-0 text-dim"
                aria-hidden
              />
              <span
                className={`min-w-0 flex-1 truncate text-xs ${
                  done ? "text-muted group-hover:text-ink" : "text-dim"
                }`}
              >
                {label}
              </span>
              <span className="flex-shrink-0 text-[10px] text-dim">
                {done ? (
                  relativeTime(job.created_at)
                ) : (
                  <span className={meta.text}>{meta.label}</span>
                )}
              </span>
              {done && (
                <ArrowUpRight
                  size={13}
                  strokeWidth={1.75}
                  aria-hidden
                  className="flex-shrink-0 text-dim transition-all duration-200 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-accent"
                />
              )}
            </>
          );

          return (
            <motion.li
              key={job.job_id}
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{
                duration: 0.35,
                delay: 0.05 * i,
                ease: [0.22, 1, 0.36, 1],
              }}
            >
              {done ? (
                <a
                  href={`/analysis/${job.job_id}`}
                  className="group flex items-center gap-2.5 rounded-lg px-2 py-2 transition-colors hover:bg-surface-2"
                >
                  {inner}
                </a>
              ) : (
                <div className="flex items-center gap-2.5 rounded-lg px-2 py-2">
                  {inner}
                </div>
              )}
            </motion.li>
          );
        })}
      </ul>
    </div>
  );
}
