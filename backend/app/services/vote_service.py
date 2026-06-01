import asyncio
import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from eth_utils import keccak
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.blockchain.client import commit_vote_on_chain, election_id_to_uint256
from app.utils.merkle import build_merkle_proof, compute_root_from_proof
from app.core.config import settings
from app.core.enums import BlockchainRecordStatus, VotingAccessType, VotingStatus
from app.database.session import AsyncSessionLocal
from app.models.user import User
from app.models.vote import Vote
from app.models.voter_list import VoterList
from app.models.voting import Voting
from app.models.voting_participation import VotingParticipation
from app.repositories.audit_repository import AuditRepository
from app.repositories.ballot_option_repository import BallotOptionRepository
from app.repositories.blockchain_record_repository import BlockchainRecordRepository
from app.repositories.vote_repository import VoteRepository
from app.repositories.voting_repository import VotingRepository


logger = logging.getLogger(__name__)


def _build_commitment(
    voting_id: uuid.UUID,
    user_id: uuid.UUID,
    option_id: uuid.UUID,
    app_salt: str,
) -> tuple[str, str]:
    nonce = secrets.token_bytes(32)
    user_hash = hashlib.sha256(
        f"{user_id}{app_salt}".encode("utf-8")
    ).digest()
    payload = (
        voting_id.bytes
        + user_hash
        + option_id.bytes
        + nonce
    )
    commitment = keccak(payload)
    return commitment.hex(), nonce.hex()


class VoteService:
    def __init__(self) -> None:
        self._votes = VoteRepository()
        self._votings = VotingRepository()
        self._options = BallotOptionRepository()
        self._audit = AuditRepository()
        self._blockchain = BlockchainRecordRepository()

    async def _get_active_voting_or_error(
        self, session: AsyncSession, voting_id: uuid.UUID
    ) -> Voting:
        voting = await self._votings.get_by_id(session, voting_id)
        if voting is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Election not found",
            )
        if voting.status != VotingStatus.active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Election is not currently active",
            )
        return voting

    async def _ensure_eligible(
        self, session: AsyncSession, voting: Voting, actor: User
    ) -> None:
        if voting.access_type == VotingAccessType.public:
            return
        result = await session.execute(
            select(VoterList).where(
                VoterList.voting_id == voting.id,
                (VoterList.user_id == actor.id)
                | (VoterList.email == actor.email.lower()),
            )
        )
        entry = result.scalar_one_or_none()
        if entry is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not eligible to vote in this election",
            )

    async def submit_vote(
        self,
        session: AsyncSession,
        actor: User,
        voting_id: uuid.UUID,
        option_id: uuid.UUID,
        ip_address: Optional[str] = None,
    ) -> tuple[Vote, str]:
        voting = await self._get_active_voting_or_error(session, voting_id)
        await self._ensure_eligible(session, voting, actor)

        option = await self._options.get_by_id(session, option_id)
        if option is None or option.voting_id != voting.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ballot option not found in this election",
            )

        if await self._votes.exists_for_user(session, voting.id, actor.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already voted in this election",
            )

        commitment_hex, nonce_hex = _build_commitment(
            voting.id, actor.id, option.id, settings.app_salt
        )

        try:
            vote = await self._votes.create(
                session,
                voting_id=voting.id,
                user_id=actor.id,
                option_id=option.id,
                commitment_hash=commitment_hex,
                nonce=nonce_hex,
                ip_address=ip_address,
            )

            participation = VotingParticipation(
                voting_id=voting.id,
                user_id=actor.id,
            )
            session.add(participation)
            await session.flush()

            audit_actor: Optional[uuid.UUID] = (
                None if voting.is_anonymous else actor.id
            )
            audit_data: dict = {
                "voting_id": str(voting.id),
                "submitted_at": datetime.now(timezone.utc).isoformat(),
            }
            await self._audit.create_entry(
                session,
                "VOTE_SUBMITTED",
                actor_id=audit_actor,
                data=audit_data,
            )

            await self._blockchain.create(
                session,
                vote_id=vote.id,
                status=BlockchainRecordStatus.pending,
                tx_hash=None,
            )

            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already voted in this election",
            )

        await session.refresh(vote)

        _fire_vote_committed(vote.id, voting.id, commitment_hex)

        return vote, BlockchainRecordStatus.pending.value

    async def get_my_vote(
        self,
        session: AsyncSession,
        actor: User,
        voting_id: uuid.UUID,
    ) -> dict:
        voting = await self._votings.get_by_id(session, voting_id)
        if voting is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Election not found",
            )

        if voting.status == VotingStatus.draft:
            return {"has_voted": False}

        vote = await self._votes.get_for_user(session, voting.id, actor.id)
        if vote is None:
            return {"has_voted": False}

        bc = await self._blockchain.get_by_vote_id(session, vote.id)
        tx_status = bc.status.value if bc else None

        tx_hash = bc.tx_hash if bc else None

        if voting.is_anonymous:
            return {
                "has_voted": True,
                "commitment_hash": vote.commitment_hash,
                "tx_status": tx_status,
                "tx_hash": tx_hash,
            }
        return {
            "has_voted": True,
            "option_id": vote.option_id,
            "submitted_at": vote.submitted_at,
            "commitment_hash": vote.commitment_hash,
            "tx_status": tx_status,
            "tx_hash": tx_hash,
        }


    async def get_merkle_proof(
        self,
        session: AsyncSession,
        actor: User,
        voting_id: uuid.UUID,
        vote_id: uuid.UUID,
    ) -> dict:
        voting = await self._votings.get_by_id(session, voting_id)
        if voting is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Election not found",
            )
        if voting.status not in (VotingStatus.finished, VotingStatus.archived):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Merkle proof not available until election is finalized",
            )

        votes = await self._votes.list_for_voting_ordered(session, voting_id)

        idx = next((i for i, v in enumerate(votes) if v.id == vote_id), None)
        if idx is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vote not found",
            )

        if actor.id != votes[idx].user_id and actor.id != voting.created_by:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )

        leaves = [keccak(primitive=bytes.fromhex(v.commitment_hash)) for v in votes]
        proof = build_merkle_proof(leaves, idx)
        computed_root = compute_root_from_proof(leaves[idx], proof, idx)

        return {
            "vote_id": vote_id,
            "leaf": "0x" + leaves[idx].hex(),
            "proof_path": ["0x" + s.hex() for s in proof],
            "leaf_index": idx,
            "total_leaves": len(leaves),
            "computed_root": "0x" + computed_root.hex(),
        }

    async def get_voter_receipt(
        self,
        session: AsyncSession,
        actor: User,
        voting_id: uuid.UUID,
    ) -> dict:
        voting = await self._votings.get_by_id(session, voting_id)
        if voting is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Election not found",
            )
        if voting.status not in (VotingStatus.finished, VotingStatus.archived):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Merkle proof not available until election is finalized",
            )

        vote = await self._votes.get_for_user(session, voting_id, actor.id)
        if vote is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="You have not voted in this election",
            )

        votes = await self._votes.list_for_voting_ordered(session, voting_id)
        idx = next((i for i, v in enumerate(votes) if v.id == vote.id), None)

        leaves = [keccak(primitive=bytes.fromhex(v.commitment_hash)) for v in votes]
        proof = build_merkle_proof(leaves, idx)
        computed_root = compute_root_from_proof(leaves[idx], proof, idx)

        return {
            "commitment": "0x" + vote.commitment_hash,
            "nonce": "0x" + vote.nonce,
            "voting_id": str(voting_id),
            "leaf_index": idx,
            "merkle_proof": ["0x" + s.hex() for s in proof],
            "expected_root": "0x" + computed_root.hex(),
            "etherscan_url": (
                f"https://sepolia.etherscan.io/tx/{voting.finalize_tx_hash}"
                if voting.finalize_tx_hash
                else None
            ),
        }


def _fire_vote_committed(
    vote_id: uuid.UUID, voting_id: uuid.UUID, commitment_hex: str
) -> None:
    """
    Fire-and-forget background task that submits the vote commitment on-chain
    and updates the blockchain_records row with the resulting tx hash.

    Runs strictly AFTER the DB commit. Never raises into the caller.
    """

    async def _runner() -> None:
        bc_repo = BlockchainRecordRepository()
        try:
            election_id_int = election_id_to_uint256(voting_id)
            tx_hash = await commit_vote_on_chain(election_id_int, commitment_hex)
            new_status = (
                BlockchainRecordStatus.confirmed
                if tx_hash is not None
                else BlockchainRecordStatus.failed
            )
            async with AsyncSessionLocal() as bg_session:
                await bc_repo.update_tx_hash(bg_session, vote_id, tx_hash, new_status)
                if tx_hash is not None:
                    await AuditRepository().create_entry(
                        bg_session,
                        "BLOCKCHAIN_RECORD",
                        actor_id=None,
                        data={"voting_id": str(voting_id), "tx_hash": tx_hash},
                    )
                await bg_session.commit()
        except Exception as exc:
            logger.error(
                "vote-committed background task failed for vote_id=%s: %s",
                vote_id,
                exc,
                exc_info=True,
            )
            try:
                async with AsyncSessionLocal() as bg_session:
                    await bc_repo.update_tx_hash(
                        bg_session,
                        vote_id,
                        None,
                        BlockchainRecordStatus.failed,
                    )
                    await bg_session.commit()
            except Exception as nested:
                logger.error(
                    "vote-committed failure-state update also failed for vote_id=%s: %s",
                    vote_id,
                    nested,
                )

    try:
        asyncio.get_running_loop().create_task(_runner())
    except RuntimeError:
        logger.warning(
            "No running event loop; skipping vote-committed blockchain hook for vote %s",
            vote_id,
        )
