import logging
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status, UploadFile, File, Form, Query

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db_session
from app.core.limiter import limiter
from app.api.deps import (
    get_current_user,
    require_role,
    get_analysis_service,
    get_storage_service,
)
from app.models.user import User
from app.schemas.transcript import (
    TranscriptCreate,
    TranscriptResponse,
    AnalysisRunResponse,
    TriggerAnalysisRequest,
)
from app.services.analysis_service import AnalysisService
from app.workers.queue import TRANSCRIBE_JOB, enqueue
from app.services.stt_service import sha256_digest
from app.services.storage_service import MinIOStorageService

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


@router.post("/upload-audio", response_model=TranscriptResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("20/minute")
async def upload_and_transcribe_audio(
    request: Request,
    file: UploadFile = File(...),
    auto_analyze: bool = Query(False, description="Automatically run LLM evaluation after transcription"),
    current_user: User = Depends(require_role(["admin", "evaluator"])),
    analysis_service: AnalysisService = Depends(get_analysis_service),
    storage_service: MinIOStorageService = Depends(get_storage_service),
    db: AsyncSession = Depends(get_db_session),
):
    """Store a call recording and queue it for transcription.

    Returns 202 with a transcript in the "queued" state; poll GET /transcripts/{id}
    (or its status field) until it reaches "transcribed" or "transcription_failed".
    """
    filename = file.filename or "uploaded_call.mp3"
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ".mp3"
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

    # Re-uploading a file that was already transcribed burns STT quota and
    # creates a duplicate call record, so short-circuit on a content match.
    audio_sha256 = sha256_digest(file_bytes)
    duplicate = await analysis_service.find_duplicate_audio(
        organization_id=current_user.organization_id, audio_sha256=audio_sha256
    )
    if duplicate:
        logger.info(
            f"Audio {audio_sha256[:12]} already transcribed as {duplicate.id}; "
            "returning existing transcript instead of re-running STT"
        )
        return duplicate

    # Store the recording BEFORE transcribing. Audio is the source of truth and
    # everything downstream is re-computable from it; if STT fails we still
    # want the file, and a storage outage must not silently discard it.
    audio_key = f"{current_user.organization_id}/{uuid.uuid4()}{extension}"
    try:
        audio_file_key: Optional[str] = await storage_service.upload_audio(
            key=audio_key,
            file_bytes=file_bytes,
            content_type=file.content_type or "audio/mpeg",
        )
    except Exception as err:
        logger.exception(f"Audio storage upload failed for {audio_key}: {err}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not store the audio recording. Please retry in a moment.",
        ) from err

    # Create the row in a pending state and hand the work to the queue. The
    # request returns immediately: transcription can take minutes, and on the
    # free tier it may be deferred for an hour waiting on quota. Neither should
    # be held open on an HTTP connection.
    transcript = await analysis_service.create_pending_audio_transcript(
        organization_id=current_user.organization_id,
        source_call_id=file.filename,
        audio_file_key=audio_file_key,
        audio_sha256=audio_sha256,
        user_id=current_user.id,
    )
    await db.commit()

    try:
        await enqueue(
            TRANSCRIBE_JOB,
            str(transcript.id),
            str(current_user.organization_id),
            audio_file_key,
            filename,
            auto_analyze,
        )
    except Exception as err:
        logger.exception(f"Could not enqueue transcription for {transcript.id}: {err}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The recording was saved but transcription could not be queued. "
                "Retry the analysis from the transcript page shortly."
            ),
        ) from err

    return transcript


@router.post("/{id}/retry-transcription", response_model=TranscriptResponse, status_code=status.HTTP_202_ACCEPTED)
async def retry_transcription(
    id: uuid.UUID,
    auto_analyze: bool = Query(False),
    current_user: User = Depends(require_role(["admin", "evaluator"])),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    """Re-queue transcription for a recording whose job failed or was lost."""
    transcript = await analysis_service.get_transcript(
        organization_id=current_user.organization_id, transcript_id=id
    )
    if not transcript.audio_file_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This transcript has no stored audio to transcribe.",
        )

    await enqueue(
        TRANSCRIBE_JOB,
        str(transcript.id),
        str(current_user.organization_id),
        transcript.audio_file_key,
        transcript.source_call_id or "recording.mp3",
        auto_analyze,
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


@router.get("/{id}/audio")
async def get_transcript_audio_url(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    analysis_service: AnalysisService = Depends(get_analysis_service),
    storage_service: MinIOStorageService = Depends(get_storage_service),
):
    """Get presigned URL for playing audio recording stored in MinIO."""
    t = await analysis_service.get_transcript(
        organization_id=current_user.organization_id, transcript_id=id
    )
    if not t.audio_file_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No audio recording attached to this transcript.",
        )
    url = await storage_service.get_presigned_url(t.audio_file_key, expiry_seconds=3600)
    return {"url": url, "expires_in": 3600}


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transcript(
    id: uuid.UUID,
    current_user: User = Depends(require_role(["admin"])),
    analysis_service: AnalysisService = Depends(get_analysis_service),
    storage_service: MinIOStorageService = Depends(get_storage_service),
):
    """Delete a transcript and remove its audio recording from MinIO (Admin only)."""
    await analysis_service.delete_transcript(
        organization_id=current_user.organization_id, transcript_id=id, storage_service=storage_service
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
