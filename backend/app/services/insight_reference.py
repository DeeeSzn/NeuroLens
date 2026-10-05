"""Versioned, exploratory reference distributions from independent TRIBE outputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from app.config import settings
from app.services.brain_regions import REGION_GROUPS
from app.services.tribe_wrapper import _get_hcp_label_map, _region_mean_activation

REFERENCE_VERSION = "audio-pilot-v1"
MIN_REFERENCE_CLIPS = 3
# A job that is itself a reference clip is compared against the remaining ones.
MIN_COMPARISON_CLIPS = MIN_REFERENCE_CLIPS - 1


def source_hash(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def current_timesteps(result: dict) -> list[dict]:
    """Reaggregate saved vertices after ROI changes, preserving model timestamps."""
    vertices = result.get("raw_vertices", [])
    if len(vertices) != len(result.get("timesteps", [])):
        raise ValueError("Result has no complete vertex predictions")
    labels = _get_hcp_label_map()
    return [
        {
            **step,
            "regions": {
                region: _region_mean_activation(np.asarray(row), labels, region)
                for region in REGION_GROUPS
            },
        }
        for step, row in zip(result["timesteps"], vertices)
    ]


def with_current_regions(result: dict) -> dict:
    """Upgrade results saved before the region split to the current partition."""
    steps = result.get("timesteps")
    if steps and "dorsal_attention" not in steps[0]["regions"] and result.get("raw_vertices"):
        result["timesteps"] = current_timesteps(result)
    return result


def build_reference(samples: list[tuple[str, dict]], media_type: str) -> dict:
    if media_type not in ("audio", "video"):
        raise ValueError("Unsupported media type")
    clips = {}
    for fingerprint, result in samples:
        if fingerprint in clips:
            raise ValueError("Duplicate source in reference set")
        timesteps = current_timesteps(result)
        if len(timesteps) < 3:
            raise ValueError("Reference clip needs at least three timesteps")
        clips[fingerprint] = {
            "regions": {
                region: {
                    "mean": float(np.mean(values)),
                    "variance": float(np.var(values)),
                }
                for region in REGION_GROUPS
                if (values := [step["regions"][region] for step in timesteps])
            }
        }
    if len(clips) < MIN_REFERENCE_CLIPS:
        raise ValueError(f"Reference needs at least {MIN_REFERENCE_CLIPS} independent clips")
    return {"version": REFERENCE_VERSION, "media_type": media_type, "clips": clips}


def load_reference(media_type: str, path: Path | None = None) -> dict | None:
    path = path or settings.insight_references_dir / f"{media_type}.json"
    if not path.exists():
        return None
    reference = json.loads(path.read_text())
    if reference.get("media_type") != media_type or reference.get("version") != REFERENCE_VERSION:
        raise ValueError("Reference media type or version mismatch")
    return reference


def region_reference(reference: dict, region: str, exclude_hash: str | None) -> dict | None:
    clips = [
        clip["regions"][region]
        for fingerprint, clip in reference["clips"].items()
        if fingerprint != exclude_hash and region in clip["regions"]
    ]
    if len(clips) < MIN_COMPARISON_CLIPS:
        return None
    mean = float(np.mean([clip["mean"] for clip in clips]))
    variance = float(np.mean([clip["variance"] + (clip["mean"] - mean) ** 2 for clip in clips]))
    if variance < 1e-8:
        return None
    return {"mean": mean, "std": float(np.sqrt(variance)), "n_clips": len(clips)}