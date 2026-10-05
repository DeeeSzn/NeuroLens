"use client";

import { RotateCcw } from "lucide-react";
import SegmentedControl from "@/components/ui/SegmentedControl";

export type SurfaceMode = "inflated" | "pial";
export type BrainMode = "open" | "close";

interface BrainControlsProps {
  surface: SurfaceMode;
  onSurface: (v: SurfaceMode) => void;
  brain: BrainMode;
  onBrain: (v: BrainMode) => void;
  onReset: () => void;
}

/** Surface / hemisphere toggles plus a camera reset, shared by both brain views. */
export default function BrainControls({
  surface,
  onSurface,
  brain,
  onBrain,
  onReset,
}: BrainControlsProps) {
  return (
    <div className="flex flex-wrap items-center justify-center gap-2">
      <SegmentedControl
        label="Surface type"
        value={surface}
        onChange={onSurface}
        options={[
          { value: "pial", label: "Normal" },
          { value: "inflated", label: "Inflated" },
        ]}
      />
      <SegmentedControl
        label="Hemisphere layout"
        value={brain}
        onChange={onBrain}
        options={[
          { value: "close", label: "Close" },
          { value: "open", label: "Open" },
        ]}
      />
      <button
        type="button"
        onClick={onReset}
        aria-label="Reset view"
        title="Reset view"
        className="nl-glass group flex h-7 w-7 items-center justify-center rounded-full text-dim transition-colors hover:text-ink"
      >
        <RotateCcw
          size={13}
          strokeWidth={1.9}
          aria-hidden
          className="transition-transform duration-500 group-hover:-rotate-180"
        />
      </button>
    </div>
  );
}
