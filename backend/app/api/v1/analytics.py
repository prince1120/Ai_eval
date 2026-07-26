import uuid
from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.user import User
from app.api.deps import require_role
from app.repositories.llm_cost_repository import LLMCostRepository

router = APIRouter()


@router.get("/llm-summary", response_model=Dict[str, Any])
async def get_llm_summary_stats(
    user_id: Optional[uuid.UUID] = Query(None, description="Filter by evaluator/user ID"),
    date_preset: Optional[str] = Query(None, description="Date filter preset: today, yesterday, 7days, 30days, all"),
    current_user: User = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db_session),
):
    """Get aggregated LLM token usage and USD spend summary stats for the organization (Admin-Only)."""
    cost_repo = LLMCostRepository(db)
    return await cost_repo.get_summary_stats(current_user.organization_id, user_id=user_id, date_preset=date_preset)


@router.get("/llm-breakdown", response_model=List[Dict[str, Any]])
async def get_llm_model_breakdown(
    user_id: Optional[uuid.UUID] = Query(None, description="Filter by evaluator/user ID"),
    date_preset: Optional[str] = Query(None, description="Date filter preset: today, yesterday, 7days, 30days, all"),
    current_user: User = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db_session),
):
    """Get token usage & USD cost breakdown grouped by LLM model & provider (Admin-Only)."""
    cost_repo = LLMCostRepository(db)
    return await cost_repo.get_model_breakdown(current_user.organization_id, user_id=user_id, date_preset=date_preset)


@router.get("/llm-logs", response_model=List[Dict[str, Any]])
async def list_llm_cost_logs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    model_name: Optional[str] = None,
    user_id: Optional[uuid.UUID] = Query(None, description="Filter by evaluator/user ID"),
    date_preset: Optional[str] = Query(None, description="Date filter preset: today, yesterday, 7days, 30days, all"),
    current_user: User = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db_session),
):
    """Get paginated individual LLM request audit logs with token, latency, and cost details (Admin-Only)."""
    cost_repo = LLMCostRepository(db)
    logs = await cost_repo.list_logs(
        organization_id=current_user.organization_id,
        limit=limit,
        offset=offset,
        model_name=model_name,
        user_id=user_id,
        date_preset=date_preset,
    )

    return [
        {
            "id": str(log.id),
            "user_id": str(log.user_id) if log.user_id else None,
            "analysis_run_id": str(log.analysis_run_id) if log.analysis_run_id else None,
            "transcript_id": str(log.transcript_id) if log.transcript_id else None,
            "source_call_id": log.transcript.source_call_id if log.transcript else None,
            "action": log.action,
            "provider": log.provider,
            "model_name": log.model_name,
            "prompt_tokens": log.prompt_tokens,
            "completion_tokens": log.completion_tokens,
            "total_tokens": log.total_tokens,
            "input_cost_usd": float(log.input_cost_usd),
            "output_cost_usd": float(log.output_cost_usd),
            "total_cost_usd": float(log.total_cost_usd),
            "latency_ms": log.latency_ms,
            "status": log.status,
            "error_message": log.error_message,
            "created_at": log.created_at.isoformat(),
            "user_email": log.user.email if log.user else "System",
            "user_name": log.user.full_name if log.user else None,
        }
        for log in logs
    ]
