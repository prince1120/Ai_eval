import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.auth import UserResponse


class AssignEvaluatorsRequest(BaseModel):
    evaluator_ids: List[uuid.UUID]


class EvaluatorAssignmentResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    evaluator_id: uuid.UUID
    viewer_id: uuid.UUID
    assigned_by: Optional[uuid.UUID] = None
    created_at: datetime
    evaluator: Optional[UserResponse] = None

    model_config = ConfigDict(from_attributes=True)
