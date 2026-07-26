import uuid
from typing import List
from fastapi import HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.transcript import EvaluatorAssignment
from app.models.user import User
from app.schemas.assignment import AssignEvaluatorsRequest, EvaluatorAssignmentResponse
from app.schemas.auth import UserResponse


class AssignmentService:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def assign_evaluators_to_viewer(
        self,
        organization_id: uuid.UUID,
        viewer_id: uuid.UUID,
        admin_id: uuid.UUID,
        req: AssignEvaluatorsRequest,
    ) -> List[EvaluatorAssignmentResponse]:
        # 1. Verify target viewer exists in org
        res = await self.session.execute(
            select(User).where(User.id == viewer_id, User.organization_id == organization_id)
        )
        target_viewer = res.scalar_one_or_none()
        if not target_viewer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target user not found in organization",
            )

        # 2. Verify every requested evaluator belongs to the same organization
        if req.evaluator_ids:
            res = await self.session.execute(
                select(User.id).where(
                    User.id.in_(req.evaluator_ids),
                    User.organization_id == organization_id,
                )
            )
            valid_ids = {row[0] for row in res.all()}
            invalid_ids = set(req.evaluator_ids) - valid_ids
            if invalid_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Evaluator id(s) not found in organization: {sorted(str(i) for i in invalid_ids)}",
                )

        # 3. Delete existing assignments for this viewer
        await self.session.execute(
            delete(EvaluatorAssignment).where(
                EvaluatorAssignment.viewer_id == viewer_id,
                EvaluatorAssignment.organization_id == organization_id,
            )
        )

        # 4. Create new evaluator assignments
        new_assignments = []
        for eval_id in req.evaluator_ids:
            assign_record = EvaluatorAssignment(
                organization_id=organization_id,
                evaluator_id=eval_id,
                viewer_id=viewer_id,
                assigned_by=admin_id,
            )
            self.session.add(assign_record)
            new_assignments.append(assign_record)

        await self.session.flush()

        # 4. Fetch and return assigned evaluators
        return await self.list_assigned_evaluators_for_viewer(organization_id, viewer_id)

    async def list_assigned_evaluators_for_viewer(
        self, organization_id: uuid.UUID, viewer_id: uuid.UUID
    ) -> List[EvaluatorAssignmentResponse]:
        res = await self.session.execute(
            select(EvaluatorAssignment)
            .options(selectinload(EvaluatorAssignment.evaluator))
            .where(
                EvaluatorAssignment.viewer_id == viewer_id,
                EvaluatorAssignment.organization_id == organization_id,
            )
        )
        records = list(res.scalars().all())
        out = []
        for r in records:
            item = EvaluatorAssignmentResponse(
                id=r.id,
                organization_id=r.organization_id,
                evaluator_id=r.evaluator_id,
                viewer_id=r.viewer_id,
                assigned_by=r.assigned_by,
                created_at=r.created_at,
                evaluator=UserResponse.model_validate(r.evaluator) if r.evaluator else None,
            )
            out.append(item)
        return out
