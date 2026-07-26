from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import get_auth_service, get_current_user
from app.core.config import settings
from app.core.security import set_auth_cookie, clear_auth_cookie
from app.core.limiter import limiter
from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(
    request: Request,
    req: RegisterRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Register a new Organization and its primary Admin user."""
    result = await auth_service.register(req)
    set_auth_cookie(response, result.access_token, settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return result


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    req: LoginRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Authenticate user with email and password, returning a JWT token."""
    result = await auth_service.login(req)
    set_auth_cookie(response, result.access_token, settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return result


@router.post("/logout")
async def logout(response: Response):
    """Clear the auth cookie set on login/register."""
    clear_auth_cookie(response)
    return {"detail": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """Get current authenticated user profile."""
    return UserResponse.model_validate(current_user)
