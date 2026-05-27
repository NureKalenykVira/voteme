import uuid
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.voter_list import VoterList


class VoterListRepository:
    async def get_by_id(
        self, session: AsyncSession, voter_id: uuid.UUID
    ) -> Optional[VoterList]:
        result = await session.execute(
            select(VoterList).where(VoterList.id == voter_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(
        self, session: AsyncSession, voting_id: uuid.UUID, email: str
    ) -> Optional[VoterList]:
        normalized = email.lower().strip()
        result = await session.execute(
            select(VoterList).where(
                VoterList.voting_id == voting_id,
                VoterList.email == normalized,
            )
        )
        return result.scalar_one_or_none()

    async def count_for_voting(
        self, session: AsyncSession, voting_id: uuid.UUID
    ) -> int:
        result = await session.execute(
            select(func.count())
            .select_from(VoterList)
            .where(VoterList.voting_id == voting_id)
        )
        return int(result.scalar_one())

    async def list_paginated(
        self,
        session: AsyncSession,
        voting_id: uuid.UUID,
        page: int,
        page_size: int,
    ) -> tuple[list[VoterList], int]:
        total_result = await session.execute(
            select(func.count())
            .select_from(VoterList)
            .where(VoterList.voting_id == voting_id)
        )
        total = int(total_result.scalar_one())

        offset = (page - 1) * page_size
        items_result = await session.execute(
            select(VoterList)
            .where(VoterList.voting_id == voting_id)
            .order_by(VoterList.invited_at.asc())
            .offset(offset)
            .limit(page_size)
        )
        items = list(items_result.scalars().all())
        return items, total

    async def add(
        self,
        session: AsyncSession,
        voting_id: uuid.UUID,
        email: str,
        user_id: Optional[uuid.UUID],
    ) -> VoterList:
        voter = VoterList(
            voting_id=voting_id,
            email=email,
            user_id=user_id,
        )
        session.add(voter)
        await session.flush()
        return voter

    async def ensure_member(
        self,
        session: AsyncSession,
        voting_id: uuid.UUID,
        email: str,
        user_id: uuid.UUID,
    ) -> None:
        stmt = (
            pg_insert(VoterList)
            .values(
                voting_id=voting_id,
                email=email.lower(),
                user_id=user_id,
            )
            .on_conflict_do_update(
                index_elements=["voting_id", "email"],
                set_={"user_id": user_id},
                where=VoterList.user_id.is_(None),
            )
        )
        await session.execute(stmt)

    async def link_user_by_email(
        self,
        session: AsyncSession,
        email: str,
        user_id: uuid.UUID,
    ) -> None:
        await session.execute(
            update(VoterList)
            .where(
                func.lower(VoterList.email) == email.lower(),
                VoterList.user_id.is_(None),
            )
            .values(user_id=user_id)
        )

    async def delete(
        self, session: AsyncSession, voter: VoterList
    ) -> None:
        await session.delete(voter)
        await session.flush()
