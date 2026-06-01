import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_optional_user, require_role
from app.core.enums import Role, VotingStatus
from app.models.user import User
from app.schemas.voting import (
    AddAuditorRequest,
    AddVoterRequest,
    AuditorListResponse,
    AuditorResponse,
    BallotOptionCreateRequest,
    BallotOptionResponse,
    BallotOptionUpdateRequest,
    CsvImportResponse,
    ElectionResultsResponse,
    MerkleProofResponse,
    MyVoteResponse,
    TimelineResponse,
    VoterReceiptResponse,
    VoteSubmitRequest,
    VoteSubmitResponse,
    VoterListResponse,
    VoterResponse,
    VotingCreateRequest,
    VotingDetailResponse,
    VotingJoinResponse,
    VotingListResponse,
    VotingResponse,
    VotingUpdateRequest,
)
from app.services.voting_service import VotingService
from app.services.vote_service import VoteService

router = APIRouter(tags=["Elections"])
voter_router = APIRouter(tags=["Whitelist"])
vote_router = APIRouter(tags=["Voting"])

_voting_service = VotingService()
_vote_service = VoteService()

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
    "/join/{code}",
    response_model=VotingJoinResponse,
    status_code=status.HTTP_200_OK,
    summary="Get election by invitation code",
    responses={404: {"description": "Election not found"}},
)
async def get_election_by_code(
    code: str,
    session: AsyncSession = Depends(get_db),
    actor: User | None = Depends(get_optional_user),
) -> VotingJoinResponse:
    (
        voting,
        already_voted,
        created_by_name,
        options,
        is_organizer,
        user_has_voted,
        voters_invited_count,
        participation,
        can_vote,
    ) = await _voting_service.get_join_view(session, code, actor)
    return VotingJoinResponse(
        id=voting.id,
        title=voting.title,
        description=voting.description,
        status=voting.status,
        is_anonymous=voting.is_anonymous,
        start_date_time=voting.start_date_time,
        end_date_time=voting.end_date_time,
        created_by=voting.created_by,
        created_by_name=created_by_name,
        voters_invited=voters_invited_count,
        already_voted=already_voted,
        participation_pct=participation,
        options=options,
        is_organizer=is_organizer,
        user_has_voted=user_has_voted,
        can_vote=can_vote,
        publish_tx_hash=voting.publish_tx_hash,
        finalize_tx_hash=voting.finalize_tx_hash,
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
        publish_tx_hash=voting.publish_tx_hash,
        finalize_tx_hash=voting.finalize_tx_hash,
        options=[BallotOptionResponse.model_validate(o) for o in options],
    )


@router.get(
    "/{election_id}/results",
    response_model=ElectionResultsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get public results for a finished election",
    description=(
        "Returns per-option vote counts and percentages for an election. "
        "Available only once the election is finished or archived; returns 409 "
        "otherwise to preserve in-progress result privacy. Results are public."
    ),
    responses={
        404: {"description": "Election not found"},
        409: {"description": "Election results are not available yet"},
    },
)
async def get_election_results(
    election_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    actor: User | None = Depends(get_optional_user),
) -> ElectionResultsResponse:
    return await _voting_service.get_results(session, election_id, actor)


@router.get(
    "/{election_id}/timeline",
    response_model=TimelineResponse,
    status_code=status.HTTP_200_OK,
    summary="Get vote timeline for organizer dashboard",
    description=(
        "Returns a time-bucketed histogram of vote submissions for the given election. "
        "Bucket granularity is determined automatically by the election duration. "
        "Only the election organizer or a global admin may access this endpoint."
    ),
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Not the election organizer"},
        404: {"description": "Election not found"},
    },
)
async def get_election_timeline(
    election_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TimelineResponse:
    return await _voting_service.get_timeline(session, election_id, current_user)


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
        409: {"description": "Operation allowed only for draft or published elections"},
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
        409: {"description": "Operation allowed only for draft or published elections"},
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
        409: {"description": "Operation allowed only for draft or published elections"},
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
        409: {"description": "Operation allowed only for draft or published elections"},
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
        409: {"description": "Operation allowed only for draft or published elections"},
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


@router.get(
    "/{election_id}/auditors",
    response_model=AuditorListResponse,
    status_code=status.HTTP_200_OK,
    summary="List auditors assigned to an election",
    description=(
        "Returns the users granted read-only audit-log access to this election. "
        "Only the election organizer or a global admin may access this endpoint."
    ),
    responses={
        401: {"description": "Missing or invalid token"},
        403: {"description": "Caller does not own this election"},
        404: {"description": "Election not found"},
    },
)
async def list_auditors(
    election_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(_organizer_or_admin()),
) -> AuditorListResponse:
    items = await _voting_service.list_auditors(
        session, current_user, election_id
    )
    return AuditorListResponse(
        items=[
            AuditorResponse(user_id=user_id, email=email)
            for user_id, email in items
        ]
    )


@router.post(
    "/{election_id}/auditors",
    response_model=AuditorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign an auditor to an election by email",
    description=(
        "Grants the user with the given email read-only access to this election "
        "audit log. The user must already exist. Idempotent: re-assigning an "
        "existing auditor returns the same record. Organizer-only."
    ),
    responses={
        401: {"description": "Missing or invalid token"},
        403: {"description": "Caller does not own this election"},
        404: {"description": "Election not found or no user with this email"},
        422: {"description": "Validation error"},
    },
)
async def add_auditor(
    election_id: uuid.UUID,
    payload: AddAuditorRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(_organizer_or_admin()),
) -> AuditorResponse:
    user_id, email = await _voting_service.add_auditor(
        session, current_user, election_id, str(payload.email)
    )
    return AuditorResponse(user_id=user_id, email=email)


@router.delete(
    "/{election_id}/auditors/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an auditor from an election",
    responses={
        401: {"description": "Missing or invalid token"},
        403: {"description": "Caller does not own this election"},
        404: {"description": "Election not found or auditor not assigned"},
    },
)
async def remove_auditor(
    election_id: uuid.UUID,
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(_organizer_or_admin()),
) -> None:
    await _voting_service.remove_auditor(
        session, current_user, election_id, user_id
    )


@voter_router.get(
    "/{election_id}/voters",
    response_model=VoterListResponse,
    status_code=status.HTTP_200_OK,
    summary="List voters for an election",
    responses={
        401: {"description": "Missing or invalid token"},
        403: {"description": "Caller does not own this election"},
        404: {"description": "Election not found"},
    },
)
async def list_voters(
    election_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(_organizer_or_admin()),
) -> VoterListResponse:
    items, total, voters_invited, already_voted, participation_pct = (
        await _voting_service.list_voters(
            session, current_user, election_id, page, page_size
        )
    )
    return VoterListResponse(
        items=[VoterResponse(**item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        voters_invited=voters_invited,
        already_voted=already_voted,
        participation_pct=participation_pct,
    )


@voter_router.post(
    "/{election_id}/voters",
    response_model=VoterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a voter to an election by email",
    responses={
        401: {"description": "Missing or invalid token"},
        403: {"description": "Caller does not own this election"},
        404: {"description": "Election not found"},
        409: {"description": "Email already on voter list or election not editable"},
        422: {"description": "Validation error"},
    },
)
async def add_voter(
    election_id: uuid.UUID,
    payload: AddVoterRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(_organizer_or_admin()),
) -> VoterResponse:
    voter = await _voting_service.add_voter(
        session, current_user, election_id, str(payload.email)
    )
    return VoterResponse(id=voter.id, email=voter.email, name=None, status="invited")


@voter_router.post(
    "/{election_id}/voters/csv",
    response_model=CsvImportResponse,
    status_code=status.HTTP_200_OK,
    summary="Bulk-import voters from a CSV file",
    description=(
        "Upload a UTF-8 CSV file with an `email` header column. "
        "Max 1000 data rows. Returns added / duplicate / invalid counts."
    ),
    responses={
        401: {"description": "Missing or invalid token"},
        403: {"description": "Caller does not own this election"},
        404: {"description": "Election not found"},
        409: {"description": "Election not editable"},
        422: {"description": "Invalid file or encoding"},
    },
)
async def import_voters_csv(
    election_id: uuid.UUID,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(_organizer_or_admin()),
) -> CsvImportResponse:
    if file.content_type not in ("text/csv", "text/plain", "application/vnd.ms-excel", "application/octet-stream"):
        content_type = file.content_type or ""
        if not (content_type.startswith("text/") or file.filename and file.filename.endswith(".csv")):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Only CSV files are accepted",
            )
    content = await file.read()
    return await _voting_service.import_voters_csv(session, current_user, election_id, content)


@voter_router.delete(
    "/{election_id}/voters/{voter_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a voter from an election",
    responses={
        401: {"description": "Missing or invalid token"},
        403: {"description": "Caller does not own this election"},
        404: {"description": "Election not found or voter not found"},
        409: {"description": "Voter has already voted or election not editable"},
    },
)
async def remove_voter(
    election_id: uuid.UUID,
    voter_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(_organizer_or_admin()),
) -> None:
    await _voting_service.remove_voter(
        session, current_user, election_id, voter_id
    )



@vote_router.post(
    "/{election_id}/vote",
    response_model=VoteSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a vote in an active election",
    description=(
        "Submits a single vote for the authenticated user in the specified election. "
        "Duplicate votes are rejected by a DB UNIQUE(voting_id, user_id) constraint. "
        "For anonymous elections, the voter identity is never written to the audit log."
    ),
    responses={
        401: {"description": "Missing or invalid token"},
        403: {"description": "Caller is not eligible to vote in this election"},
        404: {"description": "Election or ballot option not found"},
        409: {"description": "Election is not active or voter has already voted"},
        422: {"description": "Validation error"},
    },
)
async def submit_vote(
    election_id: uuid.UUID,
    payload: VoteSubmitRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VoteSubmitResponse:
    ip_address = request.client.host if request.client else None
    vote, tx_status = await _vote_service.submit_vote(
        session,
        current_user,
        election_id,
        payload.option_id,
        ip_address=ip_address,
    )
    return VoteSubmitResponse(
        vote_id=vote.id,
        commitment_hash=vote.commitment_hash,
        tx_status=tx_status,
        tx_hash=None,
        submitted_at=vote.submitted_at,
    )


@vote_router.get(
    "/{election_id}/proof",
    response_model=MerkleProofResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Merkle inclusion proof for a vote",
    description=(
        "Returns the Merkle proof path for a specific vote. Only available after election is "
        "finalized. Voter can only access their own proof; organizer can access any."
    ),
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Access denied"},
        404: {"description": "Election or vote not found"},
        409: {"description": "Election not yet finalized"},
    },
)
async def get_vote_proof(
    election_id: uuid.UUID,
    vote_id: uuid.UUID = Query(..., description="ID of the vote to prove"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MerkleProofResponse:
    payload = await _vote_service.get_merkle_proof(session, current_user, election_id, vote_id)
    return MerkleProofResponse(**payload)


@vote_router.get(
    "/{election_id}/receipt",
    response_model=VoterReceiptResponse,
    status_code=status.HTTP_200_OK,
    summary="Download voter receipt for independent verification",
    description=(
        "Returns a JSON receipt containing the voter's commitment, nonce, and Merkle proof. "
        "Use with verify_receipt.py for independent verification."
    ),
    responses={
        401: {"description": "Not authenticated"},
        404: {"description": "Election not found or you have not voted"},
        409: {"description": "Election not yet finalized"},
    },
)
async def get_voter_receipt(
    election_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VoterReceiptResponse:
    payload = await _vote_service.get_voter_receipt(session, current_user, election_id)
    return VoterReceiptResponse(**payload)


@vote_router.get(
    "/{election_id}/my-vote",
    response_model=MyVoteResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the current user vote record for an election",
    description=(
        "Returns whether the current user has voted in the election. "
        "For anonymous elections, option_id and submitted_at are omitted from the response "
        "even when has_voted=true. Returns has_voted=false for draft elections."
    ),
    responses={
        401: {"description": "Missing or invalid token"},
        404: {"description": "Election not found"},
    },
)
async def get_my_vote(
    election_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MyVoteResponse:
    payload = await _vote_service.get_my_vote(session, current_user, election_id)
    return MyVoteResponse(**payload)
