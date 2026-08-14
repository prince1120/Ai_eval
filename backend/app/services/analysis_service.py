import uuid
import logging
from collections import OrderedDict
from typing import List, Optional, Any, Dict
from fastapi import HTTPException, status

from app.repositories.transcript_repository import TranscriptRepository
from app.repositories.template_repository import TemplateRepository
from app.services.prompt_builder_service import PromptBuilderService
from app.schemas.transcript import (
    TranscriptCreate,
    TranscriptResponse,
    AnalysisRunResponse,
    TriggerAnalysisRequest,
)
from app.models.user import User

logger = logging.getLogger(__name__)

# Completed analysis runs are immutable, so caching them avoids re-hydrating
# 59 parameter rows on every report view. Bounded and FIFO-evicted: the previous
# plain dict was labelled "LRU" but had neither eviction nor a size limit, so it
# grew until the process ran out of memory. Still per-worker, which is fine
# because entries are immutable - a cache miss just costs one query.
COMPLETED_RUNS_CACHE: "OrderedDict[str, AnalysisRunResponse]" = OrderedDict()
COMPLETED_RUNS_CACHE_MAX = 256


def _cache_completed_run(key: str, value: AnalysisRunResponse) -> None:
    COMPLETED_RUNS_CACHE[key] = value
    COMPLETED_RUNS_CACHE.move_to_end(key)
    while len(COMPLETED_RUNS_CACHE) > COMPLETED_RUNS_CACHE_MAX:
        COMPLETED_RUNS_CACHE.popitem(last=False)


def invalidate_cached_run(organization_id: uuid.UUID, run_id: uuid.UUID) -> None:
    COMPLETED_RUNS_CACHE.pop(f"{organization_id}:{run_id}", None)


class AnalysisService:

    def __init__(
        self,
        transcript_repo: TranscriptRepository,
        template_repo: TemplateRepository,
        prompt_builder: PromptBuilderService,
    ):
        self.transcript_repo = transcript_repo
        self.template_repo = template_repo
        self.prompt_builder = prompt_builder

    async def create_transcript(
        self, organization_id: uuid.UUID, req: TranscriptCreate, user_id: Optional[uuid.UUID] = None
    ) -> TranscriptResponse:
        t = await self.transcript_repo.create_transcript(
            organization_id=organization_id,
            raw_text=req.raw_text,
            source_call_id=req.source_call_id,
            speaker_segments=req.speaker_segments,
            created_by=user_id,
            audio_file_key=req.audio_file_key,
            detected_language=req.detected_language,
            audio_duration_seconds=req.audio_duration_seconds,
            segments=req.segments,
            stt_confidence=req.stt_confidence,
            stt_quality_flags=req.stt_quality_flags,
            stt_model=req.stt_model,
            audio_sha256=req.audio_sha256,
        )
        refreshed = await self.transcript_repo.get_transcript(t.id, organization_id)
        return TranscriptResponse.model_validate(refreshed or t)

    async def create_pending_audio_transcript(
        self,
        organization_id: uuid.UUID,
        source_call_id: Optional[str],
        audio_file_key: str,
        audio_sha256: str,
        user_id: Optional[uuid.UUID] = None,
    ) -> TranscriptResponse:
        """Create the transcript row for a recording awaiting transcription.

        raw_text is empty until the worker fills it in, which is why this
        bypasses TranscriptCreate (whose min_length guard is right for
        text-submitted transcripts but wrong for queued audio).
        """
        t = await self.transcript_repo.create_transcript(
            organization_id=organization_id,
            raw_text="",
            source_call_id=source_call_id,
            created_by=user_id,
            audio_file_key=audio_file_key,
            audio_sha256=audio_sha256,
            status="queued",
        )
        refreshed = await self.transcript_repo.get_transcript(t.id, organization_id)
        return TranscriptResponse.model_validate(refreshed or t)

    async def find_duplicate_audio(
        self, organization_id: uuid.UUID, audio_sha256: str
    ) -> Optional[TranscriptResponse]:
        existing = await self.transcript_repo.find_by_audio_hash(
            organization_id, audio_sha256
        )
        return TranscriptResponse.model_validate(existing) if existing else None

    async def get_transcript(
        self, organization_id: uuid.UUID, transcript_id: uuid.UUID
    ) -> TranscriptResponse:
        t = await self.transcript_repo.get_transcript(transcript_id, organization_id)
        if not t:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Transcript not found"
            )
        return TranscriptResponse.model_validate(t)

    async def list_transcripts(
        self, organization_id: uuid.UUID, user: Optional[User] = None
    ) -> List[TranscriptResponse]:
        transcripts = await self.transcript_repo.list_transcripts(organization_id, user=user)
        return [TranscriptResponse.model_validate(t) for t in transcripts]

    async def delete_transcript(
        self, organization_id: uuid.UUID, transcript_id: uuid.UUID, storage_service: Optional[Any] = None
    ) -> None:
        t = await self.transcript_repo.get_transcript(transcript_id, organization_id)
        if not t:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Transcript not found"
            )

        # Also delete audio file from MinIO if stored
        if t.audio_file_key and storage_service:
            try:
                await storage_service.delete_audio(t.audio_file_key)
            except Exception as e:
                logger.warning(f"Could not delete MinIO audio '{t.audio_file_key}': {e}")

        await self.transcript_repo.delete_transcript(t)

    async def get_analysis_run(
        self, organization_id: uuid.UUID, run_id: uuid.UUID
    ) -> AnalysisRunResponse:
        cache_key = f"{organization_id}:{run_id}"
        cached = COMPLETED_RUNS_CACHE.get(cache_key)
        if cached is not None:
            COMPLETED_RUNS_CACHE.move_to_end(cache_key)
            return cached

        run = await self.transcript_repo.get_analysis_run(run_id, organization_id)
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found"
            )
        resp = AnalysisRunResponse.model_validate(run)
        if run.status == "done":
            _cache_completed_run(cache_key, resp)
        return resp

    async def list_analysis_runs(
        self,
        organization_id: uuid.UUID,
        transcript_id: Optional[uuid.UUID] = None,
        status_filter: Optional[str] = None,
        user: Optional[User] = None,
    ) -> List[AnalysisRunResponse]:
        runs = await self.transcript_repo.list_analysis_runs(
            organization_id=organization_id,
            transcript_id=transcript_id,
            status=status_filter,
            user=user,
        )
        return [AnalysisRunResponse.model_validate(r) for r in runs]

    async def trigger_analysis(
        self,
        organization_id: uuid.UUID,
        transcript_id: uuid.UUID,
        req: TriggerAnalysisRequest,
        user_id: Optional[uuid.UUID] = None,
    ) -> AnalysisRunResponse:
        transcript = await self.transcript_repo.get_transcript(transcript_id, organization_id)
        if not transcript:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Transcript not found"
            )

        if req.template_id:
            template = await self.template_repo.get_by_id(req.template_id, organization_id)
        else:
            template = await self.template_repo.get_active_template(organization_id)

        if not template:
            all_templates = await self.template_repo.list_by_organization(organization_id)
            if all_templates:
                target_tpl = all_templates[0]
                target_tpl.is_active = True
                await self.template_repo.session.flush()
                template = await self.template_repo.get_by_id(target_tpl.id, organization_id)
            else:
                new_tpl = await self.template_repo.create_template(
                    organization_id=organization_id,
                    name="Default Call Quality Scorecard",
                    description="Standard evaluation criteria for call quality, compliance, and comprehensive extractions",
                    version=1,
                    is_active=True,
                )
                await self.template_repo.add_parameter(
                    template_id=new_tpl.id,
                    name="Politeness & Professional Greeting",
                    ai_instructions="Evaluate agent polite greeting, professional tone of voice, agent identification, and empathy.",
                    weight=1.0,
                    min_score=0,
                    max_score=10,
                    is_required=True,
                    display_order=1,
                )
                # Seed default extraction sections for detailed call analysis
                default_sections = [
                    ("Call Summary & Purpose", "Extract primary reason for call, call category, and summary of interaction."),
                    ("Customer Sentiment", "Extract customer emotional state, sentiment trajectory (e.g. Frustrated to Satisfied), and key emotional phrases."),
                    ("Issue Details & Product", "Extract issue description, product/service name, ticket/order ID, and root cause."),
                    ("Resolution & Status", "Extract exact resolution provided, resolution status (Resolved/Unresolved/Escalated), and promised ETA."),
                    ("Follow-up & Commitments", "Extract any commitments made by agent or customer (callbacks, refunds, email sent) with deadlines."),
                    ("Hold & Transfer Details", "Extract if customer was put on hold, hold duration, transfer status, and reason for transfer."),
                    ("Compliance & Verification", "Extract customer authentication method, identity verification status, and disclosure compliance."),
                    ("Quality Flags & Escalations", "Extract any red flags: cancellation threats, legal/supervisor mentions, rude behavior, or policy violations."),
                ]
                for idx, (s_name, s_inst) in enumerate(default_sections, start=1):
                    await self.template_repo.add_section(
                        template_id=new_tpl.id,
                        name=s_name,
                        ai_instructions=s_inst,
                        display_order=idx,
                    )
                template = await self.template_repo.get_by_id(new_tpl.id, organization_id)

        run = await self.transcript_repo.create_analysis_run(
            organization_id=organization_id,
            transcript_id=transcript.id,
            template_id=template.id if template else None,
            template_version=template.version if template else 1,
            created_by=user_id or transcript.created_by,
        )

        # Hand off to the worker. This previously used asyncio.create_task,
        # which meant a redeploy, crash or unhandled exception left the run
        # stuck in "pending" forever with nothing to retry it, and put no
        # ceiling on how many provider calls could be in flight at once.
        from app.workers.queue import ANALYZE_JOB, enqueue

        await self.transcript_repo.session.commit()
        try:
            await enqueue(ANALYZE_JOB, str(run.id), str(organization_id))
        except Exception as err:
            logger.exception(f"Could not enqueue analysis run {run.id}: {err}")
            await self.transcript_repo.mark_run_failed(
                run.id, "Could not queue this evaluation. Please retry."
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Analysis could not be queued right now. Please retry shortly.",
            ) from err

        refreshed_run = await self.transcript_repo.get_analysis_run(run.id, organization_id)
        return AnalysisRunResponse.model_validate(refreshed_run or run)

    async def execute_analysis_job(self, run_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        run = await self.transcript_repo.get_analysis_run(run_id, organization_id)
        if not run:
            logger.error(f"Analysis run {run_id} not found")
            return

        run.status = "processing"
        await self.transcript_repo.session.flush()

        try:
            transcript = await self.transcript_repo.get_transcript(run.transcript_id, organization_id)
            template = await self.template_repo.get_by_id(run.template_id, organization_id) if run.template_id else None

            if not transcript:
                raise ValueError("Transcript missing for evaluation")

            if not template:
                template = await self.template_repo.get_active_template(organization_id)

            if not template:
                raise ValueError("No active evaluation template available")

            outcome = await self.prompt_builder.evaluate(
                template=template,
                raw_transcript=transcript.raw_text,
                organization_id=str(organization_id),
            )

            from app.repositories.llm_cost_repository import (
                LLMCostRepository,
                _provider_from_base_url,
            )
            from app.core.config import settings
            cost_repo = LLMCostRepository(self.transcript_repo.session)

            prompt_tokens = outcome.token_usage.get("prompt_tokens", 0)
            completion_tokens = outcome.token_usage.get("completion_tokens", 0)
            latency_ms = outcome.token_usage.get("latency_ms", 0)

            await cost_repo.log_request(
                organization_id=organization_id,
                user_id=run.created_by,
                analysis_run_id=run.id,
                transcript_id=run.transcript_id,
                action="scorecard_evaluation",
                provider=_provider_from_base_url(settings.LLM_BASE_URL),
                model_name=outcome.model_used,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                status="success",
            )

            await self.transcript_repo.save_run_results(
                run_id=run.id,
                overall_score=outcome.overall_score,
                parameter_results=outcome.parameter_results,
                section_results=outcome.section_results,
                raw_llm_response=outcome.raw_llm_response,
                llm_model_used=outcome.model_used,
                token_usage=outcome.token_usage,
            )

            transcript.status = "completed"
            await self.transcript_repo.session.flush()

        except Exception as exc:
            logger.exception(f"Error processing analysis run {run_id}: {exc}")
            try:
                from app.repositories.llm_cost_repository import (
                    LLMCostRepository,
                    _provider_from_base_url,
                )
                from app.core.config import settings
                cost_repo = LLMCostRepository(self.transcript_repo.session)
                await cost_repo.log_request(
                    organization_id=organization_id,
                    user_id=run.created_by,
                    analysis_run_id=run.id,
                    action="scorecard_evaluation",
                    provider=_provider_from_base_url(settings.LLM_BASE_URL),
                    model_name=settings.LLM_MODEL_NAME,
                    prompt_tokens=0,
                    completion_tokens=0,
                    latency_ms=0,
                    status="failed",
                    error_message=str(exc),
                )
            except Exception:
                pass
            await self.transcript_repo.mark_run_failed(run_id, str(exc))
