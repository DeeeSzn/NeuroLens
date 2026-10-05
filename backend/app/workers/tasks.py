"""Celery tasks for GPU inference."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

from sqlalchemy import create_engine, event, update
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.config import settings
from app.models.database import Job, JobStatus
from app.services.job_control import JobCancelled, clear_cancel, is_cancelled

logger = logging.getLogger(__name__)

# Synchronous engine for Celery workers (they run outside the async loop)
_sync_db_url = settings.database_url.replace("+aiosqlite", "")
_sync_engine = create_engine(_sync_db_url)

if _sync_engine.dialect.name == "sqlite":

    @event.listens_for(_sync_engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


# Job currently executing in this worker process. Used by the worker_shutdown
# signal (see celery_app.py) to fail a job if the worker exits gracefully.
_current_job_id: str | None = None


def _utcnow_naive() -> datetime:
    """Naive UTC, matching how SQLite stores DateTime values."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _update_job(job_id: str, **kwargs):
    """Update a job record synchronously."""
    with Session(_sync_engine) as session:
        job = session.get(Job, job_id)
        if job:
            for k, v in kwargs.items():
                setattr(job, k, v)
            session.commit()


def _touch_job(job_id: str):
    """Bump updated_at only (heartbeat), so the reaper can tell this job is alive."""
    try:
        with Session(_sync_engine) as session:
            session.execute(
                update(Job)
                .where(Job.id == job_id, Job.status == JobStatus.PROCESSING)
                .values(updated_at=_utcnow_naive())
            )
            session.commit()
    except Exception:
        logger.debug("Heartbeat update failed for %s", job_id, exc_info=True)


def _heartbeat_loop(job_id: str, stop: threading.Event):
    while not stop.wait(settings.job_heartbeat_seconds):
        _touch_job(job_id)


@celery_app.task(bind=True, name="neurolens.analyze")
def analyze_content(self, job_id: str, file_path: str, media_type: str):
    """Run TRIBE v2 inference on uploaded content.

    This task is the main GPU workload. It:
    1. Updates job status to PROCESSING and starts a heartbeat thread
    2. Runs inference via the TRIBE v2 wrapper, checking for cancellation at
       each progress checkpoint
    3. Generates insights
    4. Saves results and updates job to COMPLETE
    """
    global _current_job_id
    _current_job_id = job_id

    logger.info("Starting analysis for job %s", job_id)
    clear_cancel(job_id)  # drop any stale flag from a previous run
    _update_job(job_id, status=JobStatus.PROCESSING, progress=0.1, error_message=None)

    stop = threading.Event()
    heartbeat = threading.Thread(
        target=_heartbeat_loop,
        args=(job_id, stop),
        name=f"heartbeat-{job_id[:8]}",
        daemon=True,
    )
    heartbeat.start()

    def _on_progress(p: float):
        # Cooperative cancellation: checked at each phase boundary.
        if is_cancelled(job_id):
            raise JobCancelled()
        _update_job(job_id, progress=p)

    try:
        from app.services.tribe_wrapper import run_inference, save_result

        _update_job(job_id, progress=0.2)
        result = run_inference(file_path, media_type, on_progress=_on_progress)
        _update_job(job_id, progress=0.7)

        from app.services.insights import generate_insights
        from app.services.insight_reference import load_reference, source_hash
        from app.services.insight_rules import RULESET_VERSION

        fingerprint = source_hash(file_path)
        reference = load_reference(media_type)
        insights = generate_insights(
            result["timesteps"], result["tr_seconds"], media_type,
            reference, fingerprint,
        )
        result["insights"] = insights
        result["insight_ruleset_version"] = RULESET_VERSION
        result["insight_reference_version"] = reference["version"] if reference else None
        _update_job(job_id, progress=0.9)

        result_path = save_result(result, job_id)
        _update_job(
            job_id,
            status=JobStatus.COMPLETE,
            progress=1.0,
            result_path=result_path,
        )
        logger.info("Job %s completed successfully", job_id)
        return {"job_id": job_id, "status": "complete"}

    except JobCancelled:
        logger.info("Job %s cancelled by user", job_id)
        _update_job(job_id, status=JobStatus.FAILED, error_message="Cancelled by user")
        return {"job_id": job_id, "status": "cancelled"}

    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        _update_job(job_id, status=JobStatus.FAILED, error_message=str(exc))
        raise

    finally:
        stop.set()
        clear_cancel(job_id)
        _current_job_id = None
