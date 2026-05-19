from typing import Union

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.repositories.audit_repository import AuditRepository
from app.schemas.audit import VerifyChainBroken, VerifyChainOk

router = APIRouter(tags=["Audit"])

_audit_repo = AuditRepository()


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
