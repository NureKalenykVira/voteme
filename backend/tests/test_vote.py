import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Role, VotingStatus
from app.core.security import create_access_token, hash_password
from app.models.audit_log import AuditLog
from app.models.user import User
from app.models.vote import Vote
from app.models.voter_list import VoterList
from app.models.voting import Voting
from app.models.voting_participation import VotingParticipation


pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _make_user(
    db_session: AsyncSession,
    email: str,
    role: Role = Role.voter,
) -> User:
    user = User(
        email=email.lower(),
        hashed_password=hash_password("Password123"),
        full_name="Voter User",
        role=role,
        is_confirmed=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def _auth(user: User) -> dict:
    token = create_access_token(sub=str(user.id), role=user.role)
    return {"Authorization": f"Bearer {token}"}


def _future_window(start_seconds: int = 3600, duration_seconds: int = 3600):
    start = datetime.now(timezone.utc) + timedelta(seconds=start_seconds)
    end = start + timedelta(seconds=duration_seconds)
    return start.isoformat(), end.isoformat()


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
    response = await client.post("/elections/", headers=_auth(organizer), json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def _add_option(client: AsyncClient, organizer: User, voting_id: str, title: str) -> dict:
    response = await client.post(
        f"/elections/{voting_id}/options",
        headers=_auth(organizer),
        json={"title": title},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _make_active_voting(
    client: AsyncClient,
    db_session: AsyncSession,
    organizer: User,
    *,
    access_type: str = "public",
    is_anonymous: bool = False,
):
    voting = await _create_voting(
        client,
        organizer,
        access_type=access_type,
        is_anonymous=is_anonymous,
    )
    vid = voting["id"]
    a = await _add_option(client, organizer, vid, "A")
    b = await _add_option(client, organizer, vid, "B")
    pub = await client.post(f"/elections/{vid}/publish", headers=_auth(organizer))
    assert pub.status_code == 200, pub.text

    result = await db_session.execute(select(Voting).where(Voting.id == uuid.UUID(vid)))
    v = result.scalar_one()
    v.status = VotingStatus.active
    await db_session.commit()
    return voting, [a, b]


class TestSubmitVote:
    async def test_submit_vote_public_succeeds(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "vt_org1@example.com", Role.organizer)
        voter = await _make_user(db_session, "vt_v1@example.com")
        voting, options = await _make_active_voting(client, db_session, organizer)
        vid = voting["id"]

        response = await client.post(
            f"/elections/{vid}/vote",
            headers=_auth(voter),
            json={"option_id": options[0]["id"]},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert "vote_id" in body
        assert "commitment_hash" in body
        assert body["tx_status"] == "pending"
        assert len(body["commitment_hash"]) == 64

    async def test_duplicate_vote_returns_409(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "vt_org2@example.com", Role.organizer)
        voter = await _make_user(db_session, "vt_v2@example.com")
        voting, options = await _make_active_voting(client, db_session, organizer)
        vid = voting["id"]

        first = await client.post(
            f"/elections/{vid}/vote",
            headers=_auth(voter),
            json={"option_id": options[0]["id"]},
        )
        assert first.status_code == 201

        second = await client.post(
            f"/elections/{vid}/vote",
            headers=_auth(voter),
            json={"option_id": options[1]["id"]},
        )
        assert second.status_code == 409
        assert "already voted" in second.json()["detail"].lower()

    async def test_vote_in_draft_returns_409(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "vt_org3@example.com", Role.organizer)
        voter = await _make_user(db_session, "vt_v3@example.com")
        voting = await _create_voting(client, organizer)
        vid = voting["id"]
        a = await _add_option(client, organizer, vid, "A")

        response = await client.post(
            f"/elections/{vid}/vote",
            headers=_auth(voter),
            json={"option_id": a["id"]},
        )
        assert response.status_code == 409

    async def test_vote_with_bad_option_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "vt_org4@example.com", Role.organizer)
        voter = await _make_user(db_session, "vt_v4@example.com")
        voting, _ = await _make_active_voting(client, db_session, organizer)
        vid = voting["id"]

        response = await client.post(
            f"/elections/{vid}/vote",
            headers=_auth(voter),
            json={"option_id": str(uuid.uuid4())},
        )
        assert response.status_code == 404


    async def test_private_election_non_whitelisted_returns_403(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "vt_org5@example.com", Role.organizer)
        outsider = await _make_user(db_session, "vt_v5@example.com")
        voting, options = await _make_active_voting(
            client, db_session, organizer, access_type="private"
        )
        vid = voting["id"]

        response = await client.post(
            f"/elections/{vid}/vote",
            headers=_auth(outsider),
            json={"option_id": options[0]["id"]},
        )
        assert response.status_code == 403

    async def test_private_election_whitelisted_succeeds(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "vt_org6@example.com", Role.organizer)
        voter = await _make_user(db_session, "vt_v6@example.com")
        voting, options = await _make_active_voting(
            client, db_session, organizer, access_type="private"
        )
        vid = voting["id"]

        db_session.add(
            VoterList(
                voting_id=uuid.UUID(vid),
                email=voter.email,
                user_id=voter.id,
            )
        )
        await db_session.commit()

        response = await client.post(
            f"/elections/{vid}/vote",
            headers=_auth(voter),
            json={"option_id": options[0]["id"]},
        )
        assert response.status_code == 201

    async def test_vote_writes_voting_participation(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "vt_org7@example.com", Role.organizer)
        voter = await _make_user(db_session, "vt_v7@example.com")
        voting, options = await _make_active_voting(client, db_session, organizer)
        vid = voting["id"]

        await client.post(
            f"/elections/{vid}/vote",
            headers=_auth(voter),
            json={"option_id": options[0]["id"]},
        )

        result = await db_session.execute(
            select(VotingParticipation).where(
                VotingParticipation.voting_id == uuid.UUID(vid),
                VotingParticipation.user_id == voter.id,
            )
        )
        assert result.scalar_one_or_none() is not None

    async def test_anonymous_vote_audit_actor_is_null(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "vt_org8@example.com", Role.organizer)
        voter = await _make_user(db_session, "vt_v8@example.com")
        voting, options = await _make_active_voting(
            client, db_session, organizer, is_anonymous=True
        )
        vid = voting["id"]

        await client.post(
            f"/elections/{vid}/vote",
            headers=_auth(voter),
            json={"option_id": options[0]["id"]},
        )

        result = await db_session.execute(
            select(AuditLog).where(AuditLog.action == "VOTE_SUBMITTED")
        )
        entries = list(result.scalars().all())
        assert any(e.actor_id is None and e.data.get("voting_id") == vid for e in entries)

    async def test_non_anonymous_vote_audit_actor_is_user(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "vt_org9@example.com", Role.organizer)
        voter = await _make_user(db_session, "vt_v9@example.com")
        voting, options = await _make_active_voting(client, db_session, organizer)
        vid = voting["id"]

        await client.post(
            f"/elections/{vid}/vote",
            headers=_auth(voter),
            json={"option_id": options[0]["id"]},
        )

        result = await db_session.execute(
            select(AuditLog).where(AuditLog.action == "VOTE_SUBMITTED")
        )
        entries = list(result.scalars().all())
        assert any(e.actor_id == voter.id and e.data.get("voting_id") == vid for e in entries)

    async def test_unauthenticated_vote_returns_401(self, client: AsyncClient):
        response = await client.post(
            f"/elections/{uuid.uuid4()}/vote",
            json={"option_id": str(uuid.uuid4())},
        )
        assert response.status_code == 401

    async def test_concurrent_votes_only_one_succeeds(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "vt_race_org@example.com", Role.organizer)
        voter = await _make_user(db_session, "vt_race_voter@example.com")
        voting, options = await _make_active_voting(client, db_session, organizer)
        vid = voting["id"]

        responses = await asyncio.gather(
            *[
                client.post(
                    f"/elections/{vid}/vote",
                    headers=_auth(voter),
                    json={"option_id": options[0]["id"]},
                )
                for _ in range(5)
            ]
        )

        status_codes = [r.status_code for r in responses]
        assert status_codes.count(201) == 1, f"Expected 1×201, got: {status_codes}"
        assert status_codes.count(409) == 4, f"Expected 4×409, got: {status_codes}"

        result = await db_session.execute(
            select(func.count()).select_from(Vote).where(
                Vote.voting_id == uuid.UUID(vid),
                Vote.user_id == voter.id,
            )
        )
        count = result.scalar_one()
        assert count == 1, f"Expected exactly 1 vote in DB, got: {count}"


class TestMyVote:
    async def test_my_vote_returns_false_before_voting(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "mv_org1@example.com", Role.organizer)
        voter = await _make_user(db_session, "mv_v1@example.com")
        voting, _ = await _make_active_voting(client, db_session, organizer)
        vid = voting["id"]

        response = await client.get(
            f"/elections/{vid}/my-vote", headers=_auth(voter)
        )
        assert response.status_code == 200
        body = response.json()
        assert body["has_voted"] is False
        assert body.get("option_id") is None

    async def test_my_vote_returns_record_after_voting(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "mv_org2@example.com", Role.organizer)
        voter = await _make_user(db_session, "mv_v2@example.com")
        voting, options = await _make_active_voting(client, db_session, organizer)
        vid = voting["id"]

        await client.post(
            f"/elections/{vid}/vote",
            headers=_auth(voter),
            json={"option_id": options[0]["id"]},
        )

        response = await client.get(
            f"/elections/{vid}/my-vote", headers=_auth(voter)
        )
        assert response.status_code == 200
        body = response.json()
        assert body["has_voted"] is True
        assert body["option_id"] == options[0]["id"]
        assert body["tx_status"] == "pending"
        assert body["commitment_hash"] is not None

    async def test_my_vote_anonymous_omits_option_id(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "mv_org3@example.com", Role.organizer)
        voter = await _make_user(db_session, "mv_v3@example.com")
        voting, options = await _make_active_voting(
            client, db_session, organizer, is_anonymous=True
        )
        vid = voting["id"]

        await client.post(
            f"/elections/{vid}/vote",
            headers=_auth(voter),
            json={"option_id": options[0]["id"]},
        )

        response = await client.get(
            f"/elections/{vid}/my-vote", headers=_auth(voter)
        )
        assert response.status_code == 200
        body = response.json()
        assert body["has_voted"] is True
        assert body.get("option_id") is None
        assert body.get("submitted_at") is None
        assert body["commitment_hash"] is not None

    async def test_my_vote_unknown_election_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        voter = await _make_user(db_session, "mv_v4@example.com")
        response = await client.get(
            f"/elections/{uuid.uuid4()}/my-vote", headers=_auth(voter)
        )
        assert response.status_code == 404
