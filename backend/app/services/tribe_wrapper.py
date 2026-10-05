"""TRIBE v2 inference wrapper.

Wraps the TribeModel with post-processing logic that converts raw vertex
predictions into per-timestep, ROI-grouped activation data suitable for
the NeuroLens frontend.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

import numpy as np

from app.config import settings
from app.services.brain_regions import REGION_GROUPS
from app.services.job_control import JobCancelled
from app.services.memlog import MemorySampler, log_mem

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy-loaded singletons, one per mode — the model is heavy and should be
# loaded once per mode. Two modes instead of one: a worker sees both audio
# and video jobs over its lifetime, and TRIBE v2's `features_to_use` (which
# extractors even get built into the pipeline) is baked in at load time, so
# an audio-mode model must never be reused for a video job or vice versa.
# ---------------------------------------------------------------------------
_models: dict[str, object] = {}


def _get_model(media_type: str = "video"):
    """Load TribeModel once per mode ("video" or "audio") and cache it.

    Audio-only jobs load with `features_to_use=["text", "audio"]`, which
    excludes "video" entirely from TRIBE v2's data pipeline (see
    `tribev2/tribev2/main.py::get_loaders`, which only builds an extractor for
    modalities listed there). That means V-JEPA2 is never constructed, never
    loaded, and never touches MPS memory for an audio job -- not just "skipped
    because there are no video events", which would still pay the load cost.
    """
    mode = "video" if media_type == "video" else "audio"
    if mode in _models:
        return _models[mode]

    from tribev2 import TribeModel

    logger.info("Loading TRIBE v2 model for mode=%s (this may take a minute)\u2026", mode)
    device = settings.tribe_device
    is_video = mode == "video"

    # LLaMA 3.2-3B uses Grouped Query Attention (24 query heads / 8 KV heads).
    # PyTorch's MPS backend cannot broadcast across mismatched GQA head counts
    # (crashes with "mps.matmul incompatible dimensions", Abort trap 6).
    # Force the text extractor to CPU; audio and video run fine on MPS.
    text_device = "cpu" if device == "mps" else device

    # Halve the MPS extractors' footprint before they load (V-JEPA2/Wav2Vec-BERT
    # are fp32 by default and are the memory bottleneck). Text stays fp32 on CPU.
    if device == "mps" and settings.tribe_extractor_dtype:
        from app.services.mps_precision import apply_mps_precision

        apply_mps_precision(
            settings.tribe_extractor_dtype,
            empty_cache_each_call=settings.tribe_mps_empty_cache_each_call,
        )

    config_update: dict = {
        # Excludes "video" for audio jobs -- the actual guard, not the device
        # settings below (those only matter if video is in this list).
        "data.features_to_use": ["text", "audio", "video"] if is_video else ["text", "audio"],
        "data.text_feature.device": text_device,
        "data.audio_feature.device": device,
        # num_workers>0 fails inside Celery daemon processes (can't spawn children)
        "data.num_workers": 0,
    }
    if is_video:
        config_update["data.image_feature.image.device"] = device
        config_update["data.video_feature.image.device"] = device
        # V-JEPA2 peak memory scales with the frame batch; 1 keeps the
        # attention/hidden-state spike bounded. Output-preserving (LayerNorm).
        config_update["data.video_feature.image.batch_size"] = settings.tribe_video_batch_size
        if settings.tribe_video_num_frames:
            # `num_frames` is a field of HuggingFaceVideo itself, not its nested
            # `.image` sub-config (unlike model_name/device/batch_size above).
            # Cuts the self-attention buffer roughly quadratically (see config.py
            # docstring). Experimental: not verified output-preserving.
            config_update["data.video_feature.num_frames"] = settings.tribe_video_num_frames

    # Prefer locally-converted fp16 checkpoints when present: loading them never
    # builds an fp32 copy, removing the ~5 GB load transient. Falls back to the
    # Hub ids baked into the model config when the local dirs are absent.
    models_dir = Path(settings.tribe_models_dir)
    vjepa_local = models_dir / "vjepa2-vitg-fpc64-256-fp16"
    wav2vec_local = models_dir / "w2v-bert-2.0-fp16"
    if vjepa_local.is_dir() or wav2vec_local.is_dir():
        from app.services.mps_precision import allow_local_model_paths

        allow_local_model_paths()
    if is_video and vjepa_local.is_dir():
        config_update["data.video_feature.image.model_name"] = str(vjepa_local)
        logger.info("Using local fp16 V-JEPA2 checkpoint: %s", vjepa_local)
    if wav2vec_local.is_dir():
        config_update["data.audio_feature.model_name"] = str(wav2vec_local)
        logger.info("Using local fp16 Wav2Vec-BERT checkpoint: %s", wav2vec_local)

    model = TribeModel.from_pretrained(
        settings.tribe_model_name,
        cache_folder=settings.tribe_cache_dir,
        device=device,
        config_update=config_update,
    )
    _models[mode] = model
    logger.info("Text extractor on %s, audio%s on %s.", text_device, "/video" if is_video else "", device)
    logger.info("TRIBE v2 model loaded successfully.")
    return model


def _get_hcp_label_map() -> dict[str, np.ndarray]:
    """Return cached HCP-MMP1 label name → vertex indices mapping."""
    import mne
    from tribev2.utils import get_hcp_labels

    old_level = mne.set_log_level("WARNING", return_old_level=True)
    try:
        return get_hcp_labels(mesh="fsaverage5")
    finally:
        mne.set_log_level(old_level)


def _robust_normalize(arr: np.ndarray, percentile: int = 99) -> np.ndarray:
    """Normalize activations to [0, 1] using the 1st/99th percentiles.

    This is the upstream TRIBE v2 convention (``plotting.utils.robust_normalize``,
    percentile=99, two-sided, clipped) but applied deterministically: the previous
    implementation delegated to that optional helper when its plotting deps
    happened to be importable and silently fell back to 2/98 otherwise, so the
    stored values depended on the environment. NaNs/infs are zeroed first so they
    cannot poison the percentiles (which would serialize as bare ``NaN`` in the
    result JSON and break ``response.json()`` in the browser).
    """
    arr = np.nan_to_num(
        np.asarray(arr, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0
    )
    lo = np.percentile(arr, 100 - percentile)
    hi = np.percentile(arr, percentile)
    if hi - lo < 1e-8:
        return np.zeros_like(arr)
    return np.clip((arr - lo) / (hi - lo), 0.0, 1.0).astype(np.float32)


def _get_media_duration(file_path: str) -> float | None:
    """Get actual media duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path,
            ],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception:
        pass
    return None


def _region_mean_activation(
    vertex_data_1d: np.ndarray,
    hcp_labels: dict[str, np.ndarray],
    region: str,
) -> float:
    """Compute mean activation for a functional region group."""
    rois = REGION_GROUPS.get(region, [])
    values: list[float] = []
    for roi_name in rois:
        # get_hcp_labels returns names without hemisphere prefix (e.g. "V1" not "L_V1")
        if roi_name in hcp_labels:
            indices = hcp_labels[roi_name]
            if len(indices) > 0:
                values.append(float(np.mean(vertex_data_1d[indices])))
    return float(np.mean(values)) if values else 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_inference(file_path: str, media_type: str, on_progress=None) -> dict:
    """Run full TRIBE v2 inference and return structured result dict.

    Parameters
    ----------
    file_path : str
        Absolute path to the uploaded video or audio file.
    media_type : str
        "video" or "audio".
    on_progress : callable(float) | None
        Optional callback invoked with a progress fraction (0‒1) at each
        major phase so the caller can persist progress to the database.

    Returns
    -------
    dict
        Structured analysis result ready to be serialized as JSON.
    """
    def _emit(p: float):
        if on_progress is not None:
            try:
                on_progress(p)
            except JobCancelled:
                raise  # cooperative cancel must propagate
            except Exception:
                pass  # never let a progress update crash inference

    model = _get_model(media_type)
    log_mem("phase:model_ready")
    _emit(0.25)  # model ready, about to extract features

    # Sample RSS during the long, checkpoint-free phases (whisperx + extractors + forward).
    sampler = MemorySampler.from_settings("inference")
    sampler.start()
    try:
        # 1. Build events dataframe
        logger.info("Building events from %s …", file_path)
        if media_type == "video":
            events = model.get_events_dataframe(video_path=file_path)
        else:
            events = model.get_events_dataframe(audio_path=file_path)
        log_mem("phase:after_events")
        _emit(0.40)  # feature extraction complete

        # 2. Run prediction
        logger.info("Running brain prediction …")
        preds, segments = model.predict(events=events)
        log_mem("phase:after_predict")
    finally:
        sampler.stop()
    _emit(0.60)  # brain prediction complete
    preds_np = np.asarray(
        preds.cpu().numpy() if hasattr(preds, "cpu") else preds, dtype=np.float32
    )

    # The model's own temporal resolution is authoritative (1.0 s for the
    # released checkpoint); settings.tr_seconds is only a fallback.
    tr = float(getattr(model.data, "TR", settings.tr_seconds) or settings.tr_seconds)

    # Time comes from each segment's start, never the row index: predict() drops
    # empty windows (remove_empty_segments=True), so index != time.
    seg_starts = np.array(
        [float(getattr(seg, "start", i * tr)) for i, seg in enumerate(segments)],
        dtype=np.float64,
    )

    # Actual media duration from the file, not from a TR guess.
    actual_duration = _get_media_duration(file_path)
    if actual_duration is None:
        actual_duration = round(float(seg_starts[-1] + tr) if len(seg_starts) else 0.0, 2)
        logger.warning("Could not probe media duration, falling back to %ss", actual_duration)
    else:
        actual_duration = round(actual_duration, 2)

    # Keep only windows that start within the real media duration. Replaces the
    # old index-based clamp, which discarded valid windows whenever the assumed
    # TR exceeded the model's. Never drop everything.
    if len(seg_starts):
        keep = seg_starts < actual_duration
        if not keep.any():
            keep = np.ones(len(seg_starts), dtype=bool)
        if not keep.all():
            logger.info(
                "Dropping %d/%d windows starting at/after %.2fs",
                int((~keep).sum()), len(keep), actual_duration,
            )
            preds_np = preds_np[keep]
            seg_starts = seg_starts[keep]
            segments = [seg for seg, k in zip(segments, keep) if k]

    n_timesteps, n_vertices = preds_np.shape
    logger.info(
        "Prediction complete: %d timesteps × %d vertices (TR %.3fs, duration %.2fs)",
        n_timesteps, n_vertices, tr, actual_duration,
    )

    # 3. Normalize the prediction matrix once, for visualization
    norm_preds = _robust_normalize(preds_np)

    # 4. Get HCP label map
    hcp_labels = _get_hcp_label_map()
    log_mem("phase:after_normalize")
    _emit(0.65)  # normalization + label map ready

    # 5. Extract words for a segment from its own events (Word type only)
    def _words_for_segment(seg) -> list[str]:
        found: list[tuple[float, str]] = []
        for ev in getattr(seg, "ns_events", []):
            if getattr(ev, "type", None) != "Word":
                continue
            text = getattr(ev, "text", None)
            if text:
                found.append((float(getattr(ev, "start", 0.0)), str(text)))
        found.sort(key=lambda item: item[0])
        return [text for _, text in found]

    # 6. Build per-timestep data
    # Compute top ROIs manually (get_topk_rois has a bug with hemi="both" returning 0-d array)
    def _topk_rois(vertex_1d: np.ndarray, k: int = 10) -> list[str]:
        scores = []
        for roi_name, indices in hcp_labels.items():
            if len(indices) > 0:
                scores.append((roi_name, float(np.mean(vertex_1d[indices]))))
        scores.sort(key=lambda x: x[1], reverse=True)
        return [name for name, _ in scores[:k]]

    timesteps_data: list[dict] = []
    for t in range(n_timesteps):
        vertex_1d = norm_preds[t]
        regions = {
            region: _region_mean_activation(vertex_1d, hcp_labels, region)
            for region in REGION_GROUPS
        }
        top_rois = _topk_rois(vertex_1d, k=10)
        timesteps_data.append({
            "time_sec": round(float(seg_starts[t]), 2),
            "regions": regions,
            "top_rois": top_rois,
            "words": _words_for_segment(segments[t]),
        })
    _emit(0.68)  # per-timestep data built

    # 7. Also store raw normalized vertices per timestep for 3D brain viz
    raw_vertices = norm_preds.tolist()
    log_mem("phase:done")

    return {
        "duration_sec": actual_duration,
        "n_timesteps": n_timesteps,
        "tr_seconds": tr,
        "timesteps": timesteps_data,
        "raw_vertices": raw_vertices,
    }


def save_result(result: dict, job_id: str) -> str:
    """Save inference result to disk and return the file path."""
    out_path = settings.results_dir / f"{job_id}.json"
    with open(out_path, "w") as f:
        json.dump(result, f)
    return str(out_path)


def load_result(result_path: str) -> dict:
    """Load a previously saved result from disk."""
    with open(result_path) as f:
        return json.load(f)
