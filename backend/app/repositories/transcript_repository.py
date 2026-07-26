import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.transcript import (
    Transcript,
    AnalysisRun,
    ParameterResult,
    SectionResult,
    EvaluatorAssignment,
    TranscriptAssignment,
)
from app.models.user import User


class TranscriptRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_transcript(
        self,
        organization_id: uuid.UUID,
        raw_text: str,
        source_call_id: Optional[str] = None,
        speaker_segments: Optional[Dict[str, Any]] = None,
        created_by: Optional[uuid.UUID] = None,
    ) -> Transcript:
        transcript = Transcript(
            organization_id=organization_id,
            raw_text=raw_text,
            source_call_id=source_call_id,
            speaker_segments=speaker_segments,
            status="uploaded",
            created_by=created_by,
        )
        self.session.add(transcript)
        await self.session.flush()
        return transcript

    async def get_transcript(
        self, transcript_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Optional[Transcript]:
        result = await self.session.execute(
            select(Transcript)
            .options(selectinload(Transcript.creator))
            .where(
                Transcript.id == transcript_id,
                Transcript.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_accessible_evaluator_ids(
        self, user: User
    ) -> List[uuid.UUID]:
        """Fetch list of Evaluator IDs assigned to viewer/evaluator user."""
        res = await self.session.execute(
            select(EvaluatorAssignment.evaluator_id).where(
                EvaluatorAssignment.viewer_id == user.id,
                EvaluatorAssignment.organization_id == user.organization_id,
            )
        )
        return list(res.scalars().all())

    async def get_accessible_transcript_ids(
        self, user: User
    ) -> List[uuid.UUID]:
        """Fetch list of individually assigned Transcript IDs for user."""
        res = await self.session.execute(
            select(TranscriptAssignment.transcript_id).where(
                TranscriptAssignment.user_id == user.id,
                TranscriptAssignment.organization_id == user.organization_id,
            )
        )
        return list(res.scalars().all())

    async def list_transcripts(
        self, organization_id: uuid.UUID, user: Optional[User] = None
    ) -> List[Transcript]:
        query = select(Transcript).options(selectinload(Transcript.creator)).where(
            Transcript.organization_id == organization_id
        )

        if user and user.role != "admin":
            assigned_eval_ids = await self.get_accessible_evaluator_ids(user)
            assigned_trans_ids = await self.get_accessible_transcript_ids(user)

            filters = [
                Transcript.created_by == user.id,
                Transcript.created_by == None,  # Legacy calls without explicit created_by
            ]
            if assigned_eval_ids:
                filters.append(Transcript.created_by.in_(assigned_eval_ids))
            if assigned_trans_ids:
                filters.append(Transcript.id.in_(assigned_trans_ids))

            query = query.where(or_(*filters))

        query = query.order_by(Transcript.created_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def delete_transcript(self, transcript: Transcript) -> None:
        await self.session.delete(transcript)
        await self.session.flush()

    async def create_analysis_run(
        self,
        organization_id: uuid.UUID,
        transcript_id: uuid.UUID,
        template_id: Optional[uuid.UUID],
        template_version: int,
        created_by: Optional[uuid.UUID] = None,
    ) -> AnalysisRun:
        run = AnalysisRun(
            organization_id=organization_id,
            transcript_id=transcript_id,
            template_id=template_id,
            template_version=template_version,
            status="pending",
            created_by=created_by,
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_analysis_run(
        self, run_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Optional[AnalysisRun]:
        result = await self.session.execute(
            select(AnalysisRun)
            .options(
                selectinload(AnalysisRun.creator),
                selectinload(AnalysisRun.parameter_results),
                selectinload(AnalysisRun.section_results),
            )
            .where(
                AnalysisRun.id == run_id,
                AnalysisRun.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_analysis_runs(
        self,
        organization_id: uuid.UUID,
        transcript_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        user: Optional[User] = None,
    ) -> List[AnalysisRun]:
        user_role = getattr(user, "role", None) if user else None
        user_id = getattr(user, "id", None) if user else None

        query = (
            select(AnalysisRun)
            .options(
                selectinload(AnalysisRun.creator),
                selectinload(AnalysisRun.parameter_results),
                selectinload(AnalysisRun.section_results),
            )
            .where(AnalysisRun.organization_id == organization_id)
        )

        if user and user_role != "admin":
            assigned_eval_ids = await self.get_accessible_evaluator_ids(user)

            filters = [
                AnalysisRun.created_by == user_id,
                AnalysisRun.created_by == None,  # Legacy runs without explicit created_by
            ]
            if assigned_eval_ids:
                filters.append(AnalysisRun.created_by.in_(assigned_eval_ids))

            accessible_transcripts = await self.list_transcripts(organization_id, user)
            accessible_trans_ids = [t.id for t in accessible_transcripts]
            if accessible_trans_ids:
                filters.append(AnalysisRun.transcript_id.in_(accessible_trans_ids))

            query = query.where(or_(*filters))

        if transcript_id:
            query = query.where(AnalysisRun.transcript_id == transcript_id)
        if status:
            query = query.where(AnalysisRun.status == status)

        query = query.order_by(AnalysisRun.created_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def save_run_results(
        self,
        run_id: uuid.UUID,
        overall_score: float,
        parameter_results: List[Dict[str, Any]],
        section_results: List[Dict[str, Any]],
        raw_llm_response: Dict[str, Any],
        llm_model_used: str,
        token_usage: Dict[str, Any],
    ) -> AnalysisRun:
        result = await self.session.execute(
            select(AnalysisRun).where(AnalysisRun.id == run_id)
        )
        run = result.scalar_one()

        run.overall_score = overall_score
        run.status = "done"
        run.raw_llm_response = raw_llm_response
        run.llm_model_used = llm_model_used
        run.token_usage = token_usage
        run.completed_at = datetime.now(timezone.utc)

        # Save parameter results snapshots
        for p_res in parameter_results:
            pr = ParameterResult(
                analysis_run_id=run.id,
                parameter_id=p_res.get("parameter_id"),
                name_snapshot=p_res["name_snapshot"],
                ai_instructions_snapshot=p_res["ai_instructions_snapshot"],
                score=p_res["score"],
                max_score=p_res["max_score"],
                reason=p_res["reason"],
                evidence=p_res.get("evidence"),
                suggestion=p_res.get("suggestion"),
                confidence=p_res.get("confidence"),
            )
            self.session.add(pr)

        # Save extraction section results snapshots
        for s_res in section_results:
            sr = SectionResult(
                analysis_run_id=run.id,
                section_id=s_res.get("section_id"),
                name_snapshot=s_res["name_snapshot"],
                extracted_content=s_res["extracted_content"],
            )
            self.session.add(sr)

        await self.session.flush()
        await self.session.refresh(run, ["parameter_results", "section_results"])
        return run

    async def mark_run_failed(self, run_id: uuid.UUID, error_message: str) -> None:
        result = await self.session.execute(
            select(AnalysisRun).where(AnalysisRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        if run:
            run.status = "failed"
            run.error_message = error_message
            run.completed_at = datetime.now(timezone.utc)
            await self.session.flush()
