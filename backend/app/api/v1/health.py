import logging
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.core.config import settings
from app.core.database import get_db_session
from app.models.user import User
from app.workers.queue import get_queue

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check(response: Response, db: AsyncSession = Depends(get_db_session)):
    """Health check endpoint verifying app operational state and database connection.
    Returns 503 (not 200) when the DB is unreachable, so load balancers /
    orchestrator readiness probes stop routing traffic to this instance."""
    db_healthy = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning(f"Database health check failed: {exc}")
        db_healthy = False

    # Redis backs the job queue, so if it is down uploads are accepted and
    # stored but never transcribed. That must fail readiness, not pass quietly.
    redis_healthy = True
    try:
        pool = await get_queue()
        await pool.ping()
    except Exception as exc:
        logger.warning(f"Redis health check failed: {exc}")
        redis_healthy = False

    healthy = db_healthy and redis_healthy
    response.status_code = status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if healthy else "unhealthy",
        "project": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "database": "healthy" if db_healthy else "unhealthy",
        "queue": "healthy" if redis_healthy else "unhealthy",
    }


@router.get("/models")
async def active_models(current_user: User = Depends(get_current_user)):
    """Which models are actually running each stage.

    Read by the UI so the progress steps and reports name the real model
    instead of a hardcoded label that silently goes stale the moment the
    configuration changes.
    """
    from app.repositories.llm_cost_repository import (
        MODEL_PRICING,
        _provider_from_base_url,
    )

    def rates(name: str):
        entry = MODEL_PRICING.get((name or "").lower().strip())
        if not entry:
            return None
        return {"input_usd_per_1m": entry[0], "output_usd_per_1m": entry[1]}

    diarization_model = settings.DIARIZATION_MODEL_NAME or settings.LLM_MODEL_NAME
    return {
        "transcription": {
            "model": settings.STT_MODEL_NAME,
            "provider": "groq",
            "billing": "per audio-second",
        },
        "diarization": {
            "model": diarization_model,
            "provider": _provider_from_base_url(
                settings.DIARIZATION_BASE_URL or settings.LLM_BASE_URL
            ),
            "rates": rates(diarization_model),
        },
        "evaluation": {
            "model": settings.LLM_MODEL_NAME,
            "provider": _provider_from_base_url(settings.LLM_BASE_URL),
            "rates": rates(settings.LLM_MODEL_NAME),
        },
        "usd_to_inr_rate": settings.USD_TO_INR_RATE,
    }


@router.get("/quota")
async def quota_status(current_user: User = Depends(require_role(["admin"]))):
    """Remaining provider quota for the day, hour and minute.

    On a free tier this is the real capacity ceiling, so it needs to be visible
    before uploads start piling up in the queue rather than after.
    """
    from app.core.quota import (
        LLM_FREE_TIER_LIMITS,
        WHISPER_FREE_TIER_LIMITS,
        QuotaGuard,
        RedisQuotaBackend,
    )

    try:
        pool = await get_queue()
        backend = RedisQuotaBackend(pool)
        return {
            "whisper": await QuotaGuard("groq-whisper", WHISPER_FREE_TIER_LIMITS, backend).snapshot(),
            "llm": await QuotaGuard("llm", LLM_FREE_TIER_LIMITS, backend).snapshot(),
            "queued_jobs": await pool.zcard("arq:queue"),
        }
    except Exception as exc:
        logger.warning(f"Quota status unavailable: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Queue backend unavailable, quota cannot be read.",
        ) from exc
