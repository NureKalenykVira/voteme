import io
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Role
from app.core.security import create_access_token, hash_password
from app.models.user import User

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _make_user(db_session: AsyncSession, email: str, role: Role = Role.organizer) -> User:
    user = User(
        email=email.lower(),
        hashed_password=hash_password("Password123"),
        full_name="Test User",
        role=role,
        is_confirmed=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def _auth(user: User) -> dict[str, str]:
    token = create_access_token(sub=str(user.id), role=user.role)
    return {"Authorization": f"Bearer {token}"}


def _future_window(start_s: int = 3600, dur_s: int = 3600):
    start = datetime.now(timezone.utc) + timedelta(seconds=start_s)
    end = start + timedelta(seconds=dur_s)
    return start.isoformat(), end.isoformat()


async def _create_election(client: AsyncClient, organizer: User) -> str:
    start, end = _future_window()
    resp = await client.post(
        "/elections/",
        headers=_auth(organizer),
        json={
            "title": "CSV Test Election",
            "access_type": "private",
            "is_anonymous": False,
            "start_date_time": start,
            "end_date_time": end,
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _csv_file(content: str) -> tuple:
    return ("file", ("voters.csv", io.BytesIO(content.encode()), "text/csv"))


class TestCsvImport:
    async def test_valid_csv_imports_voters(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        org = await _make_user(db_session, f"csvorg1_{uuid.uuid4().hex[:6]}@example.com")
        election_id = await _create_election(client, org)

        csv_content = "email\nalice@example.com\nbob@example.com\ncarol@example.com\n"
        resp = await client.post(
            f"/elections/{election_id}/voters/csv",
            headers=_auth(org),
            files=[_csv_file(csv_content)],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["added_count"] == 3
        assert data["duplicate_count"] == 0
        assert data["invalid_count"] == 0
        assert data["total_rows"] == 3

    async def test_invalid_emails_reported(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        org = await _make_user(db_session, f"csvorg2_{uuid.uuid4().hex[:6]}@example.com")
        election_id = await _create_election(client, org)

        csv_content = "email\ngood@example.com\nnot-an-email\nalso-bad@\n"
        resp = await client.post(
            f"/elections/{election_id}/voters/csv",
            headers=_auth(org),
            files=[_csv_file(csv_content)],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["added_count"] == 1
        assert data["invalid_count"] == 2
        assert len(data["invalid_rows"]) == 2

    async def test_duplicate_emails_reported(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        org = await _make_user(db_session, f"csvorg3_{uuid.uuid4().hex[:6]}@example.com")
        election_id = await _create_election(client, org)

        # Pre-add one voter manually
        await client.post(
            f"/elections/{election_id}/voters",
            headers=_auth(org),
            json={"email": "existing@example.com"},
        )

        csv_content = "email\nexisting@example.com\nnew@example.com\nexisting@example.com\n"
        resp = await client.post(
            f"/elections/{election_id}/voters/csv",
            headers=_auth(org),
            files=[_csv_file(csv_content)],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["added_count"] == 1
        assert data["duplicate_count"] == 2  # 1 DB dup + 1 in-file dup

    async def test_over_1000_rows_rejected(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        org = await _make_user(db_session, f"csvorg4_{uuid.uuid4().hex[:6]}@example.com")
        election_id = await _create_election(client, org)

        rows = "\n".join(f"user{i}@example.com" for i in range(1001))
        csv_content = f"email\n{rows}\n"
        resp = await client.post(
            f"/elections/{election_id}/voters/csv",
            headers=_auth(org),
            files=[_csv_file(csv_content)],
        )
        assert resp.status_code == 422

    async def test_missing_email_column_rejected(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        org = await _make_user(db_session, f"csvorg5_{uuid.uuid4().hex[:6]}@example.com")
        election_id = await _create_election(client, org)

        csv_content = "name\nAlice\nBob\n"
        resp = await client.post(
            f"/elections/{election_id}/voters/csv",
            headers=_auth(org),
            files=[_csv_file(csv_content)],
        )
        assert resp.status_code == 422

    async def test_unauthorized_returns_401(self, client: AsyncClient, db_session: AsyncSession):
        org = await _make_user(db_session, f"csvorg6_{uuid.uuid4().hex[:6]}@example.com")
        election_id = await _create_election(client, org)

        csv_content = "email\ntest@example.com\n"
        resp = await client.post(
            f"/elections/{election_id}/voters/csv",
            files=[_csv_file(csv_content)],
        )
        assert resp.status_code == 401

    async def test_other_organizer_returns_403(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        org = await _make_user(db_session, f"csvorg7_{uuid.uuid4().hex[:6]}@example.com")
        other = await _make_user(db_session, f"csvorg8_{uuid.uuid4().hex[:6]}@example.com")
        election_id = await _create_election(client, org)

        csv_content = "email\ntest@example.com\n"
        resp = await client.post(
            f"/elections/{election_id}/voters/csv",
            headers=_auth(other),
            files=[_csv_file(csv_content)],
        )
        assert resp.status_code == 403
