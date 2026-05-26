import uuid
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import VotingStatus
from app.models.ballot_option import BallotOption
from app.models.voting import Voting
from app.models.voting_participation import VotingParticipation


class VotingRepository:
    async def get_by_id(
        self, session: AsyncSession, voting_id: uuid.UUID
    ) -> Optional[Voting]:
        result = await session.execute(
            select(Voting).where(
                Voting.id == voting_id,
                Voting.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_options(
        self, session: AsyncSession, voting_id: uuid.UUID
    ) -> Optional[tuple[Voting, list[BallotOption]]]:
        voting = await self.get_by_id(session, voting_id)
        if voting is None:
            return None
        opts_result = await session.execute(
            select(BallotOption)
            .where(BallotOption.voting_id == voting_id)
            .order_by(BallotOption.order_index.asc())
        )
        options = list(opts_result.scalars().all())
        return voting, options

    async def get_by_invitation_code(
        self, session: AsyncSession, code: str
    ) -> Optional[Voting]:
        result = await session.execute(
            select(Voting).where(
                Voting.invitation_code == code,
                Voting.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def count_participants(
        self, session: AsyncSession, voting_id: uuid.UUID
    ) -> int:
        result = await session.execute(
            select(func.count()).where(
                VotingParticipation.voting_id == voting_id
            )
        )
        return result.scalar_one() or 0

    async def has_user_voted(
        self, session: AsyncSession, voting_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        result = await session.execute(
            select(func.count()).where(
                VotingParticipation.voting_id == voting_id,
                VotingParticipation.user_id == user_id,
            )
        )
        return (result.scalar_one() or 0) > 0

    async def create(
        self,
        session: AsyncSession,
        *,
        title: str,
        description: Optional[str],
        access_type,
        is_anonymous: bool,
        start_date_time: datetime,
        end_date_time: datetime,
        created_by: uuid.UUID,
        invitation_code: Optional[str] = None,
    ) -> Voting:
        voting = Voting(
            title=title,
            description=description,
            access_type=access_type,
            is_anonymous=is_anonymous,
            start_date_time=start_date_time,
            end_date_time=end_date_time,
            created_by=created_by,
            invitation_code=invitation_code,
        )
        session.add(voting)
        await session.flush()
        return voting

    async def update(
        self, session: AsyncSession, voting: Voting, **kwargs: object
    ) -> Voting:
        for key, value in kwargs.items():
            setattr(voting, key, value)
        await session.flush()
        return voting

    async def list_for_organizer(
        self,
        session: AsyncSession,
        organizer_id: uuid.UUID,
        status: Optional[VotingStatus],
        page: int,
        page_size: int,
    ) -> tuple[Sequence[Voting], int]:
        base_filter = [
            Voting.created_by == organizer_id,
            Voting.is_deleted == False,  # noqa: E712
        ]
        if status is not None:
            base_filter.append(Voting.status == status)

        total_result = await session.execute(
            select(func.count()).select_from(Voting).where(*base_filter)
        )
        total = int(total_result.scalar_one())

        offset = (page - 1) * page_size
        items_result = await session.execute(
            select(Voting)
            .where(*base_filter)
            .order_by(Voting.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = list(items_result.scalars().all())
        return items, total

    async def list_all(
        self,
        session: AsyncSession,
        status: Optional[VotingStatus],
        page: int,
        page_size: int,
    ) -> tuple[Sequence[Voting], int]:
        base_filter = [Voting.is_deleted == False]  # noqa: E712
        if status is not None:
            base_filter.append(Voting.status == status)

        total_result = await session.execute(
            select(func.count()).select_from(Voting).where(*base_filter)
        )
        total = int(total_result.scalar_one())

        offset = (page - 1) * page_size
        items_result = await session.execute(
            select(Voting)
            .where(*base_filter)
            .order_by(Voting.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = list(items_result.scalars().all())
        return items, total

    async def find_due_for_start(
        self, session: AsyncSession, now: datetime
    ) -> Sequence[Voting]:
        result = await session.execute(
            select(Voting).where(
                Voting.status == VotingStatus.published,
                Voting.start_date_time <= now,
                Voting.is_deleted == False,  # noqa: E712
            )
        )
        return list(result.scalars().all())

    async def find_due_for_end(
        self, session: AsyncSession, now: datetime
    ) -> Sequence[Voting]:
        result = await session.execute(
            select(Voting).where(
                Voting.status == VotingStatus.active,
                Voting.end_date_time <= now,
                Voting.is_deleted == False,  # noqa: E712
            )
        )
        return list(result.scalars().all())

    async def find_pending_lifecycle(
        self, session: AsyncSession
    ) -> Sequence[Voting]:
        result = await session.execute(
            select(Voting).where(
                Voting.status.in_(
                    [VotingStatus.published, VotingStatus.active]
                ),
                Voting.is_deleted == False,  # noqa: E712
            )
        )
        return list(result.scalars().all())
