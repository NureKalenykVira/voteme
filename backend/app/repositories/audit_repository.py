import hashlib
import json
import uuid
from typing import Optional

from sqlalchemy import select, text
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
