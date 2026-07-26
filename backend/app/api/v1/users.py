import uuid
from typing import List
from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user, get_current_admin_user, get_user_service
from app.models.user import User
from app.schemas.auth import (
    UserResponse,
    InviteUserRequest,
    UserUpdateRole,
    UserStatusUpdate,
    UserProfileUpdate,
    ChangePasswordRequest,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=List[UserResponse])
async def list_users(
    admin: User = Depends(get_current_admin_user),
    user_service: UserService = Depends(get_user_service),
):
    """List all team members within the caller's organization (Admin only)."""
    return await user_service.list_users(organization_id=admin.organization_id)


@router.post("/invite", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def invite_user(
    req: InviteUserRequest,
    admin: User = Depends(get_current_admin_user),
    user_service: UserService = Depends(get_user_service),
):
    """Invite a new team user into the organization (Admin only)."""
    return await user_service.invite_user(organization_id=admin.organization_id, req=req)


@router.patch("/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: uuid.UUID,
    req: UserUpdateRole,
    admin: User = Depends(get_current_admin_user),
    user_service: UserService = Depends(get_user_service),
):
    """Update a team member's role (Admin only)."""
    return await user_service.update_user_role(
        organization_id=admin.organization_id,
        user_id=user_id,
        req=req,
        current_user_id=admin.id,
    )


@router.patch("/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: uuid.UUID,
    req: UserStatusUpdate,
    admin: User = Depends(get_current_admin_user),
    user_service: UserService = Depends(get_user_service),
):
    """Suspend, block or reactivate a team member account (Admin only)."""
    return await user_service.update_user_status(
        organization_id=admin.organization_id,
        user_id=user_id,
        req=req,
        current_user_id=admin.id,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    admin: User = Depends(get_current_admin_user),
    user_service: UserService = Depends(get_user_service),
):
    """Revoke and delete a team user account (Admin only)."""
    await user_service.delete_user(
        organization_id=admin.organization_id,
        user_id=user_id,
        current_user_id=admin.id,
    )


@router.patch("/me/profile", response_model=UserResponse)
async def update_profile(
    req: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    """Update current user's display name and email address."""
    return await user_service.update_profile(current_user=current_user, req=req)


@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    """Change current user's account password."""
    await user_service.change_password(current_user=current_user, req=req)
