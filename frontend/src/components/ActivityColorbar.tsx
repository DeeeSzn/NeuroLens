const GRADIENT =
  "linear-gradient(to right, #0a0a14, #7c0000, #c0392b, #e74c3c, #e67e22, #f39c12, #f9ca24, #ffffff)";

/**
 * The activation colour key for the brain overlay. Uses the same `hot`
 * colormap NiiVue renders, so the legend always matches the cortex.
 */
export default function ActivityColorbar({
  className = "",
}: {
  className?: string;
}) {
  return (
    <div
      className={`nl-glass flex items-center gap-2 rounded-full px-3 py-1.5 ${className}`}
    >
      <span className="hidden text-[10px] font-medium uppercase tracking-[0.14em] text-dim sm:inline">
        Activation
      </span>
      <span className="text-[10px] text-muted">Low</span>
      <span
        aria-hidden
        className="h-2 w-16 rounded-full ring-1 ring-white/10 sm:w-24"
        style={{ background: GRADIENT }}
      />
      <span className="text-[10px] text-muted">High</span>
    </div>
  );
}
