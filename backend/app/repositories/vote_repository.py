import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vote import Vote


class VoteRepository:
    async def get_for_user(
        self,
        session: AsyncSession,
        voting_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Optional[Vote]:
        result = await session.execute(
            select(Vote).where(
                Vote.voting_id == voting_id,
                Vote.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def exists_for_user(
        self,
        session: AsyncSession,
        voting_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        result = await session.execute(
            select(func.count()).where(
                Vote.voting_id == voting_id,
                Vote.user_id == user_id,
            )
        )
        return (result.scalar_one() or 0) > 0

    async def create(
        self,
        session: AsyncSession,
        *,
        voting_id: uuid.UUID,
        user_id: uuid.UUID,
        option_id: uuid.UUID,
        commitment_hash: str,
        nonce: str,
        ip_address: Optional[str] = None,
    ) -> Vote:
        vote = Vote(
            voting_id=voting_id,
            user_id=user_id,
            option_id=option_id,
            commitment_hash=commitment_hash,
            nonce=nonce,
            ip_address=ip_address,
        )
        session.add(vote)
        await session.flush()
        return vote

    async def count_for_voting(
        self, session: AsyncSession, voting_id: uuid.UUID
    ) -> int:
        result = await session.execute(
            select(func.count()).where(Vote.voting_id == voting_id)
        )
        return int(result.scalar_one() or 0)

    async def list_for_voting_ordered(
        self, session: AsyncSession, voting_id: uuid.UUID
    ) -> list[Vote]:
        """
        Return all votes for a given election ordered by submitted_at ASC, id ASC.
        Stable deterministic ordering for Merkle leaf assembly.
        """
        result = await session.execute(
            select(Vote)
            .where(Vote.voting_id == voting_id)
            .order_by(Vote.submitted_at.asc(), Vote.id.asc())
        )
        return list(result.scalars().all())
