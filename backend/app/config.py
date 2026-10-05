from __future__ import annotations

from pathlib import Path
from typing import List, Set

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "NeuroLens"
    debug: bool = False

    # File storage
    static_dir: Path = Path(__file__).resolve().parents[1] / "static"
    upload_dir: Path = Path("./uploads")
    results_dir: Path = Path("./results")
    insight_references_dir: Path = Path("./references")
    max_upload_size_mb: int = 500
    allowed_extensions: Set[str] = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".mp3", ".wav", ".flac", ".ogg"}

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # TRIBE v2
    tribe_model_name: str = "facebook/tribev2"
    tribe_cache_dir: str = "./cache"
    tribe_device: str = "mps"
    # V-JEPA2 frame batch size. Peak GPU/unified memory scales with this (the
    # video extractor's attention + cached hidden states are the dominant
    # allocation on this stack). Lower is output-preserving: V-JEPA2 is
    # LayerNorm-only, so per-sample results do not depend on the batch.
    tribe_video_batch_size: int = 1
    # Frames sampled per clip window, fed to V-JEPA2 (checkpoint max: 64). The
    # self-attention buffer scales ~quadratically with this, so 64->32 is a
    # ~4x cut, 64->16 a ~16x cut. NOT fully output-preserving: neuralset spreads
    # `num_frames` samples evenly over the *same* look-back window (see
    # `subtimes` in HuggingFaceVideo._get_data), so the real-world time span a
    # prediction covers is unchanged, only the temporal sampling density within
    # it drops. None uses the checkpoint's default (64). Unverified whether
    # V-JEPA2's temporal position embeddings interpolate cleanly for fewer
    # frames -- treat this as an experiment, not a guaranteed fix.
    tribe_video_num_frames: int | None = None
    # Half-precision for the MPS feature extractors (V-JEPA2/Wav2Vec-BERT) to
    # halve unified-memory use. "" disables. See app/services/mps_precision.py.
    tribe_extractor_dtype: str = "float16"
    # Directory holding locally-converted fp16 extractor checkpoints (see
    # scripts/convert_extractors_fp16.py). When present, these are loaded instead
    # of the fp32 Hub checkpoints, removing the fp32->fp16 load transient.
    tribe_models_dir: str = "./models"
    # Release the MPS allocator cache after every extractor forward so the
    # video attention buffer is not retained across clips.
    tribe_mps_empty_cache_each_call: bool = True

    # Inference memory guard. On Apple Silicon the hog is GPU/unified memory,
    # which is NOT reflected in process RSS — so the guard watches system
    # headroom and aborts the worker before the OS thrashes into a panic.
    mem_guard_enabled: bool = True
    mem_sample_seconds: float = 5.0
    mem_limit_rss_gb: float = 0.0     # 0 disables the (unreliable) RSS check
    mem_min_avail_gb: float = 1.5     # abort if system available RAM below this
    # 22GB (not the original 6GB): on this 16GB machine baseline swap from other
    # apps/model caches often sits in the high teens before a job even starts, so
    # 6GB aborted healthy audio jobs immediately. Swap breaches also need 2
    # consecutive samples (see MemorySampler) before aborting, so this is no
    # longer a hair-trigger. mem_min_avail_gb is still the instant, unconditional
    # abort for actual panic risk.
    mem_max_swap_gb: float = 22.0     # abort if swap in use above this (sustained)

    # Database
    database_url: str = "sqlite+aiosqlite:///./neurolens.db"

    # Job lifecycle / stale-job recovery
    job_stale_seconds: int = 300        # processing job with no heartbeat this long -> failed
    job_heartbeat_seconds: int = 30     # worker touches updated_at at this interval
    job_reaper_interval_seconds: int = 60
    cancel_flag_ttl_seconds: int = 3600

    # CORS
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://[::1]:3000",
    ]

    # fMRI. Fallback only — the loaded model's own TR (1.0 s for the released
    # facebook/tribev2 checkpoint) is authoritative at inference time.
    tr_seconds: float = 1.0

    model_config = {"env_prefix": "NEUROLENS_", "env_file": ".env"}


settings = Settings()

# Ensure directories exist
settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.results_dir.mkdir(parents=True, exist_ok=True)
