import uuid
import logging
from typing import List, Optional
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
        )
        refreshed = await self.transcript_repo.get_transcript(t.id, organization_id)
        return TranscriptResponse.model_validate(refreshed or t)

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
        self, organization_id: uuid.UUID, transcript_id: uuid.UUID
    ) -> None:
        t = await self.transcript_repo.get_transcript(transcript_id, organization_id)
        if not t:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Transcript not found"
            )
        await self.transcript_repo.delete_transcript(t)

    async def get_analysis_run(
        self, organization_id: uuid.UUID, run_id: uuid.UUID
    ) -> AnalysisRunResponse:
        run = await self.transcript_repo.get_analysis_run(run_id, organization_id)
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found"
            )
        return AnalysisRunResponse.model_validate(run)

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
                    description="Standard evaluation criteria for call quality and compliance",
                    version=1,
                    is_active=True,
                )
                await self.template_repo.add_parameter(
                    template_id=new_tpl.id,
                    name="Politeness & Tone",
                    ai_instructions="Evaluate agent polite greeting, tone of voice, and customer empathy.",
                    weight=1.0,
                    min_score=0,
                    max_score=10,
                    is_required=True,
                    display_order=1,
                )
                template = await self.template_repo.get_by_id(new_tpl.id, organization_id)

        run = await self.transcript_repo.create_analysis_run(
            organization_id=organization_id,
            transcript_id=transcript.id,
            template_id=template.id if template else None,
            template_version=template.version if template else 1,
            created_by=user_id or transcript.created_by,
        )

        # Run the evaluation inline on the same session, then return the fully
        # populated run. Re-fetch via get_analysis_run() so parameter_results /
        # section_results are eager-loaded (selectinload) for the response - the
        # bare object from create_analysis_run() doesn't have them loaded, and
        # accessing them lazily during Pydantic validation raises MissingGreenlet.
        await self.execute_analysis_job(run.id, organization_id)

        refreshed_run = await self.transcript_repo.get_analysis_run(run.id, organization_id)
        return AnalysisRunResponse.model_validate(refreshed_run)

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

            from app.repositories.llm_cost_repository import LLMCostRepository
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
                provider="mistral",
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
                from app.repositories.llm_cost_repository import LLMCostRepository
                cost_repo = LLMCostRepository(self.transcript_repo.session)
                await cost_repo.log_request(
                    organization_id=organization_id,
                    user_id=run.created_by,
                    analysis_run_id=run.id,
                    action="scorecard_evaluation",
                    provider="mistral",
                    model_name="ministral-3b-2512",
                    prompt_tokens=0,
                    completion_tokens=0,
                    latency_ms=0,
                    status="failed",
                    error_message=str(exc),
                )
            except Exception:
                pass
            await self.transcript_repo.mark_run_failed(run_id, str(exc))
