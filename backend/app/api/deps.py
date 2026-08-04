import uuid
from typing import AsyncGenerator, List, Callable, Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.security import decode_access_token, AUTH_COOKIE_NAME
from app.models.user import User
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.repositories.template_repository import TemplateRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.services.auth_service import AuthService
from app.services.user_service import UserService
from app.services.template_service import TemplateService
from app.services.llm_client import LLMClient, OpenAICompatibleClient
from app.services.stt_service import STTService
from app.services.prompt_builder_service import PromptBuilderService
from app.services.analysis_service import AnalysisService
from app.services.assignment_service import AssignmentService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_token(
    request: Request,
    header_token: Optional[str] = Depends(oauth2_scheme),
) -> str:
    """Accepts a Bearer token (for API clients / Swagger) or the httpOnly
    auth cookie set on login (for the browser frontend)."""
    token = header_token or request.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


# Repositories Dependencies
def get_org_repository(db: AsyncSession = Depends(get_db_session)) -> OrganizationRepository:
    return OrganizationRepository(db)


def get_user_repository(db: AsyncSession = Depends(get_db_session)) -> UserRepository:
    return UserRepository(db)


def get_template_repository(db: AsyncSession = Depends(get_db_session)) -> TemplateRepository:
    return TemplateRepository(db)


def get_transcript_repository(db: AsyncSession = Depends(get_db_session)) -> TranscriptRepository:
    return TranscriptRepository(db)


# LLM, STT & Prompt Builder Dependencies
def get_llm_client() -> LLMClient:
    return OpenAICompatibleClient()


def get_stt_service() -> STTService:
    return STTService()


def get_storage_service():
    from app.services.storage_service import MinIOStorageService
    return MinIOStorageService()


def get_prompt_builder_service(
    llm_client: LLMClient = Depends(get_llm_client),
) -> PromptBuilderService:
    return PromptBuilderService(llm_client)


# Services Dependencies
def get_auth_service(
    org_repo: OrganizationRepository = Depends(get_org_repository),
    user_repo: UserRepository = Depends(get_user_repository),
) -> AuthService:
    return AuthService(org_repo, user_repo)


def get_user_service(
    user_repo: UserRepository = Depends(get_user_repository),
) -> UserService:
    return UserService(user_repo)


def get_template_service(
    template_repo: TemplateRepository = Depends(get_template_repository),
) -> TemplateService:
    return TemplateService(template_repo)


def get_analysis_service(
    transcript_repo: TranscriptRepository = Depends(get_transcript_repository),
    template_repo: TemplateRepository = Depends(get_template_repository),
    prompt_builder: PromptBuilderService = Depends(get_prompt_builder_service),
) -> AnalysisService:
    return AnalysisService(transcript_repo, template_repo, prompt_builder)


def get_assignment_service(
    db: AsyncSession = Depends(get_db_session),
) -> AssignmentService:
    return AssignmentService(db)


# Authentication Dependencies
async def get_current_user(
    token: str = Depends(get_token),
    user_repo: UserRepository = Depends(get_user_repository),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if not payload:
        raise credentials_exception

    user_id_str: str = payload.get("sub")
    if not user_id_str:
        raise credentials_exception

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise credentials_exception

    user = await user_repo.get_by_id(user_id)
    if not user:
        raise credentials_exception

    if hasattr(user, "is_active") and not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been suspended/blocked by your workspace administrator.",
        )

    return user


async def get_current_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


def require_role(allowed_roles: List[str]):
    """Dependency factory for checking user role permissions."""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: user role '{current_user.role}' is not authorized. Allowed roles: {allowed_roles}",
            )
        return current_user
    return role_checker
