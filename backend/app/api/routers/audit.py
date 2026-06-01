from typing import Optional, Union

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.repositories.audit_repository import AuditRepository
from app.schemas.audit import AuditLogResponse, VerifyChainBroken, VerifyChainOk
from app.services.audit_service import get_audit_log

router = APIRouter(tags=["Audit"])

_audit_repo = AuditRepository()


@router.get(
    "/log",
    response_model=AuditLogResponse,
    status_code=200,
    summary="Get audit event log",
    description=(
        "Returns a paginated list of audit log entries. "
        "Global admins see all entries; organizers see only entries for their own elections; "
        "auditors see only entries for elections they are assigned to. Voters receive 403."
    ),
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Access denied (voter)"},
    },
)
async def get_audit_log_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    action: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AuditLogResponse:
    return await get_audit_log(
        session=session,
        actor=current_user,
        page=page,
        page_size=page_size,
        action=action,
        search=search,
    )


@router.get(
    "/verify-chain",
    response_model=Union[VerifyChainOk, VerifyChainBroken],
    status_code=200,
    summary="Verify audit log hash-chain integrity",
    responses={
        401: {"description": "Missing or invalid token"},
    },
)
async def verify_chain(
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> Union[VerifyChainOk, VerifyChainBroken]:
    broken_at = await _audit_repo.verify_chain(session)
    if broken_at is None:
        return VerifyChainOk(status="ok")
    return VerifyChainBroken(broken_at=broken_at)
