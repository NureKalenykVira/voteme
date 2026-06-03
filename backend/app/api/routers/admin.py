import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_role
from app.core.enums import Role
from app.models.user import User
from app.schemas.admin import (
    AdminElectionListResponse,
    AdminElectionResponse,
    AdminUserListResponse,
    AdminUserResponse,
    CreateUserRequest,
    PatchUserRoleRequest,
    RestoreResponse,
    SettingsResponse,
    SettingsUpdateRequest,
    StatsResponse,
)
from app.services.admin_service import AdminService

router = APIRouter(tags=["Admin"])

_admin_service = AdminService()


@router.get(
    "/users",
    response_model=AdminUserListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all users (admin only)",
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Not admin"},
    },
)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: Role | None = Query(None),
    search: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.global_admin)),
) -> AdminUserListResponse:
    items, total = await _admin_service.list_users(session, page, page_size, role, search)
    return AdminUserListResponse(
        items=[AdminUserResponse.model_validate(u) for u in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/users",
    response_model=AdminUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user (admin only)",
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Not admin"},
        409: {"description": "Email already exists"},
    },
)
async def create_user(
    payload: CreateUserRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.global_admin)),
) -> AdminUserResponse:
    user = await _admin_service.create_user(session, payload, current_user.id)
    return AdminUserResponse.model_validate(user)


@router.patch(
    "/users/{user_id}",
    response_model=AdminUserResponse,
    status_code=status.HTTP_200_OK,
    summary="Change user role (admin only)",
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Not admin"},
        404: {"description": "User not found"},
    },
)
async def patch_user_role(
    user_id: uuid.UUID,
    payload: PatchUserRoleRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.global_admin)),
) -> AdminUserResponse:
    user = await _admin_service.patch_user_role(session, user_id, payload.role, current_user.id)
    return AdminUserResponse.model_validate(user)


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a user (admin only)",
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Not admin or self-delete attempted"},
        404: {"description": "User not found"},
    },
)
async def delete_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.global_admin)),
) -> None:
    await _admin_service.delete_user(session, user_id, current_user.id)


@router.delete(
    "/elections/{voting_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Force-delete any election (admin only)",
    description="Soft-deletes any election regardless of status. Admin privilege only.",
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Not admin"},
        404: {"description": "Election not found"},
    },
)
async def force_delete_election(
    voting_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.global_admin)),
) -> None:
    await _admin_service.force_delete_voting(session, voting_id, current_user.id)


@router.get(
    "/elections",
    response_model=AdminElectionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all elections with organizer info (admin only)",
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Not admin"},
    },
)
async def list_elections(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.global_admin)),
) -> AdminElectionListResponse:
    items, total = await _admin_service.list_elections(session, page, page_size, status_filter, search)
    return AdminElectionListResponse(
        items=[AdminElectionResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/stats",
    response_model=StatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get platform statistics (admin only)",
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Not admin"},
    },
)
async def get_stats(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.global_admin)),
) -> StatsResponse:
    return await _admin_service.get_stats(session)


@router.get(
    "/settings",
    response_model=SettingsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get system settings (admin only)",
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Not admin"},
    },
)
async def get_settings(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.global_admin)),
) -> SettingsResponse:
    return await _admin_service.get_settings(session)


@router.post(
    "/settings",
    response_model=SettingsResponse,
    status_code=status.HTTP_200_OK,
    summary="Update system settings (admin only)",
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Not admin"},
    },
)
async def update_settings(
    payload: SettingsUpdateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.global_admin)),
) -> SettingsResponse:
    return await _admin_service.update_settings(session, payload, current_user.id)


@router.post(
    "/backup",
    status_code=status.HTTP_200_OK,
    summary="Create a platform backup (admin only)",
    description="Creates a JSON backup of users (no passwords) and votings. Returns filename and created_at.",
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Not admin"},
    },
)
async def create_backup(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.global_admin)),
) -> dict:
    return await _admin_service.create_backup(session, current_user.id)


@router.get(
    "/backup/latest",
    summary="Download the latest backup file (admin only)",
    description="Returns the most recent backup JSON file as a file download.",
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Not admin"},
        404: {"description": "No backup available"},
    },
)
async def get_latest_backup(
    current_user: User = Depends(require_role(Role.global_admin)),
) -> FileResponse:
    path = _admin_service.get_latest_backup()
    if path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No backup available",
        )
    return FileResponse(path, media_type="application/json", filename=path.name)


@router.get(
    "/backup/info",
    status_code=200,
    summary="Get latest backup metadata (admin only)",
    description="Returns filename and created_at of the latest backup without downloading it. Returns null if no backup exists.",
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Not admin"},
    },
)
async def get_backup_info(
    current_user: User = Depends(require_role(Role.global_admin)),
) -> dict | None:
    return _admin_service.get_latest_backup_info()


@router.post(
    "/restore",
    response_model=RestoreResponse,
    status_code=status.HTTP_200_OK,
    summary="Restore a platform backup (admin only)",
    description=(
        "Imports users (without passwords — they must reset) and votings from a backup "
        "JSON file. Existing users and votings are skipped. Votes, ballots, voter lists, "
        "blockchain records and audit logs are not imported."
    ),
    responses={
        400: {"description": "Invalid or malformed backup file"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not admin"},
    },
)
async def restore_backup(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.global_admin)),
) -> RestoreResponse:
    raw = await file.read()
    return await _admin_service.restore_backup(session, raw, current_user.id)
