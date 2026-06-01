import aiofiles
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.repositories.election_auditor_repository import (
    ElectionAuditorRepository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    BecomeOrganizerResponse,
    ConfirmEmailResponse,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)
from app.services.auth_service import AuthService


router = APIRouter(tags=["Auth"])

_auth_service = AuthService()
_user_repo = UserRepository()
_election_auditor_repo = ElectionAuditorRepository()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    responses={
        409: {"description": "Email already registered"},
        422: {"description": "Validation error"},
    },
)
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_db),
) -> UserResponse:
    user = await _auth_service.register(session, payload)
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Log in and obtain a JWT access token",
    responses={
        401: {"description": "Invalid credentials"},
        403: {"description": "Email not confirmed"},
    },
)
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    token = await _auth_service.login(session, payload)
    return TokenResponse(access_token=token)


@router.get(
    "/confirm-email",
    response_model=ConfirmEmailResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm a user's email by token",
    responses={
        404: {"description": "Invalid confirmation token"},
    },
)
async def confirm_email(
    token: str = Query(..., min_length=1),
    session: AsyncSession = Depends(get_db),
) -> ConfirmEmailResponse:
    await _auth_service.confirm_email(session, token)
    return ConfirmEmailResponse(message="Email confirmed successfully")


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the currently authenticated user",
    responses={
        401: {"description": "Missing or invalid token"},
    },
)
async def me(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    auditor_ids = await _election_auditor_repo.list_voting_ids_for_user(
        session, current_user.id
    )
    resp = UserResponse.model_validate(current_user)
    resp.is_election_auditor = len(auditor_ids) > 0
    return resp


@router.patch(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update current user profile",
    responses={
        401: {"description": "Missing or invalid token"},
    },
)
async def update_profile(
    payload: UpdateProfileRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    user = await _auth_service.update_profile(session, current_user, payload)
    auditor_ids = await _election_auditor_repo.list_voting_ids_for_user(
        session, user.id
    )
    resp = UserResponse.model_validate(user)
    resp.is_election_auditor = len(auditor_ids) > 0
    return resp


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete (soft) current user account",
    responses={
        401: {"description": "Missing or invalid token"},
    },
)
async def delete_account(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    await _auth_service.delete_account(session, current_user)


@router.post(
    "/forgot-password",
    response_model=ConfirmEmailResponse,
    status_code=status.HTTP_200_OK,
    summary="Request a password reset email",
    responses={
        500: {"description": "Failed to send reset email"},
    },
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_db),
) -> ConfirmEmailResponse:
    await _auth_service.request_password_reset(session, payload.email)
    return ConfirmEmailResponse(message="If that email is registered, a reset link has been sent")


@router.post(
    "/reset-password",
    response_model=ConfirmEmailResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset password using a token",
    responses={
        400: {"description": "Invalid or expired reset token"},
        500: {"description": "Internal error"},
    },
)
async def reset_password(
    payload: ResetPasswordRequest,
    session: AsyncSession = Depends(get_db),
) -> ConfirmEmailResponse:
    await _auth_service.reset_password(session, payload.token, payload.new_password)
    return ConfirmEmailResponse(message="Password updated successfully")


_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
_EXT_MAP = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
_AVATARS_DIR = Path("uploads/avatars")


@router.post(
    "/me/avatar",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload profile avatar",
    responses={
        400: {"description": "Invalid file type"},
        401: {"description": "Missing or invalid token"},
    },
)
async def upload_avatar(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG, PNG, and WebP images are allowed",
        )

    ext = _EXT_MAP[file.content_type]
    _AVATARS_DIR.mkdir(parents=True, exist_ok=True)
    file_path = _AVATARS_DIR / f"{current_user.id}{ext}"

    contents = await file.read()
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(contents)

    avatar_url = f"/uploads/avatars/{current_user.id}{ext}"
    user = await _user_repo.update(session, current_user, avatar_url=avatar_url)
    await session.commit()
    await session.refresh(user)
    return UserResponse.model_validate(user)


@router.post(
    "/become-organizer",
    response_model=BecomeOrganizerResponse,
    status_code=status.HTTP_200_OK,
    summary="Upgrade current user role from voter to organizer",
    responses={
        401: {"description": "Missing or invalid token"},
        403: {"description": "Email confirmation required to become an organizer"},
        409: {"description": "Role is already organizer or higher"},
    },
)
async def become_organizer(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BecomeOrganizerResponse:
    new_token, user = await _auth_service.become_organizer(session, current_user)
    return BecomeOrganizerResponse(
        access_token=new_token,
        user=UserResponse.model_validate(user),
    )
