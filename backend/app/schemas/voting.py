import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.enums import VotingAccessType, VotingStatus


class VotingCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    access_type: VotingAccessType
    is_anonymous: bool = False
    start_date_time: datetime
    end_date_time: datetime

    @field_validator("end_date_time")
    @classmethod
    def _end_after_start(cls, value: datetime, info) -> datetime:
        start = info.data.get("start_date_time")
        if start is not None and value <= start:
            raise ValueError("end_date_time must be after start_date_time")
        return value


class VotingUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    access_type: Optional[VotingAccessType] = None
    start_date_time: Optional[datetime] = None
    end_date_time: Optional[datetime] = None

    model_config = ConfigDict(extra="ignore")


class BallotOptionCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class BallotOptionUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    order_index: Optional[int] = Field(default=None, ge=0)


class BallotOptionResponse(BaseModel):
    id: uuid.UUID
    voting_id: uuid.UUID
    title: str
    description: Optional[str] = None
    photo_url: Optional[str] = None
    order_index: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VotingResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: Optional[str] = None
    access_type: VotingAccessType
    is_anonymous: bool
    invitation_code: Optional[str] = None
    start_date_time: datetime
    end_date_time: datetime
    status: VotingStatus
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VotingDetailResponse(VotingResponse):
    options: list[BallotOptionResponse] = Field(default_factory=list)


class VotingListResponse(BaseModel):
    items: list[VotingResponse]
    total: int
    page: int
    page_size: int


class VotingJoinResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: Optional[str] = None
    status: VotingStatus
    is_anonymous: bool
    start_date_time: datetime
    end_date_time: datetime
    created_by: uuid.UUID
    created_by_name: Optional[str] = None
    voters_invited: int
    already_voted: int
    participation_pct: float
    options: list[BallotOptionResponse] = Field(default_factory=list)
    is_organizer: bool = False
    user_has_voted: bool = False

    model_config = ConfigDict(from_attributes=True)


class VoterResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: Optional[str] = None
    status: str  # "invited" | "voted"

    model_config = ConfigDict(from_attributes=True)


class VoterListResponse(BaseModel):
    items: list[VoterResponse]
    total: int
    page: int
    page_size: int
    voters_invited: int
    already_voted: int
    participation_pct: float


class AddVoterRequest(BaseModel):
    email: EmailStr


class CsvImportInvalidRow(BaseModel):
    row: int
    email: str
    reason: str


class CsvImportResponse(BaseModel):
    total_rows: int
    added_count: int
    duplicate_count: int
    invalid_count: int
    invalid_rows: list[CsvImportInvalidRow]


class VoteSubmitRequest(BaseModel):
    option_id: uuid.UUID


class VoteSubmitResponse(BaseModel):
    vote_id: uuid.UUID
    commitment_hash: str
    tx_status: str
    submitted_at: datetime


class MyVoteResponse(BaseModel):
    has_voted: bool
    option_id: Optional[uuid.UUID] = None
    submitted_at: Optional[datetime] = None
    commitment_hash: Optional[str] = None
    tx_status: Optional[str] = None
