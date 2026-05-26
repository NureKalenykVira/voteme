from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Role, VotingAccessType, VotingStatus
from app.core.security import hash_password
from app.models.user import User
from app.models.voting import Voting
from app.repositories.voting_repository import VotingRepository
from app.scheduler.voting_scheduler import _run_catch_up, _run_tick


pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _organizer(db_session: AsyncSession, email: str) -> User:
    user = User(
        email=email.lower(),
        hashed_password=hash_password("Password123"),
        full_name="Org",
        role=Role.organizer,
        is_confirmed=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _voting(
    db_session: AsyncSession,
    user: User,
    *,
    status: VotingStatus,
    start_offset_sec: int,
    end_offset_sec: int,
) -> Voting:
    now = datetime.now(timezone.utc)
    voting = Voting(
        title="Sched",
        description=None,
        access_type=VotingAccessType.public,
        is_anonymous=False,
        start_date_time=now + timedelta(seconds=start_offset_sec),
        end_date_time=now + timedelta(seconds=end_offset_sec),
        status=status,
        created_by=user.id,
    )
    db_session.add(voting)
    await db_session.commit()
    await db_session.refresh(voting)
    return voting


class TestCatchUpOnBoot:
    async def test_catch_up_no_overdue_does_nothing(
        self, db_session: AsyncSession
    ):
        user = await _organizer(db_session, "sched_user1@example.com")
        await _voting(
            db_session,
            user,
            status=VotingStatus.published,
            start_offset_sec=+3600,
            end_offset_sec=+7200,
        )
        applied = await _run_catch_up(db_session)
        assert applied == 0

    async def test_catch_up_published_to_active(
        self, db_session: AsyncSession
    ):
        user = await _organizer(db_session, "sched_user2@example.com")
        voting = await _voting(
            db_session,
            user,
            status=VotingStatus.published,
            start_offset_sec=-300,
            end_offset_sec=+3600,
        )
        applied = await _run_catch_up(db_session)
        assert applied == 1

        repo = VotingRepository()
        reloaded = await repo.get_by_id(db_session, voting.id)
        assert reloaded.status == VotingStatus.active

    async def test_catch_up_published_to_finished_in_one_run(
        self, db_session: AsyncSession
    ):
        user = await _organizer(db_session, "sched_user3@example.com")
        voting = await _voting(
            db_session,
            user,
            status=VotingStatus.published,
            start_offset_sec=-3600,
            end_offset_sec=-60,
        )
        applied = await _run_catch_up(db_session)
        assert applied == 1

        repo = VotingRepository()
        reloaded = await repo.get_by_id(db_session, voting.id)
        assert reloaded.status == VotingStatus.finished

    async def test_catch_up_is_idempotent(
        self, db_session: AsyncSession
    ):
        user = await _organizer(db_session, "sched_user4@example.com")
        await _voting(
            db_session,
            user,
            status=VotingStatus.published,
            start_offset_sec=-3600,
            end_offset_sec=-60,
        )
        first = await _run_catch_up(db_session)
        second = await _run_catch_up(db_session)
        assert first == 1
        assert second == 0


class TestTick:
    async def test_tick_promotes_published_to_active(
        self, db_session: AsyncSession
    ):
        user = await _organizer(db_session, "tick_user1@example.com")
        voting = await _voting(
            db_session,
            user,
            status=VotingStatus.published,
            start_offset_sec=-10,
            end_offset_sec=+3600,
        )
        applied = await _run_tick(db_session)
        assert applied == 1

        repo = VotingRepository()
        reloaded = await repo.get_by_id(db_session, voting.id)
        assert reloaded.status == VotingStatus.active

    async def test_tick_finishes_active_after_end(
        self, db_session: AsyncSession
    ):
        user = await _organizer(db_session, "tick_user2@example.com")
        voting = await _voting(
            db_session,
            user,
            status=VotingStatus.active,
            start_offset_sec=-3600,
            end_offset_sec=-10,
        )
        applied = await _run_tick(db_session)
        assert applied == 1

        repo = VotingRepository()
        reloaded = await repo.get_by_id(db_session, voting.id)
        assert reloaded.status == VotingStatus.finished

    async def test_tick_idempotent_when_nothing_to_do(
        self, db_session: AsyncSession
    ):
        user = await _organizer(db_session, "tick_user3@example.com")
        await _voting(
            db_session,
            user,
            status=VotingStatus.published,
            start_offset_sec=+3600,
            end_offset_sec=+7200,
        )
        applied = await _run_tick(db_session)
        assert applied == 0

    async def test_tick_ignores_draft_and_finished(
        self, db_session: AsyncSession
    ):
        user = await _organizer(db_session, "tick_user4@example.com")
        draft = await _voting(
            db_session,
            user,
            status=VotingStatus.draft,
            start_offset_sec=-3600,
            end_offset_sec=-60,
        )
        await _voting(
            db_session,
            user,
            status=VotingStatus.finished,
            start_offset_sec=-7200,
            end_offset_sec=-3600,
        )
        applied = await _run_tick(db_session)
        assert applied == 0

        repo = VotingRepository()
        reloaded = await repo.get_by_id(db_session, draft.id)
        assert reloaded.status == VotingStatus.draft
