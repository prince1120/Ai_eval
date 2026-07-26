import uuid
from typing import List
from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_admin_user, get_assignment_service
from app.models.user import User
from app.schemas.assignment import AssignEvaluatorsRequest, EvaluatorAssignmentResponse
from app.services.assignment_service import AssignmentService

router = APIRouter(prefix="/assignments", tags=["Assignments"])


@router.post("/viewers/{viewer_id}/evaluators", response_model=List[EvaluatorAssignmentResponse])
async def assign_evaluators_to_viewer(
    viewer_id: uuid.UUID,
    req: AssignEvaluatorsRequest,
    admin: User = Depends(get_current_admin_user),
    assignment_service: AssignmentService = Depends(get_assignment_service),
):
    """Assign one or more Evaluators to a Viewer (Admin only)."""
    return await assignment_service.assign_evaluators_to_viewer(
        organization_id=admin.organization_id,
        viewer_id=viewer_id,
        admin_id=admin.id,
        req=req,
    )


@router.get("/viewers/{viewer_id}/evaluators", response_model=List[EvaluatorAssignmentResponse])
async def list_assigned_evaluators(
    viewer_id: uuid.UUID,
    admin: User = Depends(get_current_admin_user),
    assignment_service: AssignmentService = Depends(get_assignment_service),
):
    """List all Evaluators assigned to a specific Viewer (Admin only)."""
    return await assignment_service.list_assigned_evaluators_for_viewer(
        organization_id=admin.organization_id,
        viewer_id=viewer_id,
    )
