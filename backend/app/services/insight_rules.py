"""Exploratory findings on predicted cortical responses, not behavioral outcomes."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.services.brain_regions import REGION_GROUPS, REGION_MODALITIES
from app.services.insight_reference import region_reference

RULESET_VERSION = "descriptive-v1"
INPUT_MODALITIES = {"audio": {"audio", "text"}, "video": {"video", "audio", "text"}}
CAVEAT = "Predicted average-subject response; per-clip normalized, small uncalibrated pilot reference, not measured engagement or a clinical finding."


@dataclass(frozen=True)
class Detector:
    id: str
    signal: str
    rule: str
    modalities: tuple[str, ...]
    claim_level: str
    template: str
    citation: str
    version: str = RULESET_VERSION
    threshold_z: float = 1.5
    min_seconds: float = 2.0


DETECTORS = (
    Detector("attention_response", "dorsal_attention", "above_reference", ("audio", "video"), "descriptive", "Predicted dorsal attention response above reference", "HCP-MMP1 atlas"),
    Detector("attention_response_low", "dorsal_attention", "below_reference", ("audio", "video"), "descriptive", "Predicted dorsal attention response below reference", "HCP-MMP1 atlas"),
    Detector("auditory_response", "auditory", "above_reference", ("audio", "video"), "descriptive", "Predicted auditory response above reference", "HCP-MMP1 atlas"),
    Detector("language_response", "language", "above_reference", ("audio", "video"), "descriptive", "Predicted language-area response above reference", "HCP-MMP1 atlas"),
    Detector("mpfc_response", "mpfc_valuation", "above_reference", ("audio", "video"), "descriptive", "Predicted prefrontal response above reference", "HCP-MMP1 atlas"),
    Detector("tpoj_response", "tpoj", "above_reference", ("audio", "video"), "descriptive", "Predicted TPOJ response above reference", "TRIBE v2, d'Ascoli et al., 2026"),
    Detector("memory_area_response", "memory", "above_reference", ("audio", "video"), "descriptive", "Predicted memory-associated cortical response above reference", "HCP-MMP1 atlas"),
    Detector("visual_response", "visual", "above_reference", ("video",), "descriptive", "Predicted visual response above reference", "HCP-MMP1 atlas"),
    Detector("face_area_response", "face_body", "above_reference", ("video",), "descriptive", "Predicted face/body-area response above reference", "TRIBE v2, d'Ascoli et al., 2026"),
)


def evaluate(timesteps: list[dict], tr_seconds: float, media_type: str, reference: dict | None, exclude_hash: str | None = None) -> list[dict]:
    if len(timesteps) < 3 or reference is None or reference.get("media_type") != media_type:
        return []
    findings = []
    for detector in DETECTORS:
        if detector.claim_level != "descriptive" or media_type not in detector.modalities:
            continue
        if not INPUT_MODALITIES[media_type] & set(REGION_MODALITIES[detector.signal]):
            continue
        if any(detector.signal not in step["regions"] for step in timesteps):
            continue
        baseline = region_reference(reference, detector.signal, exclude_hash)
        if baseline is None:
            continue
        values = np.array([step["regions"][detector.signal] for step in timesteps], dtype=float)
        z_scores = (values - baseline["mean"]) / baseline["std"]
        mask = z_scores >= detector.threshold_z if detector.rule == "above_reference" else z_scores <= -detector.threshold_z
        position = 0
        while position < len(mask):
            if not mask[position]:
                position += 1
                continue
            start = position
            position += 1
            while position < len(mask) and mask[position] and float(timesteps[position]["time_sec"]) - float(timesteps[position - 1]["time_sec"]) <= tr_seconds * 1.5:
                position += 1
            end = position - 1
            start_time = float(timesteps[start]["time_sec"])
            end_time = float(timesteps[end]["time_sec"]) + tr_seconds
            if end_time - start_time < detector.min_seconds:
                continue
            value = float(np.mean(values[start:position]))
            z = (value - baseline["mean"]) / baseline["std"]
            findings.append({
                "time_start": round(start_time, 2), "time_end": round(end_time, 2),
                "type": detector.id, "region": detector.signal,
                "description": detector.template + ".",
                "value": round(value, 4), "reference": baseline,
                "z": round(z, 3),
                "evidence_rois": REGION_GROUPS[detector.signal],
                "claim_level": detector.claim_level, "confidence": None,
                "caveat": CAVEAT, "ruleset_version": detector.version,
                "citation": detector.citation,
            })
    return sorted(findings, key=lambda item: (item["time_start"], item["type"]))