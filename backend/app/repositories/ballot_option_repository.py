import uuid
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ballot_option import BallotOption


class BallotOptionRepository:
    async def get_by_id(
        self, session: AsyncSession, option_id: uuid.UUID
    ) -> Optional[BallotOption]:
        result = await session.execute(
            select(BallotOption).where(BallotOption.id == option_id)
        )
        return result.scalar_one_or_none()

    async def list_for_voting(
        self, session: AsyncSession, voting_id: uuid.UUID
    ) -> Sequence[BallotOption]:
        result = await session.execute(
            select(BallotOption)
            .where(BallotOption.voting_id == voting_id)
            .order_by(BallotOption.order_index.asc())
        )
        return list(result.scalars().all())

    async def count_for_voting(
        self, session: AsyncSession, voting_id: uuid.UUID
    ) -> int:
        result = await session.execute(
            select(func.count())
            .select_from(BallotOption)
            .where(BallotOption.voting_id == voting_id)
        )
        return int(result.scalar_one())

    async def next_order_index(
        self, session: AsyncSession, voting_id: uuid.UUID
    ) -> int:
        result = await session.execute(
            select(func.max(BallotOption.order_index)).where(
                BallotOption.voting_id == voting_id
            )
        )
        current_max = result.scalar_one_or_none()
        if current_max is None:
            return 0
        return int(current_max) + 1

    async def create(
        self,
        session: AsyncSession,
        *,
        voting_id: uuid.UUID,
        title: str,
        description: Optional[str],
        order_index: int,
    ) -> BallotOption:
        option = BallotOption(
            voting_id=voting_id,
            title=title,
            description=description,
            order_index=order_index,
        )
        session.add(option)
        await session.flush()
        return option

    async def update(
        self,
        session: AsyncSession,
        option: BallotOption,
        **kwargs: object,
    ) -> BallotOption:
        for key, value in kwargs.items():
            setattr(option, key, value)
        await session.flush()
        return option

    async def delete(
        self, session: AsyncSession, option: BallotOption
    ) -> None:
        await session.delete(option)
        await session.flush()
