import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


# Parameter Schemas
class ParameterBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    ai_instructions: str = Field(..., min_length=5)
    weight: Optional[float] = 1.0
    min_score: int = 0
    max_score: int = 10
    is_required: bool = True
    display_order: int = 0


class ParameterCreate(ParameterBase):
    pass


class ParameterUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    ai_instructions: Optional[str] = None
    weight: Optional[float] = None
    min_score: Optional[int] = None
    max_score: Optional[int] = None
    is_required: Optional[bool] = None
    display_order: Optional[int] = None


class ParameterResponse(ParameterBase):
    id: uuid.UUID
    template_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ParameterReorderItem(BaseModel):
    id: uuid.UUID
    display_order: int


class ParameterReorderRequest(BaseModel):
    orders: List[ParameterReorderItem]


# Extraction Section Schemas
class SectionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    ai_instructions: str = Field(..., min_length=5)
    display_order: int = 0


class SectionCreate(SectionBase):
    pass


class SectionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    ai_instructions: Optional[str] = None
    display_order: Optional[int] = None


class SectionResponse(SectionBase):
    id: uuid.UUID
    template_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


# Template Schemas
class TemplateBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None


class TemplateCreate(TemplateBase):
    parameters: Optional[List[ParameterCreate]] = []
    sections: Optional[List[SectionCreate]] = []


class TemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None


class TemplateResponse(TemplateBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    version: int
    is_active: bool
    created_by: Optional[uuid.UUID]
    created_at: datetime
    parameters: List[ParameterResponse] = []
    sections: List[SectionResponse] = []

    model_config = ConfigDict(from_attributes=True)


class TemplateVersionSummary(BaseModel):
    id: uuid.UUID
    name: str
    version: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
