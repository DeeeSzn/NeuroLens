"""Lightweight RSS / system-memory logging for diagnosing inference memory use.

Why system memory, not RSS: on Apple Silicon the video extractor (V-JEPA2) runs
on MPS and its allocations live in unified/GPU memory plus the video-encode path
(child processes). A probe showed the Python process RSS never exceeded 1.7 GB
while system available memory fell to <0.2 GB and swap climbed past 15 GB. So an
RSS-based guard never fires. The guard here watches *system* headroom instead.

Enable via env:
  NEUROLENS_MEM_LOG=1              -> log a sample every NEUROLENS_MEM_SAMPLE_SECONDS
  NEUROLENS_MEM_MIN_AVAIL_GB=1.5   -> abort if system available RAM drops below this
  NEUROLENS_MEM_MAX_SWAP_GB=6      -> abort if swap in use exceeds this
  NEUROLENS_MEM_LIMIT_GB=10        -> abort if the process RSS exceeds this
"""

from __future__ import annotations

import logging
import os
import resource
import sys
import threading

import psutil

logger = logging.getLogger(__name__)

_PROC = psutil.Process(os.getpid())
_IS_DARWIN = sys.platform == "darwin"


def rss_gb() -> float:
    """Current resident set size in GB."""
    return _PROC.memory_info().rss / 1e9


def peak_rss_gb() -> float:
    """Process lifetime peak RSS in GB (ru_maxrss is bytes on macOS, KiB on Linux)."""
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value / 1e9 if _IS_DARWIN else value / 1024 / 1024


def system() -> tuple[float, float]:
    """(available RAM GB, used swap GB)."""
    vm = psutil.virtual_memory()
    sw = psutil.swap_memory()
    return vm.available / 1e9, sw.used / 1e9


def log_mem(label: str) -> None:
    """Log current + peak RSS and system headroom for one phase boundary."""
    try:
        avail, swap_used = system()
        logger.info(
            "[mem] %-22s rss=%.2fGB peak=%.2fGB sys_avail=%.2fGB swap_used=%.2fGB",
            label, rss_gb(), peak_rss_gb(), avail, swap_used,
        )
    except Exception:
        logger.info("[mem] %-22s rss=%.2fGB", label, rss_gb())


def _env_float(name: str) -> float | None:
    value = os.environ.get(name)
    return float(value) if value else None


class MemorySampler:
    """Daemon thread sampling memory so peaks inside long phases are visible.

    Aborts the process (os._exit) if a configured ceiling is crossed. This is a
    last-resort safety valve: the main thread is usually blocked inside torch and
    cannot be interrupted cooperatively, and letting the machine thrash has
    already produced kernel panics on this hardware.
    """

    def __init__(
        self,
        interval: float = 5.0,
        limit_rss_gb: float | None = None,
        min_avail_gb: float | None = None,
        max_swap_gb: float | None = None,
        label: str = "sample",
    ):
        self.interval = interval
        self.limit_rss_gb = limit_rss_gb
        self.min_avail_gb = min_avail_gb
        self.max_swap_gb = max_swap_gb
        self.label = label
        self.max_rss = 0.0
        self.enabled = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        # swap climbs transiently during model loads (whisperx, extractors); require
        # 2 consecutive breaches (~2*interval seconds) before aborting on swap alone.
        # min_avail has no debounce -- it is the direct panic precursor (see activity.md).
        self._swap_breach_streak = 0
        self._swap_breach_threshold = 2

    @classmethod
    def from_env(cls, label: str = "sample") -> "MemorySampler":
        enabled = os.environ.get("NEUROLENS_MEM_LOG", "").lower() in ("1", "true", "yes")
        sampler = cls(
            interval=float(os.environ.get("NEUROLENS_MEM_SAMPLE_SECONDS", "5")),
            limit_rss_gb=_env_float("NEUROLENS_MEM_LIMIT_GB"),
            min_avail_gb=_env_float("NEUROLENS_MEM_MIN_AVAIL_GB"),
            max_swap_gb=_env_float("NEUROLENS_MEM_MAX_SWAP_GB"),
            label=label,
        )
        sampler.enabled = enabled or any(
            v is not None
            for v in (sampler.limit_rss_gb, sampler.min_avail_gb, sampler.max_swap_gb)
        )
        return sampler

    @classmethod
    def from_settings(cls, label: str = "inference") -> "MemorySampler":
        """Build from app settings (used by the worker) rather than env vars."""
        from app.config import settings

        sampler = cls(
            interval=float(
                os.environ.get("NEUROLENS_MEM_SAMPLE_SECONDS", settings.mem_sample_seconds)
            ),
            limit_rss_gb=settings.mem_limit_rss_gb or None,
            min_avail_gb=settings.mem_min_avail_gb,
            max_swap_gb=settings.mem_max_swap_gb,
            label=label,
        )
        sampler.enabled = settings.mem_guard_enabled
        return sampler

    def _abort(self, reason: str) -> None:
        logger.critical("[mem] ABORT during %s: %s", self.label, reason)
        os._exit(3)

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            cur = rss_gb()
            self.max_rss = max(self.max_rss, cur)
            avail, swap_used = system()
            logger.info(
                "[mem] %-22s rss=%.2fGB peak=%.2fGB sys_avail=%.2fGB swap_used=%.2fGB",
                self.label, cur, peak_rss_gb(), avail, swap_used,
            )
            if self.limit_rss_gb is not None and cur > self.limit_rss_gb:
                self._abort(f"process rss {cur:.2f}GB > {self.limit_rss_gb}GB")
            if self.min_avail_gb is not None and avail < self.min_avail_gb:
                self._abort(f"system available {avail:.2f}GB < {self.min_avail_gb}GB")
            if self.max_swap_gb is not None and swap_used > self.max_swap_gb:
                self._swap_breach_streak += 1
                if self._swap_breach_streak >= self._swap_breach_threshold:
                    self._abort(f"swap used {swap_used:.2f}GB > {self.max_swap_gb}GB (sustained)")
            else:
                self._swap_breach_streak = 0

    def start(self) -> None:
        if not self.enabled:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="mem-sampler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
