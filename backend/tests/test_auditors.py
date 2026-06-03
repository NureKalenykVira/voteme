import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Role
from app.core.security import create_access_token, hash_password
from app.models.user import User


pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _make_user(
    db_session: AsyncSession,
    email: str,
    role: Role = Role.organizer,
) -> User:
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


def _future_window():
    start = datetime.now(timezone.utc) + timedelta(hours=1)
    end = start + timedelta(hours=2)
    return start.isoformat(), end.isoformat()


async def _create_voting(client: AsyncClient, organizer: User) -> dict:
    start, end = _future_window()
    response = await client.post(
        "/elections/",
        headers=_auth(organizer),
        json={
            "title": "Audited Election",
            "description": "d",
            "access_type": "public",
            "is_anonymous": False,
            "start_date_time": start,
            "end_date_time": end,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


class TestListAuditors:
    async def test_list_empty_returns_200(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "aud_list_org@example.com")
        voting = await _create_voting(client, organizer)
        response = await client.get(
            f"/elections/{voting['id']}/auditors", headers=_auth(organizer)
        )
        assert response.status_code == 200
        assert response.json()["items"] == []

    async def test_list_unknown_election_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "aud_list_org2@example.com")
        response = await client.get(
            f"/elections/{uuid.uuid4()}/auditors", headers=_auth(organizer)
        )
        assert response.status_code == 404

    async def test_list_non_owner_returns_403(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        owner = await _make_user(db_session, "aud_list_owner@example.com")
        stranger = await _make_user(db_session, "aud_list_stranger@example.com")
        voting = await _create_voting(client, owner)
        response = await client.get(
            f"/elections/{voting['id']}/auditors", headers=_auth(stranger)
        )
        assert response.status_code == 403


class TestAddAuditor:
    async def test_add_auditor_returns_201(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "aud_add_org@example.com")
        auditor = await _make_user(
            db_session, "aud_add_user@example.com", Role.auditor
        )
        voting = await _create_voting(client, organizer)
        response = await client.post(
            f"/elections/{voting['id']}/auditors",
            headers=_auth(organizer),
            json={"email": "aud_add_user@example.com"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["email"] == "aud_add_user@example.com"
        assert body["user_id"] == str(auditor.id)

    async def test_add_then_list_shows_auditor(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "aud_addlist_org@example.com")
        await _make_user(db_session, "aud_addlist_user@example.com", Role.auditor)
        voting = await _create_voting(client, organizer)
        await client.post(
            f"/elections/{voting['id']}/auditors",
            headers=_auth(organizer),
            json={"email": "aud_addlist_user@example.com"},
        )
        listed = await client.get(
            f"/elections/{voting['id']}/auditors", headers=_auth(organizer)
        )
        emails = {item["email"] for item in listed.json()["items"]}
        assert "aud_addlist_user@example.com" in emails

    async def test_add_auditor_idempotent(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "aud_idem_org@example.com")
        await _make_user(db_session, "aud_idem_user@example.com", Role.auditor)
        voting = await _create_voting(client, organizer)
        first = await client.post(
            f"/elections/{voting['id']}/auditors",
            headers=_auth(organizer),
            json={"email": "aud_idem_user@example.com"},
        )
        second = await client.post(
            f"/elections/{voting['id']}/auditors",
            headers=_auth(organizer),
            json={"email": "aud_idem_user@example.com"},
        )
        assert first.status_code == 201
        assert second.status_code == 201

        listed = await client.get(
            f"/elections/{voting['id']}/auditors", headers=_auth(organizer)
        )
        assert len(listed.json()["items"]) == 1

    async def test_add_unknown_email_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "aud_add404_org@example.com")
        voting = await _create_voting(client, organizer)
        response = await client.post(
            f"/elections/{voting['id']}/auditors",
            headers=_auth(organizer),
            json={"email": "nobody@example.com"},
        )
        assert response.status_code == 404

    async def test_add_non_owner_returns_403(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        owner = await _make_user(db_session, "aud_add403_owner@example.com")
        stranger = await _make_user(db_session, "aud_add403_stranger@example.com")
        await _make_user(db_session, "aud_add403_user@example.com", Role.auditor)
        voting = await _create_voting(client, owner)
        response = await client.post(
            f"/elections/{voting['id']}/auditors",
            headers=_auth(stranger),
            json={"email": "aud_add403_user@example.com"},
        )
        assert response.status_code == 403


class TestRemoveAuditor:
    async def test_remove_auditor_returns_204(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "aud_rm_org@example.com")
        auditor = await _make_user(
            db_session, "aud_rm_user@example.com", Role.auditor
        )
        voting = await _create_voting(client, organizer)
        await client.post(
            f"/elections/{voting['id']}/auditors",
            headers=_auth(organizer),
            json={"email": "aud_rm_user@example.com"},
        )
        response = await client.delete(
            f"/elections/{voting['id']}/auditors/{auditor.id}",
            headers=_auth(organizer),
        )
        assert response.status_code == 204

        listed = await client.get(
            f"/elections/{voting['id']}/auditors", headers=_auth(organizer)
        )
        assert listed.json()["items"] == []

    async def test_remove_unassigned_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "aud_rm404_org@example.com")
        voting = await _create_voting(client, organizer)
        response = await client.delete(
            f"/elections/{voting['id']}/auditors/{uuid.uuid4()}",
            headers=_auth(organizer),
        )
        assert response.status_code == 404

    async def test_remove_non_owner_returns_403(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        owner = await _make_user(db_session, "aud_rm403_owner@example.com")
        stranger = await _make_user(db_session, "aud_rm403_stranger@example.com")
        voting = await _create_voting(client, owner)
        response = await client.delete(
            f"/elections/{voting['id']}/auditors/{uuid.uuid4()}",
            headers=_auth(stranger),
        )
        assert response.status_code == 403
