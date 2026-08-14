import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.repositories.template_repository import TemplateRepository
from app.schemas.template import (
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    ParameterCreate,
    ParameterUpdate,
    ParameterResponse,
    ParameterReorderRequest,
    SectionCreate,
    SectionUpdate,
    SectionResponse,
    TemplateVersionSummary,
)

BPO_QA_PRESET_PARAMETERS = [
    # 1. Opening / Greeting (6)
    {"name": "Greets within expected time", "ai_instructions": "Check if agent greeted the caller promptly within the first ring or opening seconds of the call.", "weight": 1.0, "min_score": 0, "max_score": 10},
    {"name": "Uses standard company greeting script", "ai_instructions": "Check if agent used the official brand/company opening greeting script.", "weight": 1.0, "min_score": 0, "max_score": 10},
    {"name": "States agent name clearly", "ai_instructions": "Check if agent stated their name clearly during the opening introduction.", "weight": 1.0, "min_score": 0, "max_score": 10},
    {"name": "States company/department name", "ai_instructions": "Check if agent identified company or department name during opening.", "weight": 1.0, "min_score": 0, "max_score": 10},
    {"name": "Tone is warm and professional", "ai_instructions": "Evaluate if agent opening tone was welcoming, polite, warm, and professional.", "weight": 1.0, "min_score": 0, "max_score": 10},
    {"name": "Confirms customer's name/identity appropriately", "ai_instructions": "Check if agent acknowledged and addressed customer by their correct name.", "weight": 1.0, "min_score": 0, "max_score": 10},

    # 2. Identity & Verification (4)
    {"name": "Verifies customer identity per policy", "ai_instructions": "Check if agent verified required security credentials (account number, phone, DOB, OTP, etc.).", "weight": 2.0, "min_score": 0, "max_score": 10},
    {"name": "Follows correct verification sequence", "ai_instructions": "Check if identity verification steps were followed in the correct logical sequence.", "weight": 1.5, "min_score": 0, "max_score": 10},
    {"name": "Handles failed verification correctly", "ai_instructions": "If customer failed verification, evaluate if agent handled security failure according to protocol.", "weight": 1.5, "min_score": 0, "max_score": 10},
    {"name": "Maintains data privacy during verification", "ai_instructions": "Check if agent maintained strict PII data privacy without leaking sensitive info.", "weight": 2.0, "min_score": 0, "max_score": 10},

    # 3. Active Listening & Needs Assessment (7)
    {"name": "Asks open-ended discovery questions", "ai_instructions": "Evaluate if agent asked effective open questions to understand customer's inquiry.", "weight": 1.0, "min_score": 0, "max_score": 10},
    {"name": "Lets customer finish speaking without interrupting", "ai_instructions": "Check if agent listened patiently without interrupting or talking over the customer.", "weight": 1.5, "min_score": 0, "max_score": 10},
    {"name": "Paraphrases/confirms understanding of the issue", "ai_instructions": "Check if agent summarized or paraphrased the problem to confirm understanding.", "weight": 1.0, "min_score": 0, "max_score": 10},
    {"name": "Asks relevant probing/follow-up questions", "ai_instructions": "Check if agent asked appropriate clarifying or follow-up questions.", "weight": 1.0, "min_score": 0, "max_score": 10},
    {"name": "Identifies the real/root problem", "ai_instructions": "Check if agent uncovered the underlying root cause instead of just addressing surface symptoms.", "weight": 2.0, "min_score": 0, "max_score": 10},
    {"name": "Shows empathy for customer's situation", "ai_instructions": "Evaluate if agent expressed genuine empathy, understanding, and care for customer inconvenience.", "weight": 1.5, "min_score": 0, "max_score": 10},
    {"name": "Avoids asking customer to repeat already-given information", "ai_instructions": "Check if agent avoided making customer repeat details already provided.", "weight": 1.0, "min_score": 0, "max_score": 10},

    # 4. Problem Diagnosis (5)
    {"name": "Correctly categorizes the issue type", "ai_instructions": "Evaluate if agent correctly diagnosed and categorized the issue.", "weight": 1.0, "min_score": 0, "max_score": 10},
    {"name": "Uses appropriate tools/systems to investigate", "ai_instructions": "Check if agent checked tools, databases, or order records to investigate.", "weight": 1.0, "min_score": 0, "max_score": 10},
    {"name": "Explains findings back to customer clearly", "ai_instructions": "Check if agent clearly communicated diagnostic findings to customer.", "weight": 1.0, "min_score": 0, "max_score": 10},
    {"name": "Checks account/order/history before responding", "ai_instructions": "Check if agent reviewed customer history before suggesting solutions.", "weight": 1.5, "min_score": 0, "max_score": 10},
    {"name": "Avoids guessing — confirms facts before proceeding", "ai_instructions": "Check if agent verified facts accurately rather than guessing or giving speculative answers.", "weight": 1.5, "min_score": 0, "max_score": 10},

    # 5. Problem Resolution (8)
    {"name": "Offers a correct and complete solution", "ai_instructions": "Check if agent provided a correct, complete, and accurate resolution.", "weight": 2.5, "min_score": 0, "max_score": 10},
    {"name": "Explains solution steps clearly", "ai_instructions": "Evaluate if solution steps and instructions were explained clearly.", "weight": 1.5, "min_score": 0, "max_score": 10},
    {"name": "Offers alternatives if primary solution isn't available", "ai_instructions": "Check if agent offered viable alternative solutions when primary options were unavailable.", "weight": 1.0, "min_score": 0, "max_score": 10},
    {"name": "Sets accurate expectations (timelines, next steps)", "ai_instructions": "Check if agent set realistic resolution timelines and next steps.", "weight": 1.5, "min_score": 0, "max_score": 10},
    {"name": "Resolves issue on first contact (FCR) where possible", "ai_instructions": "Check if issue was resolved completely on the first contact without requiring callbacks.", "weight": 2.0, "min_score": 0, "max_score": 10},
    {"name": "Follows correct escalation process if unresolved", "ai_instructions": "If unresolved, check if agent escalated the ticket/issue to correct supervisor/department.", "weight": 1.5, "min_score": 0, "max_score": 10},
    {"name": "Confirms customer understood/accepted the solution", "ai_instructions": "Check if agent confirmed customer agreed with and understood resolution.", "weight": 1.0, "min_score": 0, "max_score": 10},
    {"name": "Avoids overpromising (no false commitments)", "ai_instructions": "Check if agent avoided making false promises or unauthorized commitments.", "weight": 2.0, "min_score": 0, "max_score": 10},

    # 6. Product/Service Knowledge (4)
    {"name": "Demonstrates accurate product/policy knowledge", "ai_instructions": "Evaluate agent subject-matter expertise and policy understanding.", "weight": 1.5, "min_score": 0, "max_score": 10},
    {"name": "Avoids providing incorrect information", "ai_instructions": "Check if agent avoided giving inaccurate, misleading, or outdated information.", "weight": 2.0, "min_score": 0, "max_score": 10},
    {"name": "Cross-sell/upsell attempted where appropriate", "ai_instructions": "If relevant, check if agent offered relevant product upgrades or value-add features.", "weight": 0.5, "min_score": 0, "max_score": 10},
    {"name": "Correctly explains pricing/terms/policies", "ai_instructions": "Check if agent clearly explained relevant billing, pricing, or contract terms.", "weight": 1.5, "min_score": 0, "max_score": 10},

    # 7. Compliance & Risk (6)
    {"name": "Follows mandatory disclosure/disclaimer script", "ai_instructions": "Check if agent read required legal or regulatory disclosure disclaimers.", "weight": 3.0, "min_score": 0, "max_score": 10},
    {"name": "No prohibited language or promises used", "ai_instructions": "Check if agent avoided prohibited terms, guarantees, or compliance violations.", "weight": 3.0, "min_score": 0, "max_score": 10},
    {"name": "Handles sensitive/PII data per compliance rules", "ai_instructions": "Check if agent handled confidential credit card/PII data securely.", "weight": 3.0, "min_score": 0, "max_score": 10},
    {"name": "Follows recording/consent disclosure if required", "ai_instructions": "Check if call recording notification was communicated if applicable.", "weight": 2.0, "min_score": 0, "max_score": 10},
    {"name": "No discriminatory, rude, or inappropriate language", "ai_instructions": "Check if agent maintained respectful, non-discriminatory speech.", "weight": 3.0, "min_score": 0, "max_score": 10},
    {"name": "Adheres to industry-specific regulation", "ai_instructions": "Check adherence to regulatory rules (FDCPA, RBI, HIPAA, GDPR as applicable).", "weight": 3.0, "min_score": 0, "max_score": 10},

    # 8. Objection & Complaint Handling (5)
    {"name": "Acknowledges customer frustration/objection", "ai_instructions": "Check if agent acknowledged customer complaints or objections politely.", "weight": 1.5, "min_score": 0, "max_score": 10},
    {"name": "Stays calm and non-defensive under pressure", "ai_instructions": "Check if agent remained composed and calm during heated moments.", "weight": 1.5, "min_score": 0, "max_score": 10},
    {"name": "Offers resolution/de-escalation appropriately", "ai_instructions": "Check if agent used effective de-escalation techniques.", "weight": 1.5, "min_score": 0, "max_score": 10},
    {"name": "Doesn't argue or talk over the customer", "ai_instructions": "Check if agent avoided arguing or becoming defensive with customer.", "weight": 1.5, "min_score": 0, "max_score": 10},
    {"name": "Manages competitor mentions professionally", "ai_instructions": "Check if agent handled competitor mentions objectively and professionally.", "weight": 1.0, "min_score": 0, "max_score": 10},

    # 9. Communication Quality (5)
    {"name": "Clear speech pace and pronunciation", "ai_instructions": "Evaluate agent clarity, pace, and clarity of speech.", "weight": 1.0, "min_score": 0, "max_score": 10},
    {"name": "Uses simple, jargon-free language", "ai_instructions": "Check if agent used clear, jargon-free explanations.", "weight": 1.0, "min_score": 0, "max_score": 10},
    {"name": "Maintains professional tone throughout", "ai_instructions": "Evaluate if professional demeanor was maintained across the full call duration.", "weight": 1.0, "min_score": 0, "max_score": 10},
    {"name": "Appropriate hold/mute usage with notice given", "ai_instructions": "Check if agent asked permission before placing customer on hold/mute.", "weight": 1.0, "min_score": 0, "max_score": 10},
    {"name": "Minimal dead air / silence gaps", "ai_instructions": "Check if agent avoided awkward long periods of unannounced silence.", "weight": 1.0, "min_score": 0, "max_score": 10},

    # 10. Call Control & Efficiency (4)
    {"name": "Manages call duration efficiently", "ai_instructions": "Check if agent handled conversation efficiently without unnecessary padding.", "weight": 1.0, "min_score": 0, "max_score": 10},
    {"name": "Keeps conversation on-track without rambling", "ai_instructions": "Check if agent guided call flow constructively.", "weight": 1.0, "min_score": 0, "max_score": 10},
    {"name": "Avoids unnecessary transfers", "ai_instructions": "Check if agent avoided unnecessary call transfers.", "weight": 1.0, "min_score": 0, "max_score": 10},
    {"name": "Handles multitasking without losing engagement", "ai_instructions": "Check if agent maintained verbal engagement during system lookups.", "weight": 1.0, "min_score": 0, "max_score": 10},

    # 11. Closing (5)
    {"name": "Summarizes resolution/next steps before ending", "ai_instructions": "Check if agent recapped agreed action items before closing.", "weight": 1.0, "min_score": 0, "max_score": 10},
    {"name": "Asks if there's anything else needed", "ai_instructions": "Check if agent asked 'Is there anything else I can assist you with today?'.", "weight": 1.0, "min_score": 0, "max_score": 10},
    {"name": "Confirms follow-up action/ticket if applicable", "ai_instructions": "Check if ticket numbers or follow-up details were confirmed.", "weight": 1.0, "min_score": 0, "max_score": 10},
    {"name": "Thanks customer / proper closing script used", "ai_instructions": "Check if agent thanked customer and used proper closing branding script.", "weight": 1.0, "min_score": 0, "max_score": 10},
    {"name": "Ends call only after customer confirms satisfaction", "ai_instructions": "Check if agent waited for customer confirmation before disconnecting.", "weight": 1.0, "min_score": 0, "max_score": 10},
]

BPO_QA_PRESET_SECTIONS = [
    {"name": "Customer Sentiment", "ai_instructions": "Extract customer sentiment progression from beginning to end of call (e.g. Frustrated -> Satisfied)."},
    {"name": "Call Outcome", "ai_instructions": "Determine final call outcome: Resolved, Escalated, or Unresolved."},
    {"name": "Reason for Call", "ai_instructions": "Extract primary customer inquiry category and root cause complaint."},
    {"name": "Competitor Mentions", "ai_instructions": "Extract any competitor brand names or service comparisons stated by customer."},
    {"name": "Follow-Up Action Required", "ai_instructions": "Extract required follow-up tasks, callback promises, or open ticket numbers."},
    {"name": "Agent Talk-Time Ratio", "ai_instructions": "Estimate agent vs customer talk-time proportion and engagement balance."},
]


class TemplateService:

    def __init__(self, template_repo: TemplateRepository):
        self.template_repo = template_repo

    async def create_bpo_master_preset(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> TemplateResponse:
        """Create the complete 59-parameter BPO Call Center QA Master Template preset."""
        await self.template_repo.deactivate_all_for_organization(organization_id)
        template = await self.template_repo.create_template(
            organization_id=organization_id,
            name="BPO Call Center QA Master Framework (59 Parameters)",
            description="End-to-end 59-parameter call quality evaluation framework covering 11 call flow stages + 6 metadata extraction sections.",
            version=1,
            is_active=True,
            created_by=user_id,
        )

        for idx, p in enumerate(BPO_QA_PRESET_PARAMETERS):
            await self.template_repo.add_parameter(
                template_id=template.id,
                name=p["name"],
                description=None,
                ai_instructions=p["ai_instructions"],
                weight=p["weight"],
                min_score=p["min_score"],
                max_score=p["max_score"],
                is_required=True,
                display_order=idx,
            )

        for idx, s in enumerate(BPO_QA_PRESET_SECTIONS):
            await self.template_repo.add_section(
                template_id=template.id,
                name=s["name"],
                description=None,
                ai_instructions=s["ai_instructions"],
                display_order=idx,
            )

        refreshed = await self.template_repo.get_by_id(template.id, organization_id)
        return TemplateResponse.model_validate(refreshed)

    async def create_template(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        req: TemplateCreate,
    ) -> TemplateResponse:
        template = await self.template_repo.create_template(
            organization_id=organization_id,
            name=req.name,
            description=req.description,
            version=1,
            is_active=False,
            created_by=user_id,
        )

        if req.parameters:
            for idx, p in enumerate(req.parameters):
                order = p.display_order if p.display_order != 0 else idx
                await self.template_repo.add_parameter(
                    template_id=template.id,
                    name=p.name,
                    description=p.description,
                    ai_instructions=p.ai_instructions,
                    weight=p.weight,
                    min_score=p.min_score,
                    max_score=p.max_score,
                    is_required=p.is_required,
                    display_order=order,
                )

        if req.sections:
            for idx, s in enumerate(req.sections):
                order = s.display_order if s.display_order != 0 else idx
                await self.template_repo.add_section(
                    template_id=template.id,
                    name=s.name,
                    description=s.description,
                    ai_instructions=s.ai_instructions,
                    display_order=order,
                )

        refreshed = await self.template_repo.get_by_id(template.id, organization_id)
        return TemplateResponse.model_validate(refreshed)

    async def get_template(
        self, organization_id: uuid.UUID, template_id: uuid.UUID
    ) -> TemplateResponse:
        template = await self.template_repo.get_by_id(template_id, organization_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evaluation template not found",
            )
        return TemplateResponse.model_validate(template)

    async def list_templates(
        self, organization_id: uuid.UUID
    ) -> List[TemplateResponse]:
        templates = await self.template_repo.list_by_organization(organization_id)
        return [TemplateResponse.model_validate(t) for t in templates]

    async def delete_template(
        self, organization_id: uuid.UUID, template_id: uuid.UUID
    ) -> None:
        template = await self.template_repo.get_by_id(template_id, organization_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
            )
        await self.template_repo.delete_template(template)

    async def update_template(
        self,
        organization_id: uuid.UUID,
        template_id: uuid.UUID,
        user_id: uuid.UUID,
        req: TemplateUpdate,
    ) -> TemplateResponse:
        template = await self.template_repo.get_by_id(template_id, organization_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evaluation template not found",
            )

        if template.is_active:
            new_template = await self.template_repo.create_template(
                organization_id=organization_id,
                name=req.name or template.name,
                description=req.description if req.description is not None else template.description,
                version=template.version + 1,
                is_active=True,
                created_by=user_id,
            )
            template.is_active = False
            await self.template_repo.update_template(template)

            # Carry over whatever the caller sent; fall back to the previous
            # version's criteria only when the request omits them entirely.
            source_params = req.parameters if req.parameters is not None else template.parameters
            source_sections = req.sections if req.sections is not None else template.sections

            for idx, p in enumerate(source_params, start=1):
                await self.template_repo.add_parameter(
                    template_id=new_template.id,
                    name=p.name,
                    description=p.description,
                    ai_instructions=p.ai_instructions,
                    weight=p.weight,
                    min_score=p.min_score,
                    max_score=p.max_score,
                    is_required=p.is_required,
                    display_order=getattr(p, "display_order", None) or idx,
                )

            for idx, s in enumerate(source_sections, start=1):
                await self.template_repo.add_section(
                    template_id=new_template.id,
                    name=s.name,
                    description=s.description,
                    ai_instructions=s.ai_instructions,
                    display_order=getattr(s, "display_order", None) or idx,
                )

            refreshed = await self.template_repo.get_by_id(new_template.id, organization_id)
            return TemplateResponse.model_validate(refreshed)
        else:
            if req.name:
                template.name = req.name
            if req.description is not None:
                template.description = req.description

            if req.parameters is not None:
                await self._sync_parameters(template, req.parameters)
            if req.sections is not None:
                await self._sync_sections(template, req.sections)

            await self.template_repo.update_template(template)
            refreshed = await self.template_repo.get_by_id(template.id, organization_id)
            return TemplateResponse.model_validate(refreshed)

    async def _sync_parameters(self, template, incoming) -> None:
        """Make the template's parameters match the submitted list exactly.

        Matched by id so existing rows are updated in place: deleting and
        recreating would null out parameter_results.parameter_id on every
        historical run that referenced them.
        """
        existing = {p.id: p for p in template.parameters}
        seen: set = set()

        for idx, item in enumerate(incoming, start=1):
            order = item.display_order or idx
            current = existing.get(item.id) if item.id else None
            if current is not None:
                current.name = item.name
                current.description = item.description
                current.ai_instructions = item.ai_instructions
                current.weight = item.weight
                current.min_score = item.min_score
                current.max_score = item.max_score
                current.is_required = item.is_required
                current.display_order = order
                seen.add(current.id)
            else:
                # No id, or an id the editor generated client-side for a row
                # that was never persisted.
                await self.template_repo.add_parameter(
                    template_id=template.id,
                    name=item.name,
                    description=item.description,
                    ai_instructions=item.ai_instructions,
                    weight=item.weight,
                    min_score=item.min_score,
                    max_score=item.max_score,
                    is_required=item.is_required,
                    display_order=order,
                )

        for param_id, param in existing.items():
            if param_id not in seen:
                await self.template_repo.delete_parameter(param)

    async def _sync_sections(self, template, incoming) -> None:
        existing = {s.id: s for s in template.sections}
        seen: set = set()

        for idx, item in enumerate(incoming, start=1):
            order = item.display_order or idx
            current = existing.get(item.id) if item.id else None
            if current is not None:
                current.name = item.name
                current.description = item.description
                current.ai_instructions = item.ai_instructions
                current.display_order = order
                seen.add(current.id)
            else:
                await self.template_repo.add_section(
                    template_id=template.id,
                    name=item.name,
                    description=item.description,
                    ai_instructions=item.ai_instructions,
                    display_order=order,
                )

        for section_id, section in existing.items():
            if section_id not in seen:
                await self.template_repo.delete_section(section)

    async def activate_template(
        self, organization_id: uuid.UUID, template_id: uuid.UUID
    ) -> TemplateResponse:
        template = await self.template_repo.get_by_id(template_id, organization_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evaluation template not found",
            )

        await self.template_repo.deactivate_all_for_organization(organization_id)
        template.is_active = True
        try:
            updated = await self.template_repo.update_template(template)
        except IntegrityError:
            # uq_one_active_template_per_org caught a concurrent activation race.
            await self.template_repo.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another activation request is already in progress for this organization. Please retry.",
            )
        return TemplateResponse.model_validate(updated)

    async def add_parameter(
        self,
        organization_id: uuid.UUID,
        template_id: uuid.UUID,
        req: ParameterCreate,
    ) -> ParameterResponse:
        template = await self.template_repo.get_by_id(template_id, organization_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
            )

        param = await self.template_repo.add_parameter(
            template_id=template_id,
            name=req.name,
            description=req.description,
            ai_instructions=req.ai_instructions,
            weight=req.weight,
            min_score=req.min_score,
            max_score=req.max_score,
            is_required=req.is_required,
            display_order=req.display_order,
        )
        return ParameterResponse.model_validate(param)

    async def update_parameter(
        self,
        organization_id: uuid.UUID,
        template_id: uuid.UUID,
        parameter_id: uuid.UUID,
        req: ParameterUpdate,
    ) -> ParameterResponse:
        template = await self.template_repo.get_by_id(template_id, organization_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
            )

        param = await self.template_repo.get_parameter_by_id(parameter_id, template_id)
        if not param:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Parameter not found"
            )

        for key, val in req.model_dump(exclude_unset=True).items():
            setattr(param, key, val)

        await self.template_repo.session.flush()
        return ParameterResponse.model_validate(param)

    async def delete_parameter(
        self, organization_id: uuid.UUID, template_id: uuid.UUID, parameter_id: uuid.UUID
    ) -> None:
        template = await self.template_repo.get_by_id(template_id, organization_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
            )

        param = await self.template_repo.get_parameter_by_id(parameter_id, template_id)
        if not param:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Parameter not found"
            )

        await self.template_repo.delete_parameter(param)

    async def reorder_parameters(
        self,
        organization_id: uuid.UUID,
        template_id: uuid.UUID,
        req: ParameterReorderRequest,
    ) -> List[ParameterResponse]:
        template = await self.template_repo.get_by_id(template_id, organization_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
            )

        param_map = {p.id: p for p in template.parameters}
        for item in req.orders:
            if item.id in param_map:
                param_map[item.id].display_order = item.display_order

        await self.template_repo.session.flush()
        refreshed = await self.template_repo.get_by_id(template_id, organization_id)
        return [ParameterResponse.model_validate(p) for p in refreshed.parameters]

    async def add_section(
        self,
        organization_id: uuid.UUID,
        template_id: uuid.UUID,
        req: SectionCreate,
    ) -> SectionResponse:
        template = await self.template_repo.get_by_id(template_id, organization_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
            )

        section = await self.template_repo.add_section(
            template_id=template_id,
            name=req.name,
            description=req.description,
            ai_instructions=req.ai_instructions,
            display_order=req.display_order,
        )
        return SectionResponse.model_validate(section)

    async def delete_section(
        self, organization_id: uuid.UUID, template_id: uuid.UUID, section_id: uuid.UUID
    ) -> None:
        template = await self.template_repo.get_by_id(template_id, organization_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
            )

        section = await self.template_repo.get_section_by_id(section_id, template_id)
        if not section:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Section not found"
            )

        await self.template_repo.delete_section(section)

    async def list_template_versions(
        self, organization_id: uuid.UUID, template_id: uuid.UUID
    ) -> List[TemplateVersionSummary]:
        template = await self.template_repo.get_by_id(template_id, organization_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
            )

        versions = await self.template_repo.list_versions(organization_id, template.name)
        return [TemplateVersionSummary.model_validate(v) for v in versions]
