import asyncio
import sys
import os

# Allow running from the backend/ directory
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import String, cast, select
from app.database.session import AsyncSessionLocal
from app.models.audit_log import AuditLog
from app.models.voting import Voting
from app.models.vote import Vote
from app.models.blockchain_record import BlockchainRecord
from app.core.enums import BlockchainRecordStatus
from app.repositories.audit_repository import AuditRepository

_audit = AuditRepository()


async def _already_exists(session, tx_hash: str) -> bool:
    result = await session.execute(
        select(AuditLog.id).where(
            cast(AuditLog.data["tx_hash"], String) == f'"{tx_hash}"'
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def backfill() -> None:
    async with AsyncSessionLocal() as session:
        created = 0

        # 1. publish_tx_hash
        rows = await session.execute(
            select(Voting.id, Voting.publish_tx_hash).where(
                Voting.publish_tx_hash.isnot(None)
            )
        )
        for voting_id, tx_hash in rows:
            if not await _already_exists(session, tx_hash):
                await _audit.create_entry(
                    session,
                    "BLOCKCHAIN_RECORD",
                    actor_id=None,
                    data={"voting_id": str(voting_id), "tx_hash": tx_hash},
                )
                created += 1
                print(f"  [publish]   voting={voting_id}  tx={tx_hash[:18]}...")

        # 2. finalize_tx_hash
        rows = await session.execute(
            select(Voting.id, Voting.finalize_tx_hash).where(
                Voting.finalize_tx_hash.isnot(None)
            )
        )
        for voting_id, tx_hash in rows:
            if not await _already_exists(session, tx_hash):
                await _audit.create_entry(
                    session,
                    "BLOCKCHAIN_RECORD",
                    actor_id=None,
                    data={"voting_id": str(voting_id), "tx_hash": tx_hash},
                )
                created += 1
                print(f"  [finalize]  voting={voting_id}  tx={tx_hash[:18]}...")

        # 3. vote commitment tx hashes
        rows = await session.execute(
            select(Vote.voting_id, BlockchainRecord.tx_hash)
            .join(Vote, BlockchainRecord.vote_id == Vote.id)
            .where(
                BlockchainRecord.tx_hash.isnot(None),
                BlockchainRecord.status == BlockchainRecordStatus.confirmed,
            )
        )
        for voting_id, tx_hash in rows:
            if not await _already_exists(session, tx_hash):
                await _audit.create_entry(
                    session,
                    "BLOCKCHAIN_RECORD",
                    actor_id=None,
                    data={"voting_id": str(voting_id), "tx_hash": tx_hash},
                )
                created += 1
                print(f"  [vote]      voting={voting_id}  tx={tx_hash[:18]}...")

        await session.commit()
        print(f"\nDone. Created {created} BLOCKCHAIN_RECORD audit entries.")


if __name__ == "__main__":
    asyncio.run(backfill())
