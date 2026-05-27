"""
Tests that voter_lists.user_id is back-filled when a user registers or logs in,
covering the case where an organizer added the voter by email before the voter
created an account.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User
from app.models.voter_list import VoterList
from app.repositories.voter_list_repository import VoterListRepository

pytestmark = pytest.mark.asyncio(loop_scope="session")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_voting(db_session: AsyncSession) -> uuid.UUID:
    """Insert a minimal voting row so voter_lists FK is satisfied."""
    from app.core.enums import Role, VotingAccessType
    from app.models.voting import Voting

    organizer = User(
        email=f"org_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("Password123"),
        full_name="Organizer",
        role=Role.organizer,
        is_confirmed=True,
    )
    db_session.add(organizer)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    voting = Voting(
        title="Link Test Election",
        created_by=organizer.id,
        access_type=VotingAccessType.private,
        is_anonymous=False,
        start_date_time=now + timedelta(hours=1),
        end_date_time=now + timedelta(hours=2),
    )
    db_session.add(voting)
    await db_session.flush()
    await db_session.commit()
    return voting.id


async def _insert_voter_list_row(
    db_session: AsyncSession,
    voting_id: uuid.UUID,
    email: str,
    user_id: uuid.UUID | None = None,
) -> VoterList:
    voter = VoterList(voting_id=voting_id, email=email, user_id=user_id)
    db_session.add(voter)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(voter)
    return voter


async def _register(client: AsyncClient, email: str, password: str = "Password123"):
    return await client.post(
        "/auth/register", json={"email": email, "password": password}
    )


async def _confirm_and_login(
    client: AsyncClient,
    db_session: AsyncSession,
    email: str,
    password: str = "Password123",
) -> str:
    """Confirm the user directly in the DB, then POST /auth/login. Returns JWT."""
    db_session.expire_all()
    result = await db_session.execute(
        select(User).where(User.email == email.lower())
    )
    user = result.scalar_one()
    user.is_confirmed = True
    user.confirmation_token = None
    await db_session.commit()

    resp = await client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestVoterLinking:
    async def test_register_links_voter_list(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Register fires link_user_by_email: voter_lists.user_id must be filled."""
        voting_id = await _make_voting(db_session)
        email = f"reg_link_{uuid.uuid4().hex[:6]}@test.com"

        # Organizer added the voter before they had an account.
        row = await _insert_voter_list_row(db_session, voting_id, email.lower(), user_id=None)
        row_id = row.id  # capture before expire_all

        resp = await _register(client, email)
        assert resp.status_code == 201
        new_user_id = uuid.UUID(resp.json()["id"])

        db_session.expire_all()
        result = await db_session.execute(select(VoterList).where(VoterList.id == row_id))
        refreshed = result.scalar_one_or_none()
        assert refreshed is not None
        assert refreshed.user_id == new_user_id

    async def test_login_links_voter_list(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Login fires link_user_by_email: voter_lists.user_id must be filled."""
        voting_id = await _make_voting(db_session)
        email = f"login_link_{uuid.uuid4().hex[:6]}@test.com"

        # Register and confirm the user first (simulating account existed before being whitelisted).
        await _register(client, email)
        db_session.expire_all()
        result = await db_session.execute(select(User).where(User.email == email.lower()))
        user = result.scalar_one()
        user_id = user.id  # capture before further expire_all
        user.is_confirmed = True
        user.confirmation_token = None
        await db_session.commit()

        # Insert whitelist row AFTER account already exists but before login.
        row = await _insert_voter_list_row(db_session, voting_id, email.lower(), user_id=None)
        row_id = row.id  # capture before expire_all

        # Login should back-fill user_id.
        resp = await client.post("/auth/login", json={"email": email, "password": "Password123"})
        assert resp.status_code == 200

        db_session.expire_all()
        result2 = await db_session.execute(select(VoterList).where(VoterList.id == row_id))
        refreshed = result2.scalar_one_or_none()
        assert refreshed is not None
        assert refreshed.user_id == user_id

    async def test_link_is_case_insensitive(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Voter list row stored with uppercase email is linked to lowercase-registered user."""
        voting_id = await _make_voting(db_session)
        base_email = f"case_{uuid.uuid4().hex[:6]}@test.com"

        # Row stored with uppercase (defensive against old data).
        row = await _insert_voter_list_row(
            db_session, voting_id, base_email.upper(), user_id=None
        )
        row_id = row.id  # capture before expire_all

        # User registers with lowercase.
        resp = await _register(client, base_email.lower())
        assert resp.status_code == 201
        new_user_id = uuid.UUID(resp.json()["id"])

        db_session.expire_all()
        result = await db_session.execute(select(VoterList).where(VoterList.id == row_id))
        refreshed = result.scalar_one_or_none()
        assert refreshed is not None
        assert refreshed.user_id == new_user_id

    async def test_link_multiple_rows(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """All whitelist rows for this email (across multiple elections) are linked."""
        voting_id_a = await _make_voting(db_session)
        voting_id_b = await _make_voting(db_session)
        voting_id_c = await _make_voting(db_session)
        email = f"multi_{uuid.uuid4().hex[:6]}@test.com"

        row_a = await _insert_voter_list_row(db_session, voting_id_a, email, user_id=None)
        row_b = await _insert_voter_list_row(db_session, voting_id_b, email, user_id=None)
        row_c = await _insert_voter_list_row(db_session, voting_id_c, email, user_id=None)
        row_ids = [row_a.id, row_b.id, row_c.id]  # capture before expire_all

        resp = await _register(client, email)
        assert resp.status_code == 201
        new_user_id = uuid.UUID(resp.json()["id"])

        db_session.expire_all()
        for row_id in row_ids:
            result = await db_session.execute(select(VoterList).where(VoterList.id == row_id))
            refreshed = result.scalar_one_or_none()
            assert refreshed is not None
            assert refreshed.user_id == new_user_id, (
                f"Row {row_id} was not linked"
            )

    async def test_link_does_not_overwrite_existing_user_id(
        self, db_session: AsyncSession
    ):
        """link_user_by_email must not touch rows where user_id is already set."""
        from app.core.enums import Role

        voting_id = await _make_voting(db_session)
        email = f"noover_{uuid.uuid4().hex[:6]}@test.com"

        # A different user already owns this whitelist row.
        existing_owner = User(
            email=f"owner_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=hash_password("Password123"),
            full_name="Owner",
            role=Role.voter,
            is_confirmed=True,
        )
        db_session.add(existing_owner)
        await db_session.flush()
        await db_session.commit()
        await db_session.refresh(existing_owner)

        row = await _insert_voter_list_row(
            db_session, voting_id, email, user_id=existing_owner.id
        )
        row_id = row.id  # capture before expire_all
        owner_id = existing_owner.id  # capture before expire_all

        # A new user with a different id tries to link the same email.
        new_user = User(
            email=f"newuser_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=hash_password("Password123"),
            full_name="New",
            role=Role.voter,
            is_confirmed=True,
        )
        db_session.add(new_user)
        await db_session.flush()
        await db_session.commit()
        await db_session.refresh(new_user)
        new_user_id = new_user.id  # capture before expire_all

        repo = VoterListRepository()
        await repo.link_user_by_email(db_session, email, new_user_id)
        await db_session.commit()

        db_session.expire_all()
        result = await db_session.execute(select(VoterList).where(VoterList.id == row_id))
        refreshed = result.scalar_one_or_none()
        assert refreshed is not None
        # Must still be the original owner — not the new user.
        assert refreshed.user_id == owner_id
