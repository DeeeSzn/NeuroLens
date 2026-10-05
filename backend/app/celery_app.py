"""Celery application configuration."""

import logging

from celery import Celery
from celery.signals import worker_ready, worker_shutdown

from app.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "neurolens",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,  # one GPU task at a time
    worker_concurrency=1,
)

# Auto-discover tasks in workers package
celery_app.autodiscover_tasks(["app.workers"])


@worker_ready.connect
def preload_tribe_model(**kwargs):
    """Pre-warm the TRIBE v2 model when the worker process starts.

    This moves the multi-minute model load from the first job to worker
    startup, so every inference task hits a warm cache instantly. Preloads
    the "audio" mode (text+audio only, no V-JEPA2) -- that's the one this
    machine can actually run reliably. Video mode loads lazily on the first
    video job instead, since eagerly warming V-JEPA2 at startup would spend
    the same memory this Mac doesn't have to spare on jobs that may never come.
    """
    logger.info("Worker ready — pre-loading TRIBE v2 model (audio mode)…")
    try:
        from app.services.tribe_wrapper import _get_model
        _get_model("audio")
        logger.info("TRIBE v2 model pre-loaded and ready.")
    except Exception:
        logger.exception("Failed to pre-load TRIBE v2 model — will retry on first task.")


@worker_shutdown.connect
def mark_running_job_failed(**kwargs):
    """Fail the in-flight job when the worker shuts down gracefully.

    A hard kill (SIGKILL) skips this handler; the stale-job reaper covers that.
    """
    from app.models.database import JobStatus
    from app.workers import tasks

    job_id = tasks._current_job_id
    if not job_id:
        return
    logger.warning("Worker shutting down mid-job — failing %s", job_id)
    try:
        tasks._update_job(
            job_id,
            status=JobStatus.FAILED,
            error_message="Worker shut down mid-job",
        )
    except Exception:
        logger.exception("Failed to mark job %s failed on shutdown", job_id)
