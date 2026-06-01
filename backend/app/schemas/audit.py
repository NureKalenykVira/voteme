from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict


class VerifyChainOk(BaseModel):
    status: Literal["ok"]


class VerifyChainBroken(BaseModel):
    broken_at: int


class AuditLogEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    action: str
    details: Optional[str] = None
    voting_id: Optional[str] = None
    voting_title: Optional[str] = None
    tx_hash: Optional[str] = None


class AuditLogResponse(BaseModel):
    items: List[AuditLogEntry]
    total: int
    votes_cast: int
    blockchain_records: int
    page: int
    page_size: int
