import uuid

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.election_auditor import ElectionAuditor


class ElectionAuditorRepository:
    async def add(
        self,
        session: AsyncSession,
        voting_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ElectionAuditor:
        stmt = (
            pg_insert(ElectionAuditor)
            .values(voting_id=voting_id, user_id=user_id)
            .on_conflict_do_nothing(
                index_elements=["voting_id", "user_id"]
            )
        )
        await session.execute(stmt)
        await session.flush()

        result = await session.execute(
            select(ElectionAuditor).where(
                ElectionAuditor.voting_id == voting_id,
                ElectionAuditor.user_id == user_id,
            )
        )
        return result.scalar_one()

    async def remove(
        self,
        session: AsyncSession,
        voting_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        result = await session.execute(
            delete(ElectionAuditor).where(
                ElectionAuditor.voting_id == voting_id,
                ElectionAuditor.user_id == user_id,
            )
        )
        await session.flush()
        return result.rowcount > 0

    async def list_for_voting(
        self,
        session: AsyncSession,
        voting_id: uuid.UUID,
    ) -> list[ElectionAuditor]:
        result = await session.execute(
            select(ElectionAuditor)
            .where(ElectionAuditor.voting_id == voting_id)
            .order_by(ElectionAuditor.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_voting_ids_for_user(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
    ) -> list[uuid.UUID]:
        result = await session.execute(
            select(ElectionAuditor.voting_id).where(
                ElectionAuditor.user_id == user_id
            )
        )
        return list(result.scalars().all())

    async def is_auditor_for(
        self,
        session: AsyncSession,
        voting_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        result = await session.execute(
            select(ElectionAuditor).where(
                ElectionAuditor.voting_id == voting_id,
                ElectionAuditor.user_id == user_id,
            )
        )
        return result.scalar_one_or_none() is not None
