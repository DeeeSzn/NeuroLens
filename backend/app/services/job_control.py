"""Redis-backed job control: cooperative cancellation.

Cancellation is a flag in Redis rather than a DB column so no schema change (and
therefore no migration) is needed. The worker checks it at progress checkpoints;
the API sets it via the cancel endpoint. Because the in-flight ``model.predict``
call is a single blocking operation, cancellation only takes effect at the next
checkpoint — it cannot interrupt inference itself.
"""

from __future__ import annotations

import redis
import redis.asyncio as aioredis

from app.config import settings


class JobCancelled(Exception):
    """Raised inside the worker when a cancel flag is observed."""


def _key(job_id: str) -> str:
    return f"neurolens:cancel:{job_id}"


_sync: redis.Redis | None = None
_async: aioredis.Redis | None = None


def _sync_client() -> redis.Redis:
    global _sync
    if _sync is None:
        _sync = redis.Redis.from_url(settings.redis_url)
    return _sync


def _async_client() -> aioredis.Redis:
    global _async
    if _async is None:
        _async = aioredis.Redis.from_url(settings.redis_url)
    return _async


# --- worker side (synchronous) ---------------------------------------------

def request_cancel(job_id: str) -> None:
    _sync_client().set(_key(job_id), "1", ex=settings.cancel_flag_ttl_seconds)


def is_cancelled(job_id: str) -> bool:
    return bool(_sync_client().exists(_key(job_id)))


def clear_cancel(job_id: str) -> None:
    _sync_client().delete(_key(job_id))


# --- API side (asynchronous) ------------------------------------------------

async def arequest_cancel(job_id: str) -> None:
    await _async_client().set(_key(job_id), "1", ex=settings.cancel_flag_ttl_seconds)


async def aclear_cancel(job_id: str) -> None:
    await _async_client().delete(_key(job_id))
