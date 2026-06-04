import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.enums import Role


class AdminUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: Optional[str] = None
    role: Role
    is_confirmed: bool
    is_deleted: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminUserListResponse(BaseModel):
    items: list[AdminUserResponse]
    total: int
    page: int
    page_size: int


class CreateUserRequest(BaseModel):
    full_name: Optional[str] = None
    email: EmailStr
    role: Role
    password: str = Field(..., min_length=8)


class PatchUserRoleRequest(BaseModel):
    role: Role


class SettingsResponse(BaseModel):
    max_free_votings_per_month: int
    maintenance_mode: bool
    require_email_verification: bool
    session_timeout_minutes: int


class SettingsUpdateRequest(BaseModel):
    max_free_votings_per_month: Optional[int] = None
    maintenance_mode: Optional[bool] = None
    require_email_verification: Optional[bool] = None
    session_timeout_minutes: Optional[int] = None


class DayCount(BaseModel):
    date: str
    count: int


class RoleCount(BaseModel):
    role: str
    count: int


class TopVoting(BaseModel):
    title: str
    votes_count: int


class AdminElectionResponse(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    organizer_name: Optional[str] = None
    organizer_email: Optional[str] = None
    start_date_time: datetime
    end_date_time: datetime
    created_by: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


class AdminElectionListResponse(BaseModel):
    items: list[AdminElectionResponse]
    total: int
    page: int
    page_size: int


class StatsResponse(BaseModel):
    total_users: int
    total_votings: int
    votes_cast: int
    active_votings: int
    new_users_this_month: int
    avg_participation_pct: float
    votings_per_day: list[DayCount]
    votes_per_day: list[DayCount]
    users_by_role: list[RoleCount]
    top_votings: list[TopVoting]
    blockchain_total: int
    blockchain_confirmed: int
    blockchain_failed: int
    blockchain_published: int
    blockchain_finalized: int
    emails_total: int
    emails_sent: int
    emails_failed: int


class RestoreResponse(BaseModel):
    users_imported: int
    users_skipped: int
    votings_imported: int
    votings_skipped: int
