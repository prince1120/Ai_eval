import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Numeric, Text, DateTime, ForeignKey, Index, desc
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class LLMCostLog(Base):
    __tablename__ = "llm_cost_logs"
    __table_args__ = (
        Index("idx_llm_cost_logs_org_created", "organization_id", desc("created_at")),
        Index("idx_llm_cost_logs_model", "model_name"),
        Index("idx_llm_cost_logs_transcript", "transcript_id"),
        Index("idx_llm_cost_logs_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    analysis_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="SET NULL"), nullable=True
    )
    transcript_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transcripts.id", ondelete="SET NULL"), nullable=True
    )

    action: Mapped[str] = mapped_column(String(100), default="llm_call", nullable=False)
    provider: Mapped[str] = mapped_column(String(50), default="mistral", nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)

    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    input_cost_usd: Mapped[float] = mapped_column(Numeric(12, 6), default=0.0, nullable=False)
    output_cost_usd: Mapped[float] = mapped_column(Numeric(12, 6), default=0.0, nullable=False)
    total_cost_usd: Mapped[float] = mapped_column(Numeric(12, 6), default=0.0, nullable=False)

    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="success", nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    organization = relationship("Organization")
    user = relationship("User")
    analysis_run = relationship("AnalysisRun")
    transcript = relationship("Transcript")
