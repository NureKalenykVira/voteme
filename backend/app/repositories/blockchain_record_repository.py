import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import BlockchainRecordStatus
from app.models.blockchain_record import BlockchainRecord


class BlockchainRecordRepository:
    async def get_by_vote_id(
        self, session: AsyncSession, vote_id: uuid.UUID
    ) -> Optional[BlockchainRecord]:
        result = await session.execute(
            select(BlockchainRecord).where(BlockchainRecord.vote_id == vote_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        session: AsyncSession,
        *,
        vote_id: uuid.UUID,
        status: BlockchainRecordStatus = BlockchainRecordStatus.pending,
        tx_hash: Optional[str] = None,
    ) -> BlockchainRecord:
        record = BlockchainRecord(
            vote_id=vote_id,
            status=status,
            tx_hash=tx_hash,
        )
        session.add(record)
        await session.flush()
        return record
