import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.auth import UserResponse


class TranscriptCreate(BaseModel):
    raw_text: str = Field(..., min_length=10)
    source_call_id: Optional[str] = None
    speaker_segments: Optional[Dict[str, Any]] = None
    audio_file_key: Optional[str] = None
    detected_language: Optional[str] = None
    audio_duration_seconds: Optional[float] = None
    segments: Optional[List[Dict[str, Any]]] = None
    stt_confidence: Optional[float] = None
    stt_quality_flags: Optional[List[str]] = None
    stt_model: Optional[str] = None
    audio_sha256: Optional[str] = None


class TranscriptResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_by: Optional[uuid.UUID] = None
    source_call_id: Optional[str]
    raw_text: str
    speaker_segments: Optional[Dict[str, Any]]
    status: str
    audio_file_key: Optional[str] = None
    detected_language: Optional[str] = None
    audio_duration_seconds: Optional[float] = None
    segments: Optional[List[Dict[str, Any]]] = None
    stt_confidence: Optional[float] = None
    stt_quality_flags: Optional[List[str]] = None
    stt_model: Optional[str] = None
    created_at: datetime
    creator: Optional[UserResponse] = None

    model_config = ConfigDict(from_attributes=True)


class ParameterResultResponse(BaseModel):
    id: uuid.UUID
    parameter_id: Optional[uuid.UUID]
    name_snapshot: str
    ai_instructions_snapshot: str
    score: float
    max_score: int
    reason: str
    evidence: Optional[str]
    suggestion: Optional[str]
    confidence: Optional[float]

    model_config = ConfigDict(from_attributes=True)


class SectionResultResponse(BaseModel):
    id: uuid.UUID
    section_id: Optional[uuid.UUID]
    name_snapshot: str
    extracted_content: str

    model_config = ConfigDict(from_attributes=True)


class AnalysisRunResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    transcript_id: uuid.UUID
    template_id: Optional[uuid.UUID] = None
    created_by: Optional[uuid.UUID] = None
    template_version: int
    overall_score: Optional[float]
    status: str
    raw_llm_response: Optional[Dict[str, Any]]
    llm_model_used: Optional[str]
    token_usage: Optional[Dict[str, Any]]
    error_message: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    creator: Optional[UserResponse] = None
    parameter_results: List[ParameterResultResponse] = []
    section_results: List[SectionResultResponse] = []

    model_config = ConfigDict(from_attributes=True)


class TriggerAnalysisRequest(BaseModel):
    template_id: Optional[uuid.UUID] = None  # If omitted, uses organization's active template
