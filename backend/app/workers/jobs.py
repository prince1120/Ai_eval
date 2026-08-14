"""Background jobs for transcription and evaluation.

Every provider call is gated by the quota guard in app/core/quota.py. When a
limit is exhausted the job is *deferred*, not failed - on a free tier, hitting
a rate limit is an ordinary scheduling event, not an error, and the user's
upload must survive it.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from arq import Retry

from app.core.config import settings
from app.core.quota import (
    LLM_FREE_TIER_LIMITS,
    WHISPER_FREE_TIER_LIMITS,
    QuotaGuard,
    RedisQuotaBackend,
)
from app.workers.queue import ANALYZE_JOB, TRANSCRIBE_JOB

logger = logging.getLogger(__name__)

# Transcript lifecycle. "uploaded" and "completed" predate the queue and are
# kept so existing rows and the current frontend keep working.
STATUS_QUEUED = "queued"
STATUS_TRANSCRIBING = "transcribing"
STATUS_TRANSCRIBED = "transcribed"
STATUS_TRANSCRIPTION_FAILED = "transcription_failed"


def _whisper_guard(ctx: Dict[str, Any]) -> QuotaGuard:
    return QuotaGuard("groq-whisper", WHISPER_FREE_TIER_LIMITS, RedisQuotaBackend(ctx["redis"]))


def _llm_guard(ctx: Dict[str, Any]) -> QuotaGuard:
    return QuotaGuard("llm", LLM_FREE_TIER_LIMITS, RedisQuotaBackend(ctx["redis"]))


async def transcribe_audio_job(
    ctx: Dict[str, Any],
    transcript_id: str,
    organization_id: str,
    audio_key: str,
    filename: str,
    auto_analyze: bool = False,
) -> Dict[str, Any]:
    """Transcribe a stored recording and persist segments plus quality signals."""
    from app.core.database import AsyncSessionLocal
    from app.repositories.transcript_repository import TranscriptRepository
    from app.services.storage_service import MinIOStorageService
    from app.services.stt_service import (
        STTService,
        estimate_audio_duration_seconds,
        whisper_cost_usd,
    )

    tid = uuid.UUID(transcript_id)
    oid = uuid.UUID(organization_id)
    storage = MinIOStorageService()
    audio = await storage.download_audio(audio_key)

    # Reserve quota against the raw duration before spending any of it. The
    # estimate is deliberately conservative; whatever the pipeline ends up not
    # using is handed back below.
    estimated_seconds = estimate_audio_duration_seconds(audio, filename)
    guard = _whisper_guard(ctx)
    reservation = {
        "whisper_requests_per_minute": 1,
        "whisper_audio_seconds_per_hour": int(estimated_seconds),
        "whisper_audio_seconds_per_day": int(estimated_seconds),
    }

    decision = await guard.consume(reservation)
    if not decision.allowed:
        defer = max(5.0, min(decision.retry_after_seconds + 1.0, 3600.0))
        logger.info(
            f"Transcript {tid}: STT quota '{decision.blocking_limit}' exhausted, "
            f"deferring {defer:.0f}s"
        )
        raise Retry(defer=defer)

    async with AsyncSessionLocal() as session:
        repo = TranscriptRepository(session)
        transcript = await repo.get_transcript(tid, oid)
        if not transcript:
            logger.error(f"Transcript {tid} vanished before transcription")
            await guard.release(reservation)
            return {"status": "missing"}
        transcript.status = STATUS_TRANSCRIBING
        await session.commit()

    try:
        stt = STTService()
        result = await stt.transcribe_audio(file_bytes=audio, filename=filename)
    except Exception as exc:
        # The provider may or may not have counted this attempt. Releasing the
        # reservation risks double-spending real quota, so it is left consumed:
        # over-counting costs throughput, under-counting costs 429s.
        job_try = ctx.get("job_try", 1)
        max_tries = ctx.get("max_tries", settings.WORKER_MAX_TRIES)
        final_attempt = job_try >= max_tries

        logger.warning(
            f"Transcript {tid}: transcription attempt {job_try}/{max_tries} "
            f"failed: {exc}"
        )

        # Only surface failure once arq has exhausted its retries. Marking it
        # failed on the first exception showed users a dead transcript while
        # the queue was still going to retry it - and provider 500s arrive in
        # bursts, so a later attempt often succeeds.
        if final_attempt:
            async with AsyncSessionLocal() as session:
                repo = TranscriptRepository(session)
                transcript = await repo.get_transcript(tid, oid)
                if transcript:
                    transcript.status = STATUS_TRANSCRIPTION_FAILED
                    await session.commit()
            logger.error(f"Transcript {tid}: giving up after {max_tries} attempts")
        else:
            # Back off before arq re-runs it, so a provider outage is not hit
            # again immediately.
            raise Retry(defer=min(30 * job_try, 300))
        raise

    # Hand back the difference between the conservative reservation and the
    # audio actually sent, so trimmed silence really does buy extra capacity.
    billable = result["stt_usage"].get("billable_seconds") or estimated_seconds
    refund = int(max(0.0, estimated_seconds - billable))
    if refund > 0:
        await guard.release({
            "whisper_audio_seconds_per_hour": refund,
            "whisper_audio_seconds_per_day": refund,
        })

    quality = result.get("quality", {})
    async with AsyncSessionLocal() as session:
        repo = TranscriptRepository(session)
        transcript = await repo.get_transcript(tid, oid)
        if not transcript:
            return {"status": "missing"}

        transcript.raw_text = result["raw_text"]
        # Speaker attribution is AI-inferred from text alone - there is no
        # acoustic voice separation - so the report must be able to say so
        # rather than presenting it as ground truth.
        transcript.speaker_segments = {
            "diarized_text": result["diarized_text"],
            "diarization_method": result.get("diarize_method"),
            "diarization_warning": result.get("diarize_warning"),
        }
        transcript.segments = result.get("segments")
        transcript.stt_confidence = quality.get("confidence")
        transcript.stt_quality_flags = quality.get("flags")
        transcript.stt_model = result.get("stt_model")
        transcript.detected_language = result.get("detected_language")
        transcript.audio_duration_seconds = result.get("audio_duration_seconds")
        transcript.audio_sha256 = result.get("audio_sha256")
        transcript.status = STATUS_TRANSCRIBED

        await _log_cost(
            session,
            organization_id=oid,
            user_id=transcript.created_by,
            transcript_id=tid,
            action="stt_whisper_transcription",
            provider="groq",
            model_name=result.get("stt_model") or settings.STT_MODEL_NAME,
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=result.get("stt_latency_ms", 0),
            override_total_cost_usd=result["stt_usage"].get("estimated_cost_usd", 0.0),
        )

        diarize_usage = result.get("diarize_usage") or {}
        if diarize_usage.get("total_tokens"):
            from app.repositories.llm_cost_repository import _provider_from_base_url

            await _log_cost(
                session,
                organization_id=oid,
                user_id=transcript.created_by,
                transcript_id=tid,
                action="speaker_diarization",
                provider=_provider_from_base_url(settings.LLM_BASE_URL),
                model_name=settings.DIARIZATION_MODEL_NAME or settings.LLM_MODEL_NAME,
                prompt_tokens=diarize_usage.get("prompt_tokens", 0),
                completion_tokens=diarize_usage.get("completion_tokens", 0),
                latency_ms=result.get("diarize_latency_ms", 0),
            )

        await session.commit()

    logger.info(
        f"Transcript {tid}: transcribed in {result.get('stt_latency_ms')}ms, "
        f"confidence={quality.get('confidence')}, flags={quality.get('flags')}, "
        f"billable={billable:.0f}s"
    )

    if auto_analyze:
        await _enqueue_analysis(ctx, tid, oid)

    return {
        "status": "ok",
        "confidence": quality.get("confidence"),
        "billable_seconds": billable,
    }


async def _enqueue_analysis(ctx: Dict[str, Any], transcript_id: uuid.UUID, organization_id: uuid.UUID) -> None:
    """Create the analysis run row, then queue the evaluation."""
    from app.core.database import AsyncSessionLocal
    from app.repositories.template_repository import TemplateRepository
    from app.repositories.transcript_repository import TranscriptRepository

    async with AsyncSessionLocal() as session:
        template_repo = TemplateRepository(session)
        template = await template_repo.get_active_template(organization_id)
        if not template:
            # Fall back to any template the org has, matching what the manual
            # "Run AI Evaluation" path does. Silently skipping meant a user who
            # ticked "automatically run evaluation" got a transcript and no
            # scorecard, with nothing anywhere explaining why.
            available = await template_repo.list_by_organization(organization_id)
            template = available[0] if available else None

        if not template:
            logger.warning(
                f"Transcript {transcript_id}: organization has no evaluation "
                "template at all, skipping auto-analysis"
            )
            return

        repo = TranscriptRepository(session)
        transcript = await repo.get_transcript(transcript_id, organization_id)
        run = await repo.create_analysis_run(
            organization_id=organization_id,
            transcript_id=transcript_id,
            template_id=template.id,
            template_version=template.version,
            created_by=transcript.created_by if transcript else None,
        )
        run_id = run.id
        await session.commit()

    await ctx["redis"].enqueue_job(ANALYZE_JOB, str(run_id), str(organization_id))


async def run_analysis_job(
    ctx: Dict[str, Any], run_id: str, organization_id: str
) -> Dict[str, Any]:
    """Score a transcript against its template, gated on LLM token quota."""
    from app.core.database import AsyncSessionLocal
    from app.repositories.template_repository import TemplateRepository
    from app.repositories.transcript_repository import TranscriptRepository
    from app.services.analysis_service import AnalysisService
    from app.services.llm_client import OpenAICompatibleClient
    from app.services.prompt_builder_service import PromptBuilderService

    rid = uuid.UUID(run_id)
    oid = uuid.UUID(organization_id)

    # Roughly size the request so the token-per-minute limit is respected
    # before the call rather than after a 429. ~1 token per 3 characters is a
    # reasonable approximation for mixed Devanagari/Latin text.
    async with AsyncSessionLocal() as session:
        repo = TranscriptRepository(session)
        run = await repo.get_analysis_run(rid, oid)
        if not run:
            logger.error(f"Analysis run {rid} not found")
            return {"status": "missing"}
        transcript = await repo.get_transcript(run.transcript_id, oid)
        estimated_tokens = int(len(transcript.raw_text or "") / 3) * 2 if transcript else 4_000

    guard = _llm_guard(ctx)
    reservation = {
        "llm_requests_per_minute": 1,
        "llm_tokens_per_minute": estimated_tokens,
        "llm_tokens_per_day": estimated_tokens,
    }
    decision = await guard.consume(reservation)
    if not decision.allowed:
        defer = max(5.0, min(decision.retry_after_seconds + 1.0, 3600.0))
        logger.info(
            f"Run {rid}: LLM quota '{decision.blocking_limit}' exhausted, "
            f"deferring {defer:.0f}s"
        )
        raise Retry(defer=defer)

    async with AsyncSessionLocal() as session:
        service = AnalysisService(
            transcript_repo=TranscriptRepository(session),
            template_repo=TemplateRepository(session),
            prompt_builder=PromptBuilderService(OpenAICompatibleClient()),
        )
        await service.execute_analysis_job(rid, oid)
        await session.commit()

    return {"status": "ok"}


async def _log_cost(session, **kwargs) -> None:
    """Best-effort cost logging - never fail a job over bookkeeping."""
    from app.repositories.llm_cost_repository import LLMCostRepository

    try:
        await LLMCostRepository(session).log_request(**kwargs)
    except Exception:
        logger.exception("Failed to record cost log entry")


async def startup(ctx: Dict[str, Any]) -> None:
    logger.info("Worker starting up")


async def shutdown(ctx: Dict[str, Any]) -> None:
    logger.info("Worker shutting down")


class WorkerSettings:
    """arq entrypoint: `arq app.workers.jobs.WorkerSettings`."""

    from app.workers.queue import redis_settings as _redis_settings

    functions = [transcribe_audio_job, run_analysis_job]
    redis_settings = _redis_settings()
    on_startup = startup
    on_shutdown = shutdown
    # Provider calls are slow and quota-limited, so a small pool keeps the
    # worker from stampeding the rate limiter.
    max_jobs = settings.WORKER_MAX_JOBS
    job_timeout = settings.WORKER_JOB_TIMEOUT
    max_tries = settings.WORKER_MAX_TRIES
    # Keep finished job results long enough for the API to report on them.
    keep_result = 3600
