"""Fail jobs whose worker died mid-inference.

A running task bumps ``jobs.updated_at`` every ``job_heartbeat_seconds`` from a
daemon thread (see ``app/workers/tasks.py``). If a worker is killed hard, the
heartbeat stops; a background loop in the API marks such jobs ``failed`` once
``updated_at`` is older than ``job_stale_seconds``. No schema change: this reuses
the existing ``updated_at`` column.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.config import settings
from app.database import async_session
from app.models.database import Job, JobStatus

logger = logging.getLogger(__name__)


def _utcnow_naive() -> datetime:
    """Naive UTC, matching how SQLite stores DateTime values."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def reap_stale_jobs() -> int:
    """Mark processing jobs with a stale heartbeat as failed. Returns the count."""
    cutoff = _utcnow_naive() - timedelta(seconds=settings.job_stale_seconds)
    async with async_session() as session:
        result = await session.execute(
            update(Job)
            .where(Job.status == JobStatus.PROCESSING, Job.updated_at < cutoff)
            .values(
                status=JobStatus.FAILED,
                error_message="Worker heartbeat lost — job marked failed (stale).",
                updated_at=_utcnow_naive(),
            )
        )
        await session.commit()
        count = result.rowcount or 0
    if count:
        logger.warning("Reaped %d stale processing job(s)", count)
    return count


async def reaper_loop() -> None:
    """Run :func:`reap_stale_jobs` forever on the configured interval."""
    while True:
        try:
            await reap_stale_jobs()
        except Exception:
            logger.exception("Stale-job reaper iteration failed")
        await asyncio.sleep(settings.job_reaper_interval_seconds)
