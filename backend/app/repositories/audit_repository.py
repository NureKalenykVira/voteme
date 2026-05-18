import hashlib
import json
import uuid
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

# Fixed advisory lock key for serializing audit log inserts globally.
_AUDIT_LOCK_KEY = 7_777_777_777


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

        payload = {
            "action": action,
            "actor_id": str(actor_id) if actor_id else None,
            "data": data,
            "previous_hash": previous_hash,
        }
        serialized = json.dumps(
            payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        )
        entry_hash = hashlib.sha256(serialized.encode()).hexdigest()

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
