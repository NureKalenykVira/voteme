import asyncio
import hashlib
import json

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.user import User

pytestmark = pytest.mark.asyncio(loop_scope="session")

GENESIS_HASH = "9ed9b8091629a72699f9de6e263ae2c7a018a1d904ff0e8e86bb053ba318efd5"
ZERO_HASH = "0" * 64


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def _ensure_genesis(db_session: AsyncSession, _clean_tables):
    """Re-insert genesis row after _clean_tables wipes it."""
    genesis = AuditLog(
        action="GENESIS",
        actor_id=None,
        data=None,
        previous_hash=ZERO_HASH,
        entry_hash=GENESIS_HASH,
    )
    db_session.add(genesis)
    await db_session.commit()
    yield


async def _register(client: AsyncClient, email: str):
    return await client.post(
        "/auth/register", json={"email": email, "password": "Password123"}
    )


class TestGenesisRow:
    async def test_genesis_row_hash_is_deterministic(self, db_session: AsyncSession):
        result = await db_session.execute(
            select(AuditLog).where(AuditLog.action == "GENESIS")
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        g = rows[0]
        assert g.previous_hash == ZERO_HASH
        assert g.entry_hash == GENESIS_HASH


class TestChain:
    async def test_sequential_inserts_form_valid_chain(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        for i in range(3):
            resp = await _register(client, f"seq{i}@example.com")
            assert resp.status_code == 201

        result = await db_session.execute(
            select(AuditLog).order_by(AuditLog.id.asc())
        )
        rows = result.scalars().all()
        assert len(rows) >= 4  # genesis + 3 USER_REGISTERED

        for i in range(1, len(rows)):
            prev, curr = rows[i - 1], rows[i]
            assert curr.previous_hash == prev.entry_hash, (
                f"Chain broken at id={curr.id}: {curr.previous_hash!r} != {prev.entry_hash!r}"
            )
            payload = {
                "action": curr.action,
                "actor_id": str(curr.actor_id) if curr.actor_id else None,
                "data": curr.data,
                "previous_hash": curr.previous_hash,
            }
            serialized = json.dumps(
                payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
            )
            expected = hashlib.sha256(serialized.encode()).hexdigest()
            assert curr.entry_hash == expected, (
                f"Hash mismatch at id={curr.id}: stored={curr.entry_hash!r} computed={expected!r}"
            )

    async def test_concurrent_inserts_keep_chain_valid(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        emails = [f"con{i}@example.com" for i in range(3)]
        responses = await asyncio.gather(*[_register(client, e) for e in emails])
        for r in responses:
            assert r.status_code == 201

        db_session.expire_all()
        result = await db_session.execute(
            select(AuditLog).order_by(AuditLog.id.asc())
        )
        rows = result.scalars().all()
        assert len(rows) >= 4

        for i in range(1, len(rows)):
            prev, curr = rows[i - 1], rows[i]
            assert curr.previous_hash == prev.entry_hash, (
                f"Concurrent chain broken at id={curr.id}"
            )

        hashes = [r.entry_hash for r in rows]
        assert len(hashes) == len(set(hashes)), "Duplicate entry_hash values found"


class TestAuditEvents:
    async def test_auth_events_appear_in_audit_log(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        resp = await _register(client, "evented@example.com")
        assert resp.status_code == 201

        # Get confirmation token from DB
        result = await db_session.execute(
            select(User).where(User.email == "evented@example.com")
        )
        user = result.scalar_one()
        token = user.confirmation_token

        # Confirm via endpoint (triggers USER_CONFIRMED audit entry)
        resp = await client.get("/auth/confirm-email", params={"token": token})
        assert resp.status_code == 200

        # Login (triggers USER_LOGIN audit entry)
        resp = await client.post(
            "/auth/login",
            json={"email": "evented@example.com", "password": "Password123"},
        )
        assert resp.status_code == 200

        # Assert all 3 event types in audit log with non-null actor_id
        result = await db_session.execute(
            select(AuditLog).where(
                AuditLog.action.in_(["USER_REGISTERED", "USER_CONFIRMED", "USER_LOGIN"])
            )
        )
        rows = result.scalars().all()
        actions = {r.action for r in rows}
        assert "USER_REGISTERED" in actions
        assert "USER_CONFIRMED" in actions
        assert "USER_LOGIN" in actions
        for r in rows:
            assert r.actor_id is not None
