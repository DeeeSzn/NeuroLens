/** Small presentation helpers shared across pages. */

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(.+)$/i;

/**
 * Uploads are often named after their storage id (`9c937596-….mp3`). Those are
 * meaningless to a reader, so surface a readable label plus a short id fragment
 * that still lets you tell two uploads apart.
 */
export function prettyFilename(name: string, mediaType?: string): string {
  const m = name.match(UUID_RE);
  if (m) {
    const kind = (mediaType || m[1] || "file").replace(/^\./, "");
    return `Untitled ${kind} · ${name.slice(0, 8)}`;
  }
  return name;
}

/** "2h ago" / "3d ago", falling back to a short date for older items. */
export function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const diff = Date.now() - then;
  const min = Math.round(diff / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.round(hr / 24);
  if (day < 7) return `${day}d ago`;
  return new Date(iso).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
  });
}

export function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds)) return "—";
  const s = Math.max(0, seconds);
  const m = Math.floor(s / 60);
  const rem = Math.round(s % 60);
  return m > 0
    ? `${m}:${String(rem).padStart(2, "0")}`
    : `${rem % 60}s`;
}
