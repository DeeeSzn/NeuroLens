/** Brain region color scheme and labels. */

export const REGION_COLORS: Record<string, string> = {
  visual: "#3b82f6",           // blue
  auditory: "#22c55e",         // green
  language: "#f97316",         // orange
  dorsal_attention: "#ef4444", // red — attention control (area 8/6, FEF/PEF)
  mpfc_valuation: "#6366f1",   // indigo — mPFC, frontal pole, valuation
  multisensory: "#a855f7",     // purple
  tpoj: "#14b8a6",             // teal  — TPOJ multimodal hotspot
  memory: "#f59e0b",           // amber — memory encoding
  face_body: "#ec4899",        // pink  — face/body content
};

export const REGION_LABELS: Record<string, string> = {
  visual: "Visual Cortex",
  auditory: "Auditory Cortex",
  language: "Language Areas",
  dorsal_attention: "Dorsal Attention",
  mpfc_valuation: "Prefrontal Areas",
  multisensory: "Multisensory Integration",
  tpoj: "TPOJ (Multimodal Hub)",
  memory: "Memory-Associated Areas",
  face_body: "Face / Body Areas",
};

export const REGIONS = [
  "visual", "auditory", "language", "dorsal_attention", "mpfc_valuation",
  "multisensory", "tpoj", "memory", "face_body",
] as const;
export type RegionName = (typeof REGIONS)[number];

/** Compact labels for tight readouts (region strips, dense legends). */
export const REGION_SHORT_LABELS: Record<string, string> = {
  visual: "Visual",
  auditory: "Auditory",
  language: "Language",
  dorsal_attention: "Dorsal Attn",
  mpfc_valuation: "Prefrontal",
  multisensory: "Multisensory",
  tpoj: "TPOJ",
  memory: "Memory",
  face_body: "Face/Body",
};

/** Input modalities whose TRIBE v2 features drive each region. */
export const REGION_MODALITIES: Record<string, string[]> = {
  visual: ["video"],
  auditory: ["audio"],
  language: ["audio", "text"],
  dorsal_attention: ["video", "audio", "text"],
  mpfc_valuation: ["video", "audio", "text"],
  multisensory: ["video", "audio", "text"],
  tpoj: ["video", "audio", "text"],
  memory: ["video", "audio", "text"],
  face_body: ["video"],
};

const MODALITY_LABELS: Record<string, string> = {
  video: "Video",
  audio: "Audio",
  text: "Text",
};

const MODALITY_INITIALS: Record<string, string> = {
  video: "V",
  audio: "A",
  text: "T",
};

/** Spelled-out modalities, e.g. "Video · Audio" — for tooltips. */
export function modalityLabel(region: string, mediaType?: string): string {
  return (REGION_MODALITIES[region] ?? []).filter((modality) => mediaType !== "audio" || modality !== "video")
    .map((m) => MODALITY_LABELS[m] ?? m)
    .join(" · ");
}

/** Compact modality initials, e.g. "V·A" — for dense readouts. */
export function modalityInitials(region: string, mediaType?: string): string {
  return (REGION_MODALITIES[region] ?? []).filter((modality) => mediaType !== "audio" || modality !== "video")
    .map((m) => MODALITY_INITIALS[m] ?? m)
    .join("·");
}

export const INSIGHT_TYPE_LABELS: Record<string, string> = {
  attention_response: "Dorsal attention ↑",
  attention_response_low: "Dorsal attention ↓",
  auditory_response: "Auditory ↑",
  language_response: "Language ↑",
  mpfc_response: "Prefrontal ↑",
  tpoj_response: "TPOJ ↑",
  memory_area_response: "Memory-associated ↑",
  visual_response: "Visual ↑",
  face_area_response: "Face/body areas ↑",
};

export const INSIGHT_TYPE_COLORS: Record<string, string> = {
  attention_response: "#22c55e",
  attention_response_low: "#ef4444",
  auditory_response: "#22c55e",
  language_response: "#f97316",
  mpfc_response: "#ef4444",
  tpoj_response: "#14b8a6",
  memory_area_response: "#f59e0b",
  visual_response: "#3b82f6",
  face_area_response: "#ec4899",
};
