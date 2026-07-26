import uuid
from typing import List, Optional
from sqlalchemy import String, Text, Integer, Float, Boolean, UUID, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class EvaluationTemplate(Base, TimestampMixin):
    __tablename__ = "evaluation_templates"
    __table_args__ = (
        # Prevents the concurrent-activation race where two templates end up
        # is_active=True for the same org, which crashes get_active_template()
        # (scalar_one_or_none() raises MultipleResultsFound).
        Index(
            "uq_one_active_template_per_org",
            "organization_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    parameters: Mapped[List["EvaluationParameter"]] = relationship(
        "EvaluationParameter",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="EvaluationParameter.display_order",
    )
    sections: Mapped[List["ExtractionSection"]] = relationship(
        "ExtractionSection",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="ExtractionSection.display_order",
    )


class EvaluationParameter(Base, TimestampMixin):
    __tablename__ = "evaluation_parameters"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluation_templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_instructions: Mapped[str] = mapped_column(Text, nullable=False)
    weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=1.0)
    min_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_score: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationship
    template: Mapped["EvaluationTemplate"] = relationship(
        "EvaluationTemplate", back_populates="parameters"
    )


class ExtractionSection(Base):
    __tablename__ = "extraction_sections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluation_templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_instructions: Mapped[str] = mapped_column(Text, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationship
    template: Mapped["EvaluationTemplate"] = relationship(
        "EvaluationTemplate", back_populates="sections"
    )
