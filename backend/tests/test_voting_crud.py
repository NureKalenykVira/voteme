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


def _future_window(start_seconds: int = 3600, duration_seconds: int = 3600):
    start = datetime.now(timezone.utc) + timedelta(seconds=start_seconds)
    end = start + timedelta(seconds=duration_seconds)
    return start.isoformat(), end.isoformat()


class TestCreateElection:
    async def test_create_returns_201_and_draft(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "org1@example.com")
        start, end = _future_window()
        response = await client.post(
            "/elections/",
            headers=_auth(organizer),
            json={
                "title": "Test Election",
                "description": "desc",
                "access_type": "public",
                "is_anonymous": False,
                "start_date_time": start,
                "end_date_time": end,
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "draft"
        assert body["title"] == "Test Election"
        assert body["created_by"] == str(organizer.id)
        assert body["is_anonymous"] is False

    async def test_create_invalid_dates_returns_422(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "org2@example.com")
        start = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        end = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        response = await client.post(
            "/elections/",
            headers=_auth(organizer),
            json={
                "title": "Bad",
                "access_type": "public",
                "is_anonymous": False,
                "start_date_time": start,
                "end_date_time": end,
            },
        )
        assert response.status_code == 422

    async def test_create_without_token_returns_401(
        self, client: AsyncClient
    ):
        start, end = _future_window()
        response = await client.post(
            "/elections/",
            json={
                "title": "X",
                "access_type": "public",
                "is_anonymous": False,
                "start_date_time": start,
                "end_date_time": end,
            },
        )
        assert response.status_code == 401

    async def test_voter_role_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        voter = await _make_user(db_session, "voter1@example.com", Role.voter)
        start, end = _future_window()
        response = await client.post(
            "/elections/",
            headers=_auth(voter),
            json={
                "title": "X",
                "access_type": "public",
                "is_anonymous": False,
                "start_date_time": start,
                "end_date_time": end,
            },
        )
        assert response.status_code == 403


async def _create_voting(client: AsyncClient, organizer: User, **overrides) -> dict:
    start, end = _future_window()
    payload = {
        "title": "Vote",
        "description": "d",
        "access_type": "public",
        "is_anonymous": False,
        "start_date_time": start,
        "end_date_time": end,
    }
    payload.update(overrides)
    response = await client.post(
        "/elections/", headers=_auth(organizer), json=payload
    )
    assert response.status_code == 201
    return response.json()


async def _add_option(
    client: AsyncClient, organizer: User, voting_id: str, title: str
) -> dict:
    response = await client.post(
        f"/elections/{voting_id}/options",
        headers=_auth(organizer),
        json={"title": title},
    )
    assert response.status_code == 201
    return response.json()


class TestPublishElection:
    async def test_publish_requires_two_options(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "pub1@example.com")
        voting = await _create_voting(client, organizer)
        vid = voting["id"]
        response = await client.post(
            f"/elections/{vid}/publish", headers=_auth(organizer)
        )
        assert response.status_code == 409

    async def test_publish_succeeds_with_two_options(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "pub2@example.com")
        voting = await _create_voting(client, organizer)
        vid = voting["id"]
        await _add_option(client, organizer, vid, "A")
        await _add_option(client, organizer, vid, "B")
        response = await client.post(
            f"/elections/{vid}/publish", headers=_auth(organizer)
        )
        assert response.status_code == 200
        assert response.json()["status"] == "published"

    async def test_publish_private_generates_invitation_code(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "pub3@example.com")
        voting = await _create_voting(client, organizer, access_type="private")
        vid = voting["id"]
        await _add_option(client, organizer, vid, "A")
        await _add_option(client, organizer, vid, "B")
        response = await client.post(
            f"/elections/{vid}/publish", headers=_auth(organizer)
        )
        assert response.status_code == 200
        assert response.json()["invitation_code"] is not None

    async def test_publish_twice_returns_409(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "pub4@example.com")
        voting = await _create_voting(client, organizer)
        vid = voting["id"]
        await _add_option(client, organizer, vid, "A")
        await _add_option(client, organizer, vid, "B")
        await client.post(
            f"/elections/{vid}/publish", headers=_auth(organizer)
        )
        again = await client.post(
            f"/elections/{vid}/publish", headers=_auth(organizer)
        )
        assert again.status_code == 409


class TestUpdateAndDelete:
    async def test_update_draft_succeeds(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "upd1@example.com")
        voting = await _create_voting(client, organizer)
        vid = voting["id"]
        response = await client.patch(
            f"/elections/{vid}",
            headers=_auth(organizer),
            json={"title": "Updated"},
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Updated"

    async def test_update_ignores_is_anonymous(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "upd2@example.com")
        voting = await _create_voting(client, organizer)
        vid = voting["id"]
        response = await client.patch(
            f"/elections/{vid}",
            headers=_auth(organizer),
            json={"is_anonymous": True},
        )
        assert response.status_code == 200
        assert response.json()["is_anonymous"] is False

    async def test_update_published_returns_409(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "upd3@example.com")
        voting = await _create_voting(client, organizer)
        vid = voting["id"]
        await _add_option(client, organizer, vid, "A")
        await _add_option(client, organizer, vid, "B")
        await client.post(
            f"/elections/{vid}/publish", headers=_auth(organizer)
        )
        response = await client.patch(
            f"/elections/{vid}",
            headers=_auth(organizer),
            json={"title": "Late"},
        )
        assert response.status_code == 409

    async def test_delete_draft_succeeds(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "del1@example.com")
        voting = await _create_voting(client, organizer)
        vid = voting["id"]
        response = await client.delete(
            f"/elections/{vid}", headers=_auth(organizer)
        )
        assert response.status_code == 204

        follow = await client.get(
            f"/elections/{vid}", headers=_auth(organizer)
        )
        assert follow.status_code == 404

    async def test_delete_published_returns_409(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "del2@example.com")
        voting = await _create_voting(client, organizer)
        vid = voting["id"]
        await _add_option(client, organizer, vid, "A")
        await _add_option(client, organizer, vid, "B")
        await client.post(
            f"/elections/{vid}/publish", headers=_auth(organizer)
        )
        response = await client.delete(
            f"/elections/{vid}", headers=_auth(organizer)
        )
        assert response.status_code == 409

    async def test_other_organizer_cannot_update(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer_a = await _make_user(db_session, "owner1@example.com")
        organizer_b = await _make_user(db_session, "stranger1@example.com")
        voting = await _create_voting(client, organizer_a)
        vid = voting["id"]
        response = await client.patch(
            f"/elections/{vid}",
            headers=_auth(organizer_b),
            json={"title": "Hijack"},
        )
        assert response.status_code in (403, 404)


class TestBallotOptions:
    async def test_create_option_assigns_order(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "opt1@example.com")
        voting = await _create_voting(client, organizer)
        vid = voting["id"]
        a = await _add_option(client, organizer, vid, "A")
        b = await _add_option(client, organizer, vid, "B")
        assert a["order_index"] == 0
        assert b["order_index"] == 1

    async def test_create_option_on_published_returns_409(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "opt2@example.com")
        voting = await _create_voting(client, organizer)
        vid = voting["id"]
        await _add_option(client, organizer, vid, "A")
        await _add_option(client, organizer, vid, "B")
        await client.post(
            f"/elections/{vid}/publish", headers=_auth(organizer)
        )
        response = await client.post(
            f"/elections/{vid}/options",
            headers=_auth(organizer),
            json={"title": "C"},
        )
        assert response.status_code == 409

    async def test_delete_option_in_draft(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "opt3@example.com")
        voting = await _create_voting(client, organizer)
        vid = voting["id"]
        a = await _add_option(client, organizer, vid, "A")
        oid = a["id"]
        response = await client.delete(
            f"/elections/{vid}/options/{oid}",
            headers=_auth(organizer),
        )
        assert response.status_code == 204

    async def test_update_option_in_draft(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "opt4@example.com")
        voting = await _create_voting(client, organizer)
        vid = voting["id"]
        a = await _add_option(client, organizer, vid, "A")
        oid = a["id"]
        response = await client.patch(
            f"/elections/{vid}/options/{oid}",
            headers=_auth(organizer),
            json={"title": "Aprime"},
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Aprime"


class TestListAndDetail:
    async def test_list_returns_own_drafts(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "list1@example.com")
        await _create_voting(client, organizer)
        await _create_voting(client, organizer)
        response = await client.get(
            "/elections/", headers=_auth(organizer)
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] >= 2
        assert all(v["created_by"] == str(organizer.id) for v in body["items"])

    async def test_detail_returns_options(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "det1@example.com")
        voting = await _create_voting(client, organizer)
        vid = voting["id"]
        await _add_option(client, organizer, vid, "A")
        await _add_option(client, organizer, vid, "B")
        response = await client.get(
            f"/elections/{vid}", headers=_auth(organizer)
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body["options"]) == 2
        assert body["options"][0]["order_index"] == 0


class TestArchive:
    async def test_archive_only_from_finished(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "arc1@example.com")
        voting = await _create_voting(client, organizer)
        vid = voting["id"]
        response = await client.post(
            f"/elections/{vid}/archive", headers=_auth(organizer)
        )
        assert response.status_code == 409
