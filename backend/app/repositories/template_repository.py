import uuid
from typing import Optional, List
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.template import EvaluationTemplate, EvaluationParameter, ExtractionSection


class TemplateRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_template(
        self,
        organization_id: uuid.UUID,
        name: str,
        description: Optional[str] = None,
        version: int = 1,
        is_active: bool = False,
        created_by: Optional[uuid.UUID] = None,
    ) -> EvaluationTemplate:
        template = EvaluationTemplate(
            organization_id=organization_id,
            name=name,
            description=description,
            version=version,
            is_active=is_active,
            created_by=created_by,
        )
        self.session.add(template)
        await self.session.flush()
        return template

    async def get_by_id(
        self, template_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Optional[EvaluationTemplate]:
        result = await self.session.execute(
            select(EvaluationTemplate)
            .options(
                selectinload(EvaluationTemplate.parameters),
                selectinload(EvaluationTemplate.sections),
            )
            .where(
                EvaluationTemplate.id == template_id,
                EvaluationTemplate.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_active_template(
        self, organization_id: uuid.UUID
    ) -> Optional[EvaluationTemplate]:
        result = await self.session.execute(
            select(EvaluationTemplate)
            .options(
                selectinload(EvaluationTemplate.parameters),
                selectinload(EvaluationTemplate.sections),
            )
            .where(
                EvaluationTemplate.organization_id == organization_id,
                EvaluationTemplate.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_organization(
        self, organization_id: uuid.UUID
    ) -> List[EvaluationTemplate]:
        result = await self.session.execute(
            select(EvaluationTemplate)
            .options(
                selectinload(EvaluationTemplate.parameters),
                selectinload(EvaluationTemplate.sections),
            )
            .where(EvaluationTemplate.organization_id == organization_id)
            .order_by(EvaluationTemplate.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_versions(
        self, organization_id: uuid.UUID, template_name: str
    ) -> List[EvaluationTemplate]:
        result = await self.session.execute(
            select(EvaluationTemplate)
            .where(
                EvaluationTemplate.organization_id == organization_id,
                EvaluationTemplate.name == template_name,
            )
            .order_by(EvaluationTemplate.version.desc())
        )
        return list(result.scalars().all())

    async def deactivate_all_for_organization(self, organization_id: uuid.UUID) -> None:
        await self.session.execute(
            update(EvaluationTemplate)
            .where(EvaluationTemplate.organization_id == organization_id)
            .values(is_active=False)
        )
        await self.session.flush()

    async def delete_template(self, template: EvaluationTemplate) -> None:
        await self.session.delete(template)
        await self.session.flush()

    async def add_parameter(
        self,
        template_id: uuid.UUID,
        name: str,
        ai_instructions: str,
        description: Optional[str] = None,
        weight: Optional[float] = 1.0,
        min_score: int = 0,
        max_score: int = 10,
        is_required: bool = True,
        display_order: int = 0,
    ) -> EvaluationParameter:
        param = EvaluationParameter(
            template_id=template_id,
            name=name,
            description=description,
            ai_instructions=ai_instructions,
            weight=weight,
            min_score=min_score,
            max_score=max_score,
            is_required=is_required,
            display_order=display_order,
        )
        self.session.add(param)
        await self.session.flush()
        return param

    async def get_parameter_by_id(
        self, param_id: uuid.UUID, template_id: uuid.UUID
    ) -> Optional[EvaluationParameter]:
        result = await self.session.execute(
            select(EvaluationParameter).where(
                EvaluationParameter.id == param_id,
                EvaluationParameter.template_id == template_id,
            )
        )
        return result.scalar_one_or_none()

    async def delete_parameter(self, param: EvaluationParameter) -> None:
        await self.session.delete(param)
        await self.session.flush()

    async def add_section(
        self,
        template_id: uuid.UUID,
        name: str,
        ai_instructions: str,
        description: Optional[str] = None,
        display_order: int = 0,
    ) -> ExtractionSection:
        section = ExtractionSection(
            template_id=template_id,
            name=name,
            description=description,
            ai_instructions=ai_instructions,
            display_order=display_order,
        )
        self.session.add(section)
        await self.session.flush()
        return section

    async def get_section_by_id(
        self, section_id: uuid.UUID, template_id: uuid.UUID
    ) -> Optional[ExtractionSection]:
        result = await self.session.execute(
            select(ExtractionSection).where(
                ExtractionSection.id == section_id,
                ExtractionSection.template_id == template_id,
            )
        )
        return result.scalar_one_or_none()

    async def delete_section(self, section: ExtractionSection) -> None:
        await self.session.delete(section)
        await self.session.flush()

    async def update_template(self, template: EvaluationTemplate) -> EvaluationTemplate:
        await self.session.flush()
        return template
