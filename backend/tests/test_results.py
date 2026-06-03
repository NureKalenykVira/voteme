import secrets
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Role, VotingAccessType, VotingStatus
from app.core.security import create_access_token, hash_password
from app.models.ballot_option import BallotOption
from app.models.user import User
from app.models.vote import Vote
from app.models.vote_result import VoteResult
from app.models.voter_list import VoterList
from app.models.voting import Voting


pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _make_user(
    db_session: AsyncSession,
    email: str,
    role: Role = Role.voter,
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


async def _make_finished_election(
    db_session: AsyncSession,
    organizer: User,
    *,
    voters: list[User] | None = None,
    finalize_tx_hash: str | None = "0xabc",
    status: VotingStatus = VotingStatus.finished,
) -> dict:
    """Create a finished election with 2 options, one vote per provided voter,
    and matching VoteResult rows. Returns ids needed by tests."""
    start = datetime.now(timezone.utc) - timedelta(hours=2)
    end = datetime.now(timezone.utc) - timedelta(hours=1)
    voting = Voting(
        title="Finished Election",
        description="d",
        access_type=VotingAccessType.public,
        is_anonymous=False,
        start_date_time=start,
        end_date_time=end,
        status=status,
        created_by=organizer.id,
        invitation_code=uuid.uuid4().hex,
        finalize_tx_hash=finalize_tx_hash,
    )
    db_session.add(voting)
    await db_session.flush()

    option_a = BallotOption(
        voting_id=voting.id, title="A", order_index=0
    )
    option_b = BallotOption(
        voting_id=voting.id, title="B", order_index=1
    )
    db_session.add_all([option_a, option_b])
    await db_session.flush()

    votes: list[Vote] = []
    voters = voters or []
    for i, voter in enumerate(voters):
        vote = Vote(
            voting_id=voting.id,
            user_id=voter.id,
            option_id=option_a.id,
            commitment_hash=secrets.token_hex(32),
            nonce=secrets.token_hex(32),
            submitted_at=start + timedelta(minutes=i + 1),
        )
        db_session.add(vote)
        db_session.add(
            VoterList(
                voting_id=voting.id, email=voter.email, user_id=voter.id
            )
        )
        votes.append(vote)
    await db_session.flush()

    db_session.add(
        VoteResult(
            voting_id=voting.id,
            option_id=option_a.id,
            votes_count=len(voters),
        )
    )
    db_session.add(
        VoteResult(voting_id=voting.id, option_id=option_b.id, votes_count=0)
    )
    await db_session.commit()

    return {
        "voting_id": voting.id,
        "option_a_id": option_a.id,
        "option_b_id": option_b.id,
        "vote_ids": [v.id for v in votes],
    }


class TestResults:
    async def test_results_returns_counts(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "res_org@example.com", Role.organizer)
        voter = await _make_user(db_session, "res_voter@example.com")
        setup = await _make_finished_election(
            db_session, organizer, voters=[voter]
        )
        response = await client.get(f"/elections/{setup['voting_id']}/results")
        assert response.status_code == 200
        body = response.json()
        assert body["total_votes"] == 1
        assert len(body["options"]) == 2
        winner = body["options"][0]
        assert winner["votes_count"] == 1
        assert winner["percentage"] == 100.0

    async def test_results_is_public_no_auth(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "res_pub_org@example.com", Role.organizer)
        setup = await _make_finished_election(db_session, organizer, voters=[])
        response = await client.get(f"/elections/{setup['voting_id']}/results")
        assert response.status_code == 200
        assert response.json()["is_organizer"] is False

    async def test_results_organizer_flag_true(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "res_flag_org@example.com", Role.organizer)
        setup = await _make_finished_election(db_session, organizer, voters=[])
        response = await client.get(
            f"/elections/{setup['voting_id']}/results",
            headers=_auth(organizer),
        )
        assert response.status_code == 200
        assert response.json()["is_organizer"] is True

    async def test_results_draft_returns_409(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "res_draft_org@example.com", Role.organizer)
        setup = await _make_finished_election(
            db_session, organizer, voters=[], status=VotingStatus.draft
        )
        response = await client.get(f"/elections/{setup['voting_id']}/results")
        assert response.status_code == 409

    async def test_results_unknown_election_returns_404(
        self, client: AsyncClient
    ):
        response = await client.get(f"/elections/{uuid.uuid4()}/results")
        assert response.status_code == 404


class TestTimeline:
    async def test_timeline_returns_buckets(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "tl_org@example.com", Role.organizer)
        voter = await _make_user(db_session, "tl_voter@example.com")
        setup = await _make_finished_election(
            db_session, organizer, voters=[voter]
        )
        response = await client.get(
            f"/elections/{setup['voting_id']}/timeline",
            headers=_auth(organizer),
        )
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body["buckets"], list)
        assert len(body["buckets"]) >= 3
        assert isinstance(body["date_range"], str)

    async def test_timeline_non_owner_returns_403(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "tl_owner@example.com", Role.organizer)
        stranger = await _make_user(db_session, "tl_stranger@example.com", Role.organizer)
        setup = await _make_finished_election(db_session, organizer, voters=[])
        response = await client.get(
            f"/elections/{setup['voting_id']}/timeline",
            headers=_auth(stranger),
        )
        assert response.status_code == 403

    async def test_timeline_unknown_election_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "tl_404_org@example.com", Role.organizer)
        response = await client.get(
            f"/elections/{uuid.uuid4()}/timeline",
            headers=_auth(organizer),
        )
        assert response.status_code == 404

    async def test_timeline_without_token_returns_401(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "tl_401_org@example.com", Role.organizer)
        setup = await _make_finished_election(db_session, organizer, voters=[])
        response = await client.get(f"/elections/{setup['voting_id']}/timeline")
        assert response.status_code == 401


class TestProof:
    async def test_proof_for_own_vote_returns_200(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "pf_org@example.com", Role.organizer)
        voter = await _make_user(db_session, "pf_voter@example.com")
        setup = await _make_finished_election(
            db_session, organizer, voters=[voter]
        )
        vote_id = setup["vote_ids"][0]
        response = await client.get(
            f"/elections/{setup['voting_id']}/proof?vote_id={vote_id}",
            headers=_auth(voter),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["vote_id"] == str(vote_id)
        assert body["leaf"].startswith("0x")
        assert body["computed_root"].startswith("0x")
        assert body["total_leaves"] == 1

    async def test_proof_organizer_can_access_any(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "pf_org2@example.com", Role.organizer)
        voter = await _make_user(db_session, "pf_voter2@example.com")
        setup = await _make_finished_election(
            db_session, organizer, voters=[voter]
        )
        vote_id = setup["vote_ids"][0]
        response = await client.get(
            f"/elections/{setup['voting_id']}/proof?vote_id={vote_id}",
            headers=_auth(organizer),
        )
        assert response.status_code == 200

    async def test_proof_other_voter_returns_403(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "pf_org3@example.com", Role.organizer)
        voter = await _make_user(db_session, "pf_voter3@example.com")
        outsider = await _make_user(db_session, "pf_outsider3@example.com")
        setup = await _make_finished_election(
            db_session, organizer, voters=[voter]
        )
        vote_id = setup["vote_ids"][0]
        response = await client.get(
            f"/elections/{setup['voting_id']}/proof?vote_id={vote_id}",
            headers=_auth(outsider),
        )
        assert response.status_code == 403

    async def test_proof_unknown_vote_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "pf_org4@example.com", Role.organizer)
        voter = await _make_user(db_session, "pf_voter4@example.com")
        setup = await _make_finished_election(
            db_session, organizer, voters=[voter]
        )
        response = await client.get(
            f"/elections/{setup['voting_id']}/proof?vote_id={uuid.uuid4()}",
            headers=_auth(organizer),
        )
        assert response.status_code == 404

    async def test_proof_not_finalized_returns_409(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "pf_org5@example.com", Role.organizer)
        voter = await _make_user(db_session, "pf_voter5@example.com")
        setup = await _make_finished_election(
            db_session, organizer, voters=[voter], status=VotingStatus.active
        )
        vote_id = setup["vote_ids"][0]
        response = await client.get(
            f"/elections/{setup['voting_id']}/proof?vote_id={vote_id}",
            headers=_auth(voter),
        )
        assert response.status_code == 409


class TestReceipt:
    async def test_receipt_for_voter_returns_200(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "rc_org@example.com", Role.organizer)
        voter = await _make_user(db_session, "rc_voter@example.com")
        setup = await _make_finished_election(
            db_session, organizer, voters=[voter]
        )
        response = await client.get(
            f"/elections/{setup['voting_id']}/receipt",
            headers=_auth(voter),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["commitment"].startswith("0x")
        assert body["nonce"].startswith("0x")
        assert body["expected_root"].startswith("0x")
        assert body["etherscan_url"] is not None

    async def test_receipt_non_voter_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "rc_org2@example.com", Role.organizer)
        voter = await _make_user(db_session, "rc_voter2@example.com")
        outsider = await _make_user(db_session, "rc_outsider2@example.com")
        setup = await _make_finished_election(
            db_session, organizer, voters=[voter]
        )
        response = await client.get(
            f"/elections/{setup['voting_id']}/receipt",
            headers=_auth(outsider),
        )
        assert response.status_code == 404

    async def test_receipt_not_finalized_returns_409(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "rc_org3@example.com", Role.organizer)
        voter = await _make_user(db_session, "rc_voter3@example.com")
        setup = await _make_finished_election(
            db_session, organizer, voters=[voter], status=VotingStatus.active
        )
        response = await client.get(
            f"/elections/{setup['voting_id']}/receipt",
            headers=_auth(voter),
        )
        assert response.status_code == 409

    async def test_receipt_without_token_returns_401(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        organizer = await _make_user(db_session, "rc_org4@example.com", Role.organizer)
        setup = await _make_finished_election(db_session, organizer, voters=[])
        response = await client.get(f"/elections/{setup['voting_id']}/receipt")
        assert response.status_code == 401
