import logging
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status, UploadFile, File, Form, Query

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db_session
from app.core.limiter import limiter
from app.api.deps import get_current_user, require_role, get_analysis_service, get_stt_service
from app.models.user import User
from app.schemas.transcript import (
    TranscriptCreate,
    TranscriptResponse,
    AnalysisRunResponse,
    TriggerAnalysisRequest,
)
from app.services.analysis_service import AnalysisService
from app.services.stt_service import STTService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transcripts", tags=["Transcripts"])

MAX_AUDIO_UPLOAD_BYTES = 25 * 1024 * 1024  # matches Groq's Whisper API limit
ALLOWED_AUDIO_CONTENT_TYPES = {
    "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav", "audio/wave",
    "audio/mp4", "audio/x-m4a", "audio/m4a", "audio/webm", "audio/ogg",
}
ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".webm"}


@router.post("", response_model=TranscriptResponse, status_code=status.HTTP_201_CREATED)
async def create_transcript(
    req: TranscriptCreate,
    current_user: User = Depends(require_role(["admin", "evaluator"])),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    """Submit raw transcript text or call reference for analysis."""
    return await analysis_service.create_transcript(
        organization_id=current_user.organization_id, req=req, user_id=current_user.id
    )


@router.post("/upload-audio", response_model=TranscriptResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def upload_and_transcribe_audio(
    request: Request,
    file: UploadFile = File(...),
    auto_analyze: bool = Query(False, description="Automatically run LLM evaluation after transcription"),
    current_user: User = Depends(require_role(["admin", "evaluator"])),
    stt_service: STTService = Depends(get_stt_service),
    analysis_service: AnalysisService = Depends(get_analysis_service),
    db: AsyncSession = Depends(get_db_session),
):
    """Upload call audio file (.mp3, .wav, .m4a), transcribe with Whisper STT, and create transcript."""
    filename = file.filename or "uploaded_call.mp3"
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in ALLOWED_AUDIO_EXTENSIONS or (
        file.content_type and file.content_type not in ALLOWED_AUDIO_CONTENT_TYPES
    ):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported audio file type. Allowed: {', '.join(sorted(ALLOWED_AUDIO_EXTENSIONS))}",
        )

    file_bytes = await file.read(MAX_AUDIO_UPLOAD_BYTES + 1)
    if len(file_bytes) > MAX_AUDIO_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Audio file exceeds the {MAX_AUDIO_UPLOAD_BYTES // (1024 * 1024)}MB limit.",
        )

    stt_res = await stt_service.transcribe_audio(
        file_bytes=file_bytes, filename=filename
    )

    transcript = await analysis_service.create_transcript(
        organization_id=current_user.organization_id,
        req=TranscriptCreate(
            raw_text=stt_res["raw_text"],
            source_call_id=file.filename,
            speaker_segments={"diarized_text": stt_res["diarized_text"]},
        ),
        user_id=current_user.id,
    )

    # Record LLM Cost Logs for STT & Diarization
    try:
        from app.repositories.llm_cost_repository import LLMCostRepository
        cost_repo = LLMCostRepository(db)

        # 1. Log Groq Whisper STT (billed per audio-second, not per token - see stt_service.py)
        stt_usage = stt_res.get("stt_usage", {})
        await cost_repo.log_request(
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            transcript_id=transcript.id,
            action="stt_whisper_transcription",
            provider="groq",
            model_name="whisper-large-v3-turbo",
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=stt_res.get("stt_latency_ms", 0),
            status="success",
            override_total_cost_usd=stt_usage.get("estimated_cost_usd", 0),
        )

        # 2. Log Mistral Diarization
        diar_usage = stt_res.get("diarize_usage", {})
        if diar_usage and diar_usage.get("total_tokens", 0) > 0:
            await cost_repo.log_request(
                organization_id=current_user.organization_id,
                user_id=current_user.id,
                transcript_id=transcript.id,
                action="speaker_diarization",
                provider="mistral",
                model_name=settings.LLM_MODEL_NAME,
                prompt_tokens=diar_usage.get("prompt_tokens", 0),
                completion_tokens=diar_usage.get("completion_tokens", 0),
                latency_ms=stt_res.get("diarize_latency_ms", 0),
                status="success",
            )
    except Exception:
        logger.exception(
            f"Failed to record LLM cost logs for transcript {transcript.id}"
        )

    if auto_analyze:
        await analysis_service.trigger_analysis(
            organization_id=current_user.organization_id,
            transcript_id=transcript.id,
            req=TriggerAnalysisRequest(),
            user_id=current_user.id,
        )

    return transcript


@router.get("", response_model=List[TranscriptResponse])
async def list_transcripts(
    current_user: User = Depends(get_current_user),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    """List transcripts accessible to caller based on role & assignment mapping."""
    return await analysis_service.list_transcripts(
        organization_id=current_user.organization_id, user=current_user
    )


@router.get("/{id}", response_model=TranscriptResponse)
async def get_transcript(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    """Get transcript details by ID."""
    return await analysis_service.get_transcript(
        organization_id=current_user.organization_id, transcript_id=id
    )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transcript(
    id: uuid.UUID,
    current_user: User = Depends(require_role(["admin"])),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    """Delete a transcript (Admin only)."""
    await analysis_service.delete_transcript(
        organization_id=current_user.organization_id, transcript_id=id
    )


@router.post("/{id}/analyze", response_model=AnalysisRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_analysis(
    id: uuid.UUID,
    req: TriggerAnalysisRequest = TriggerAnalysisRequest(),
    current_user: User = Depends(require_role(["admin", "evaluator"])),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    """Run the AI evaluation against the organization's active template and
    return the completed analysis run with its parameter and section results."""
    return await analysis_service.trigger_analysis(
        organization_id=current_user.organization_id,
        transcript_id=id,
        req=req,
        user_id=current_user.id,
    )


@router.get("/{id}/analysis-runs", response_model=List[AnalysisRunResponse])
async def list_transcript_analysis_runs(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    """Get all historical analysis runs for a specific transcript across template versions."""
    return await analysis_service.list_analysis_runs(
        organization_id=current_user.organization_id, transcript_id=id, user=current_user
    )
