import type { JobStatus } from "@/lib/api";

export type JobState = JobStatus["status"];

interface Meta {
  label: string;
  dot: string;
  text: string;
}

const META: Record<JobState, Meta> = {
  pending: { label: "Queued", dot: "bg-warn", text: "text-warn" },
  processing: {
    label: "Processing",
    dot: "bg-accent-soft animate-pulse-soft",
    text: "text-accent-soft",
  },
  complete: { label: "Complete", dot: "bg-good", text: "text-good" },
  failed: { label: "Failed", dot: "bg-bad", text: "text-bad" },
};

export function jobStatusMeta(status: JobState): Meta {
  return META[status] ?? META.pending;
}

/** Small coloured dot + optional label describing a job's lifecycle state. */
export function StatusDot({
  status,
  showLabel = false,
}: {
  status: JobState;
  showLabel?: boolean;
}) {
  const m = jobStatusMeta(status);
  return (
    <span className="flex items-center gap-1.5">
      <span
        aria-hidden
        className={`h-1.5 w-1.5 flex-shrink-0 rounded-full ${m.dot}`}
      />
      {showLabel ? (
        <span className={`text-[11px] font-medium ${m.text}`}>{m.label}</span>
      ) : (
        <span className="sr-only">{m.label}</span>
      )}
    </span>
  );
}
