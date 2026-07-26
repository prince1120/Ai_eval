import logging
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db_session

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

    response.status_code = status.HTTP_200_OK if db_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if db_healthy else "unhealthy",
        "project": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "database": "healthy" if db_healthy else "unhealthy",
    }
