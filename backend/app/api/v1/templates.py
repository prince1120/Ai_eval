import uuid
from typing import List
from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user, get_current_admin_user, require_role, get_template_service
from app.models.user import User
from app.schemas.template import (
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    ParameterCreate,
    ParameterUpdate,
    ParameterResponse,
    ParameterReorderRequest,
    SectionCreate,
    SectionResponse,
    TemplateVersionSummary,
)
from app.services.template_service import TemplateService

router = APIRouter(prefix="/templates", tags=["Templates"])


@router.post("/seed-bpo-preset", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def seed_bpo_preset(
    current_user: User = Depends(get_current_admin_user),
    template_service: TemplateService = Depends(get_template_service),
):
    """Seed the 59-parameter BPO Call Center QA Master Scorecard preset (Admin only)."""
    return await template_service.create_bpo_master_preset(
        organization_id=current_user.organization_id,
        user_id=current_user.id,
    )


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    req: TemplateCreate,
    current_user: User = Depends(get_current_admin_user),
    template_service: TemplateService = Depends(get_template_service),
):
    """Create a new evaluation template with dynamic parameters and extraction sections (Admin only)."""
    return await template_service.create_template(
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        req=req,
    )


@router.get("", response_model=List[TemplateResponse])
async def list_templates(
    current_user: User = Depends(get_current_user),
    template_service: TemplateService = Depends(get_template_service),
):
    """List all evaluation templates defined for caller's organization."""
    return await template_service.list_templates(organization_id=current_user.organization_id)


@router.get("/{id}", response_model=TemplateResponse)
async def get_template(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    template_service: TemplateService = Depends(get_template_service),
):
    """Get a specific template by ID."""
    return await template_service.get_template(
        organization_id=current_user.organization_id, template_id=id
    )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    id: uuid.UUID,
    current_user: User = Depends(get_current_admin_user),
    template_service: TemplateService = Depends(get_template_service),
):
    """Delete an evaluation template (Admin only)."""
    await template_service.delete_template(
        organization_id=current_user.organization_id, template_id=id
    )


@router.put("/{id}", response_model=TemplateResponse)
async def update_template(
    id: uuid.UUID,
    req: TemplateUpdate,
    current_user: User = Depends(get_current_admin_user),
    template_service: TemplateService = Depends(get_template_service),
):
    """Update a template (Admin only). Creates a new version copy (v+1) if active."""
    return await template_service.update_template(
        organization_id=current_user.organization_id,
        template_id=id,
        user_id=current_user.id,
        req=req,
    )


@router.post("/{id}/activate", response_model=TemplateResponse)
async def activate_template(
    id: uuid.UUID,
    current_user: User = Depends(get_current_admin_user),
    template_service: TemplateService = Depends(get_template_service),
):
    """Set template as active for organization (Admin only)."""
    return await template_service.activate_template(
        organization_id=current_user.organization_id, template_id=id
    )


@router.post("/{id}/parameters", response_model=ParameterResponse, status_code=status.HTTP_201_CREATED)
async def add_parameter(
    id: uuid.UUID,
    req: ParameterCreate,
    current_user: User = Depends(get_current_admin_user),
    template_service: TemplateService = Depends(get_template_service),
):
    """Add a new evaluation parameter to template (Admin only)."""
    return await template_service.add_parameter(
        organization_id=current_user.organization_id,
        template_id=id,
        req=req,
    )


@router.put("/{id}/parameters/reorder", response_model=List[ParameterResponse])
async def reorder_parameters(
    id: uuid.UUID,
    req: ParameterReorderRequest,
    current_user: User = Depends(get_current_admin_user),
    template_service: TemplateService = Depends(get_template_service),
):
    """Reorder display position of parameters in template (Admin only)."""
    return await template_service.reorder_parameters(
        organization_id=current_user.organization_id,
        template_id=id,
        req=req,
    )


@router.put("/{id}/parameters/{param_id}", response_model=ParameterResponse)
async def update_parameter(
    id: uuid.UUID,
    param_id: uuid.UUID,
    req: ParameterUpdate,
    current_user: User = Depends(get_current_admin_user),
    template_service: TemplateService = Depends(get_template_service),
):
    """Update an existing parameter (Admin only)."""
    return await template_service.update_parameter(
        organization_id=current_user.organization_id,
        template_id=id,
        parameter_id=param_id,
        req=req,
    )


@router.delete("/{id}/parameters/{param_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_parameter(
    id: uuid.UUID,
    param_id: uuid.UUID,
    current_user: User = Depends(get_current_admin_user),
    template_service: TemplateService = Depends(get_template_service),
):
    """Remove a parameter from template (Admin only)."""
    await template_service.delete_parameter(
        organization_id=current_user.organization_id,
        template_id=id,
        parameter_id=param_id,
    )


@router.post("/{id}/sections", response_model=SectionResponse, status_code=status.HTTP_201_CREATED)
async def add_section(
    id: uuid.UUID,
    req: SectionCreate,
    current_user: User = Depends(get_current_admin_user),
    template_service: TemplateService = Depends(get_template_service),
):
    """Add a new extraction section to template (Admin only)."""
    return await template_service.add_section(
        organization_id=current_user.organization_id,
        template_id=id,
        req=req,
    )


@router.delete("/{id}/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_section(
    id: uuid.UUID,
    section_id: uuid.UUID,
    current_user: User = Depends(get_current_admin_user),
    template_service: TemplateService = Depends(get_template_service),
):
    """Remove an extraction section from template (Admin only)."""
    await template_service.delete_section(
        organization_id=current_user.organization_id,
        template_id=id,
        section_id=section_id,
    )


@router.get("/{id}/versions", response_model=List[TemplateVersionSummary])
async def list_template_versions(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    template_service: TemplateService = Depends(get_template_service),
):
    """List historical versions of template with same name."""
    return await template_service.list_template_versions(
        organization_id=current_user.organization_id, template_id=id
    )
