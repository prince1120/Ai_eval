import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_analysis_service
from app.models.user import User
from app.schemas.transcript import AnalysisRunResponse
from app.services.analysis_service import AnalysisService

router = APIRouter(prefix="/analysis-runs", tags=["Analysis Runs"])


@router.get("", response_model=List[AnalysisRunResponse])
async def list_analysis_runs(
    transcript_id: Optional[uuid.UUID] = Query(None, description="Filter by transcript ID"),
    status: Optional[str] = Query(None, description="Filter by status (pending/processing/done/failed)"),
    current_user: User = Depends(get_current_user),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    """List analysis runs, optionally filtering by transcript or status with RBAC access control."""
    return await analysis_service.list_analysis_runs(
        organization_id=current_user.organization_id,
        transcript_id=transcript_id,
        status_filter=status,
        user=current_user,
    )


@router.get("/{id}", response_model=AnalysisRunResponse)
async def get_analysis_run(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    """Get full status and detailed scoring results for an analysis run."""
    return await analysis_service.get_analysis_run(
        organization_id=current_user.organization_id, run_id=id
    )
