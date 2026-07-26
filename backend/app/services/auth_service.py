from fastapi import HTTPException, status

from app.core.security import hash_password, verify_password, create_access_token
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserResponse, OrganizationResponse


class AuthService:

    def __init__(
        self,
        org_repo: OrganizationRepository,
        user_repo: UserRepository,
    ):
        self.org_repo = org_repo
        self.user_repo = user_repo

    async def register(self, req: RegisterRequest) -> TokenResponse:
        existing_user = await self.user_repo.get_by_email(req.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists",
            )

        org = await self.org_repo.create(name=req.organization_name)

        hashed = hash_password(req.password)
        user = await self.user_repo.create(
            organization_id=org.id,
            email=req.email,
            hashed_password=hashed,
            role="admin",
        )

        token = create_access_token(
            subject=str(user.id),
            organization_id=str(org.id),
            role=user.role,
        )

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user=UserResponse.model_validate(user),
            organization=OrganizationResponse.model_validate(org),
        )

    async def login(self, req: LoginRequest) -> TokenResponse:
        user = await self.user_repo.get_by_email(req.email)
        if not user or not verify_password(req.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if hasattr(user, "is_active") and not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been suspended/blocked by your workspace administrator.",
            )

        org = await self.org_repo.get_by_id(user.organization_id)
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found",
            )

        token = create_access_token(
            subject=str(user.id),
            organization_id=str(org.id),
            role=user.role,
        )

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user=UserResponse.model_validate(user),
            organization=OrganizationResponse.model_validate(org),
        )
