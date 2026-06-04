import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Role
from app.models.user import User
from app.models.voting import Voting
from app.repositories.audit_repository import AuditRepository
from app.repositories.election_auditor_repository import (
    ElectionAuditorRepository,
)
from app.schemas.audit import AuditLogEntry, AuditLogResponse


_audit_repo = AuditRepository()
_election_auditor_repo = ElectionAuditorRepository()


def _build_details(action: str, data: dict) -> Optional[str]:
    if action in ("ELECTION_CREATED", "ELECTION_UPDATED", "ELECTION_DELETED"):
        return data.get("title")
    if action in ("VOTER_ADDED", "VOTER_REMOVED", "AUDITOR_ADDED", "AUDITOR_REMOVED"):
        return data.get("email")
    if action == "VOTER_BULK_IMPORTED":
        return f"{data.get('added', 0)} voters added"
    return None


async def get_audit_log(
    session: AsyncSession,
    actor: User,
    page: int,
    page_size: int,
    action: Optional[str],
    search: Optional[str],
    voting_id_filter: Optional[str] = None,
) -> AuditLogResponse:
    voting_ids: Optional[list[uuid.UUID]]

    if actor.role == Role.voter:
        # voter: only granted audit access if assigned as an auditor on at least
        # one election; otherwise access is denied.
        auditor_ids = await _election_auditor_repo.list_voting_ids_for_user(
            session, actor.id
        )
        if not auditor_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )
        voting_ids = auditor_ids
    elif actor.role == Role.global_admin:
        # Admin can optionally scope the log to a single election.
        if voting_id_filter is not None:
            voting_ids = [uuid.UUID(voting_id_filter)]
        else:
            voting_ids = None
    elif actor.role == Role.auditor:
        # auditor: scope to elections they are explicitly assigned to.
        # An empty list yields no entries (list_entries treats [] as empty),
        # which is the correct behaviour for an unassigned auditor.
        voting_ids = await _election_auditor_repo.list_voting_ids_for_user(
            session, actor.id
        )
    else:
        # organizer: scope to elections they own
        result = await session.execute(
            select(Voting.id).where(
                Voting.created_by == actor.id,
                Voting.is_deleted.is_(False),
            )
        )
        voting_ids = list(result.scalars().all())

    items, total, votes_cast, blockchain_records = await _audit_repo.list_entries(
        session,
        voting_ids=voting_ids,
        page=page,
        page_size=page_size,
        action=action,
        search=search,
    )

    voting_ids_in_page = {
        vid for e in items if (vid := (e.data or {}).get("voting_id"))
    }
    voting_title_map: dict[str, str] = {}
    if voting_ids_in_page:
        rows = await session.execute(
            select(Voting.id, Voting.title).where(
                Voting.id.in_([uuid.UUID(v) for v in voting_ids_in_page])
            )
        )
        voting_title_map = {str(r.id): r.title for r in rows}

    entries = [
        AuditLogEntry(
            id=entry.id,
            created_at=entry.created_at,
            action=entry.action,
            details=_build_details(entry.action, entry.data or {}),
            voting_id=(voting_id := (entry.data or {}).get("voting_id")),
            voting_title=voting_title_map.get(voting_id) if voting_id else None,
            tx_hash=(entry.data or {}).get("tx_hash"),
        )
        for entry in items
    ]

    return AuditLogResponse(
        items=entries,
        total=total,
        votes_cast=votes_cast,
        blockchain_records=blockchain_records,
        page=page,
        page_size=page_size,
    )
