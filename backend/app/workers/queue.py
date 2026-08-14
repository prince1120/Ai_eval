"""Queue wiring: Redis connection settings and enqueue helpers.

The API process only ever enqueues; all provider calls happen in the worker
process defined in app/workers/jobs.py.
"""
import logging
from typing import Any, Optional
from urllib.parse import urlparse

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import settings

logger = logging.getLogger(__name__)

TRANSCRIBE_JOB = "transcribe_audio_job"
ANALYZE_JOB = "run_analysis_job"

_pool: Optional[ArqRedis] = None


def redis_settings() -> RedisSettings:
    parsed = urlparse(settings.REDIS_URL)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        password=parsed.password,
        database=int(parsed.path.lstrip("/") or 0),
        ssl=parsed.scheme == "rediss",
    )


async def get_queue() -> ArqRedis:
    """Lazily create and reuse a single connection pool per process."""
    global _pool
    if _pool is None:
        _pool = await create_pool(redis_settings())
    return _pool


async def close_queue() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


async def enqueue(job_name: str, *args: Any, **kwargs: Any):
    """Enqueue a job, raising if Redis is unreachable.

    Failing loudly is deliberate: silently dropping the job would leave a
    transcript stuck in 'queued' with nothing ever picking it up, which is the
    exact failure mode the queue exists to eliminate.
    """
    pool = await get_queue()
    job = await pool.enqueue_job(job_name, *args, **kwargs)
    logger.info(f"Enqueued {job_name} as job {getattr(job, 'job_id', 'unknown')}")
    return job
