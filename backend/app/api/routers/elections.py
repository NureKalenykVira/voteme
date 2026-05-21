import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_role
from app.core.enums import Role, VotingStatus
from app.models.user import User
from app.schemas.voting import (
    BallotOptionCreateRequest,
    BallotOptionResponse,
    BallotOptionUpdateRequest,
    VotingCreateRequest,
    VotingDetailResponse,
    VotingListResponse,
    VotingResponse,
    VotingUpdateRequest,
)
from app.services.voting_service import VotingService

router = APIRouter(tags=["Elections"])

_voting_service = VotingService()

_BALLOT_PHOTO_DIR = Path("uploads/ballot_options")
_ALLOWED_PHOTO_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
_PHOTO_EXT_MAP = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
_MAX_PHOTO_BYTES = 5 * 1024 * 1024


def _organizer_or_admin():
    return require_role(Role.organizer, Role.global_admin)


@router.post(
    "/",
    response_model=VotingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new election (draft)",
    responses={
        400: {"description": "Invalid date range"},
        401: {"description": "Missing or invalid token"},
        403: {"description": "Insufficient permissions"},
        422: {"description": "Validation error"},
    },
)
async def create_election(
    payload: VotingCreateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(_organizer_or_admin()),
) -> VotingResponse:
    voting = await _voting_service.create_voting(session, current_user, payload)
    return VotingResponse.model_validate(voting)


@router.get(
    "/",
    response_model=VotingListResponse,
    status_code=status.HTTP_200_OK,
    summary="List elections visible to the current user",
    responses={
        401: {"description": "Missing or invalid token"},
    },
)
async def list_elections(
    status_filter: VotingStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VotingListResponse:
    items, total = await _voting_service.list_votings(
        session, current_user, status_filter, page, page_size
    )
    return VotingListResponse(
        items=[VotingResponse.model_validate(v) for v in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{election_id}",
    response_model=VotingDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get election detail with ballot options",
    responses={
        401: {"description": "Missing or invalid token"},
        403: {"description": "Election is not visible"},
        404: {"description": "Election not found"},
    },
)
async def get_election(
    election_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VotingDetailResponse:
    voting, options = await _voting_service.get_voting_detail(
        session, current_user, election_id
    )
    return VotingDetailResponse(
        id=voting.id,
        title=voting.title,
        description=voting.description,
        access_type=voting.access_type,
        is_anonymous=voting.is_anonymous,
        invitation_code=voting.invitation_code,
        start_date_time=voting.start_date_time,
        end_date_time=voting.end_date_time,
        status=voting.status,
        created_by=voting.created_by,
        created_at=voting.created_at,
        updated_at=voting.updated_at,
        options=[BallotOptionResponse.model_validate(o) for o in options],
    )


@router.patch(
    "/{election_id}",
    response_model=VotingResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a draft election",
    responses={
        400: {"description": "Invalid date range"},
        401: {"description": "Missing or invalid token"},
        403: {"description": "Caller does not own this election"},
        404: {"description": "Election not found"},
        409: {"description": "Operation allowed only for draft elections"},
        422: {"description": "Validation error"},
    },
)
async def update_election(
    election_id: uuid.UUID,
    payload: VotingUpdateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(_organizer_or_admin()),
) -> VotingResponse:
    voting = await _voting_service.update_voting(
        session, current_user, election_id, payload
    )
    return VotingResponse.model_validate(voting)


@router.delete(
    "/{election_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a draft election",
    responses={
        401: {"description": "Missing or invalid token"},
        403: {"description": "Caller does not own this election"},
        404: {"description": "Election not found"},
        409: {"description": "Operation allowed only for draft elections"},
    },
)
async def delete_election(
    election_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(_organizer_or_admin()),
) -> None:
    await _voting_service.delete_voting(session, current_user, election_id)


@router.post(
    "/{election_id}/publish",
    response_model=VotingResponse,
    status_code=status.HTTP_200_OK,
    summary="Publish a draft election (FSM: draft -> published)",
    responses={
        401: {"description": "Missing or invalid token"},
        403: {"description": "Caller does not own this election"},
        404: {"description": "Election not found"},
        409: {"description": "Invalid state or missing prerequisites"},
    },
)
async def publish_election(
    election_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(_organizer_or_admin()),
) -> VotingResponse:
    voting = await _voting_service.publish_voting(
        session, current_user, election_id
    )
    return VotingResponse.model_validate(voting)


@router.post(
    "/{election_id}/archive",
    response_model=VotingResponse,
    status_code=status.HTTP_200_OK,
    summary="Archive a finished election (FSM: finished -> archived)",
    responses={
        401: {"description": "Missing or invalid token"},
        403: {"description": "Caller does not own this election"},
        404: {"description": "Election not found"},
        409: {"description": "Election is not in finished status"},
    },
)
async def archive_election(
    election_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(_organizer_or_admin()),
) -> VotingResponse:
    voting = await _voting_service.archive_voting(
        session, current_user, election_id
    )
    return VotingResponse.model_validate(voting)


@router.post(
    "/{election_id}/options",
    response_model=BallotOptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a ballot option to a draft election",
    responses={
        400: {"description": "Invalid input"},
        401: {"description": "Missing or invalid token"},
        403: {"description": "Caller does not own this election"},
        404: {"description": "Election not found"},
        409: {"description": "Operation allowed only for draft elections"},
        422: {"description": "Validation error"},
    },
)
async def create_ballot_option(
    election_id: uuid.UUID,
    payload: BallotOptionCreateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(_organizer_or_admin()),
) -> BallotOptionResponse:
    option = await _voting_service.create_option(
        session, current_user, election_id, payload
    )
    return BallotOptionResponse.model_validate(option)


@router.patch(
    "/{election_id}/options/{option_id}",
    response_model=BallotOptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a ballot option in a draft election",
    responses={
        401: {"description": "Missing or invalid token"},
        403: {"description": "Caller does not own this election"},
        404: {"description": "Ballot option not found"},
        409: {"description": "Operation allowed only for draft elections"},
        422: {"description": "Validation error"},
    },
)
async def update_ballot_option(
    election_id: uuid.UUID,
    option_id: uuid.UUID,
    payload: BallotOptionUpdateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(_organizer_or_admin()),
) -> BallotOptionResponse:
    option = await _voting_service.update_option(
        session, current_user, election_id, option_id, payload
    )
    return BallotOptionResponse.model_validate(option)


@router.delete(
    "/{election_id}/options/{option_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a ballot option from a draft election",
    responses={
        401: {"description": "Missing or invalid token"},
        403: {"description": "Caller does not own this election"},
        404: {"description": "Ballot option not found"},
        409: {"description": "Operation allowed only for draft elections"},
    },
)
async def delete_ballot_option(
    election_id: uuid.UUID,
    option_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(_organizer_or_admin()),
) -> None:
    await _voting_service.delete_option(
        session, current_user, election_id, option_id
    )


@router.post(
    "/{election_id}/options/{option_id}/photo",
    response_model=BallotOptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload a photo for a ballot option (draft only)",
    responses={
        400: {"description": "Invalid file type or size"},
        401: {"description": "Missing or invalid token"},
        403: {"description": "Caller does not own this election"},
        404: {"description": "Ballot option not found"},
        409: {"description": "Operation allowed only for draft elections"},
    },
)
async def upload_ballot_option_photo(
    election_id: uuid.UUID,
    option_id: uuid.UUID,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(_organizer_or_admin()),
) -> BallotOptionResponse:
    if file.content_type not in _ALLOWED_PHOTO_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG, PNG, and WebP images are allowed",
        )

    contents = await file.read()
    if len(contents) > _MAX_PHOTO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Photo exceeds the 5 MB size limit",
        )

    ext = _PHOTO_EXT_MAP[file.content_type]
    _BALLOT_PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    file_path = _BALLOT_PHOTO_DIR / f"{option_id}{ext}"

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(contents)

    photo_url = f"/uploads/ballot_options/{option_id}{ext}"
    option = await _voting_service.set_option_photo(
        session, current_user, election_id, option_id, photo_url
    )
    return BallotOptionResponse.model_validate(option)
