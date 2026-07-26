import uuid
from typing import List
from fastapi import HTTPException, status

from app.core.security import hash_password, verify_password
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    UserCreate,
    UserResponse,
    InviteUserRequest,
    UserUpdateRole,
    UserProfileUpdate,
    ChangePasswordRequest,
    UserStatusUpdate,
)
from app.models.user import User


class UserService:

    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def invite_user(self, organization_id: uuid.UUID, req: InviteUserRequest) -> UserResponse:
        existing = await self.user_repo.get_by_email(req.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists",
            )

        hashed = hash_password(req.password)
        user = await self.user_repo.create(
            organization_id=organization_id,
            email=req.email,
            full_name=req.full_name,
            hashed_password=hashed,
            role=req.role,
        )
        return UserResponse.model_validate(user)

    async def list_users(self, organization_id: uuid.UUID) -> List[UserResponse]:
        users = await self.user_repo.list_by_organization(organization_id)
        return [UserResponse.model_validate(u) for u in users]

    async def update_user_role(
        self, organization_id: uuid.UUID, user_id: uuid.UUID, req: UserUpdateRole, current_user_id: uuid.UUID
    ) -> UserResponse:
        user = await self.user_repo.get_by_id(user_id, organization_id=organization_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in organization",
            )

        if user.id == current_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot change your own admin role",
            )

        user.role = req.role
        updated_user = await self.user_repo.update(user)
        return UserResponse.model_validate(updated_user)

    async def update_user_status(
        self, organization_id: uuid.UUID, user_id: uuid.UUID, req: UserStatusUpdate, current_user_id: uuid.UUID
    ) -> UserResponse:
        user = await self.user_repo.get_by_id(user_id, organization_id=organization_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in organization",
            )

        if user.id == current_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot suspend/block your own admin account",
            )

        user.is_active = req.is_active
        updated_user = await self.user_repo.update(user)
        return UserResponse.model_validate(updated_user)

    async def delete_user(
        self, organization_id: uuid.UUID, user_id: uuid.UUID, current_user_id: uuid.UUID
    ) -> None:
        user = await self.user_repo.get_by_id(user_id, organization_id=organization_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in organization",
            )

        if user.id == current_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot delete your own account from the team page. Use account settings.",
            )

        await self.user_repo.delete(user)

    async def update_profile(self, current_user: User, req: UserProfileUpdate) -> UserResponse:
        if req.email and req.email != current_user.email:
            existing = await self.user_repo.get_by_email(req.email)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email address is already in use",
                )
            current_user.email = req.email

        if req.full_name is not None:
            current_user.full_name = req.full_name

        updated_user = await self.user_repo.update(current_user)
        return UserResponse.model_validate(updated_user)

    async def change_password(self, current_user: User, req: ChangePasswordRequest) -> None:
        if not verify_password(req.current_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )

        current_user.hashed_password = hash_password(req.new_password)
        await self.user_repo.update(current_user)
