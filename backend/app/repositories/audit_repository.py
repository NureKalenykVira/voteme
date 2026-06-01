import hashlib
import json
import uuid
from typing import Optional

from sqlalchemy import String, cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

# Fixed advisory lock key for serializing audit log inserts globally.
_AUDIT_LOCK_KEY = 7_777_777_777


def _compute_entry_hash(
    action: str,
    actor_id: Optional[uuid.UUID],
    data: Optional[dict],
    previous_hash: str,
) -> str:
    payload = {
        "action": action,
        "actor_id": str(actor_id) if actor_id else None,
        "data": data,
        "previous_hash": previous_hash,
    }
    serialized = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(serialized.encode()).hexdigest()


class AuditRepository:
    async def create_entry(
        self,
        session: AsyncSession,
        action: str,
        actor_id: Optional[uuid.UUID] = None,
        data: Optional[dict] = None,
    ) -> AuditLog:
        # Acquire a transaction-scoped advisory lock so that concurrent
        # transactions cannot read the chain tail simultaneously.
        await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _AUDIT_LOCK_KEY})

        result = await session.execute(
            select(AuditLog).order_by(AuditLog.id.desc()).limit(1)
        )
        tail = result.scalar_one_or_none()
        previous_hash = tail.entry_hash if tail else "0" * 64

        entry_hash = _compute_entry_hash(action, actor_id, data, previous_hash)

        entry = AuditLog(
            action=action,
            actor_id=actor_id,
            data=data,
            previous_hash=previous_hash,
            entry_hash=entry_hash,
        )
        session.add(entry)
        await session.flush()
        return entry

    async def list_entries(
        self,
        session: AsyncSession,
        voting_ids: Optional[list[uuid.UUID]],
        page: int,
        page_size: int,
        action: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[list[AuditLog], int, int, int]:
        """
        Returns (items, total_count, votes_cast_count, blockchain_records_count).

        voting_ids=None  → no voting filter (admin path, see all entries)
        voting_ids=[]    → organizer with no elections, return empty immediately
        """
        if voting_ids is not None and len(voting_ids) == 0:
            return [], 0, 0, 0

        def _base_filters(q):
            if voting_ids is not None:
                str_ids = [str(vid) for vid in voting_ids]
                q = q.where(
                    cast(AuditLog.data["voting_id"], String).in_(
                        [f'"{s}"' for s in str_ids]
                    )
                )
            if action is not None:
                q = q.where(AuditLog.action == action)
            if search is not None:
                pattern = f"%{search}%"
                q = q.where(
                    AuditLog.action.ilike(pattern)
                    | cast(AuditLog.data, String).ilike(pattern)
                )
            return q

        count_q = _base_filters(select(func.count()).select_from(AuditLog))
        total_result = await session.execute(count_q)
        total = total_result.scalar_one()

        votes_q = _base_filters(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.action == "VOTE_SUBMITTED"
            )
        )
        votes_result = await session.execute(votes_q)
        votes_cast = votes_result.scalar_one()

        # blockchain_records count: entries whose data JSONB contains a tx_hash key
        bc_q = _base_filters(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.data["tx_hash"].isnot(None)
            )
        )
        bc_result = await session.execute(bc_q)
        blockchain_records = bc_result.scalar_one()

        items_q = (
            _base_filters(select(AuditLog))
            .order_by(AuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items_result = await session.execute(items_q)
        items = list(items_result.scalars().all())

        return items, total, votes_cast, blockchain_records

    async def verify_chain(self, session: AsyncSession) -> Optional[int]:
        prev_entry_hash: Optional[str] = None
        async for entry in await session.stream_scalars(
            select(AuditLog).order_by(AuditLog.id)
        ):
            if prev_entry_hash is None:
                # Genesis entry: previous_hash must be 64 zero characters
                if entry.previous_hash != "0" * 64:
                    return entry.id
            else:
                if entry.previous_hash != prev_entry_hash:
                    return entry.id

            expected_hash = _compute_entry_hash(
                entry.action, entry.actor_id, entry.data, entry.previous_hash
            )
            if entry.entry_hash != expected_hash:
                return entry.id

            prev_entry_hash = entry.entry_hash

        return None
