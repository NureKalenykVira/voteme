import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vote_result import VoteResult


class VoteResultRepository:
    async def upsert_results(
        self,
        session: AsyncSession,
        voting_id: uuid.UUID,
        counts: dict[uuid.UUID, int],
    ) -> None:
        if not counts:
            return

        rows = [
            {
                "voting_id": voting_id,
                "option_id": option_id,
                "votes_count": count,
            }
            for option_id, count in counts.items()
        ]
        stmt = pg_insert(VoteResult).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_vote_result_voting_option",
            set_={"votes_count": stmt.excluded.votes_count},
        )
        await session.execute(stmt)

    async def get_for_voting(
        self, session: AsyncSession, voting_id: uuid.UUID
    ) -> list[VoteResult]:
        result = await session.execute(
            select(VoteResult)
            .where(VoteResult.voting_id == voting_id)
            .order_by(VoteResult.votes_count.desc())
        )
        return list(result.scalars().all())
