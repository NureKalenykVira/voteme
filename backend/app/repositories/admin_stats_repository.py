from datetime import datetime, timedelta, timezone

from sqlalchemy import cast, func, select
from sqlalchemy.types import Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import BlockchainRecordStatus, VotingStatus
from app.models.blockchain_record import BlockchainRecord
from app.models.user import User
from app.models.vote import Vote
from app.models.voter_list import VoterList
from app.models.voting import Voting


class AdminStatsRepository:
    async def get_stats(self, session: AsyncSession) -> dict:
        now = datetime.now(timezone.utc)

        # total users (not deleted)
        total_users: int = (
            await session.execute(
                select(func.count()).select_from(User).where(User.is_deleted == False)  # noqa: E712
            )
        ).scalar_one()

        # total votings (not deleted)
        total_votings: int = (
            await session.execute(
                select(func.count()).select_from(Voting).where(Voting.is_deleted == False)  # noqa: E712
            )
        ).scalar_one()

        # votes cast
        votes_cast: int = (
            await session.execute(
                select(func.count()).select_from(Vote)
            )
        ).scalar_one()

        # active votings
        active_votings: int = (
            await session.execute(
                select(func.count())
                .select_from(Voting)
                .where(
                    Voting.status == VotingStatus.active,
                    Voting.is_deleted == False,  # noqa: E712
                )
            )
        ).scalar_one()

        # new users this month
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        new_users_this_month: int = (
            await session.execute(
                select(func.count())
                .select_from(User)
                .where(
                    User.created_at >= start_of_month,
                    User.is_deleted == False,  # noqa: E712
                )
            )
        ).scalar_one()

        # avg participation pct — votes cast / max(eligible voters, votes cast) per voting,
        # averaged across all non-deleted votings.
        # Denominator uses VoterList count (pre-registered eligible voters) when available,
        # falling back to votes_cast for open/public elections with no pre-registration rows.
        # max(...) ensures we never divide by zero even when both are 0.
        voter_list_subq = (
            select(func.count(VoterList.id))
            .where(VoterList.voting_id == Voting.id)
            .scalar_subquery()
        )
        vote_subq = (
            select(func.count(Vote.id))
            .where(Vote.voting_id == Voting.id)
            .scalar_subquery()
        )
        denominator_subq = func.greatest(voter_list_subq, vote_subq)
        avg_result = await session.execute(
            select(
                func.avg(
                    vote_subq * 100.0 / func.nullif(denominator_subq, 0)
                )
            )
            .select_from(Voting)
            .where(Voting.is_deleted == False)  # noqa: E712
        )
        avg_participation_pct: float = float(avg_result.scalar_one() or 0.0)

        # votings per day (last 14 days)
        vpd_rows = (
            await session.execute(
                select(
                    cast(Voting.created_at, Date).label("date"),
                    func.count().label("count"),
                )
                .where(
                    Voting.is_deleted == False,  # noqa: E712
                    Voting.created_at >= now - timedelta(days=14),
                )
                .group_by(cast(Voting.created_at, Date))
                .order_by(cast(Voting.created_at, Date))
            )
        ).all()
        votings_per_day = [{"date": str(r.date), "count": r.count} for r in vpd_rows]

        # votes per day (last 14 days)
        vpd2_rows = (
            await session.execute(
                select(
                    cast(Vote.submitted_at, Date).label("date"),
                    func.count().label("count"),
                )
                .where(Vote.submitted_at >= now - timedelta(days=14))
                .group_by(cast(Vote.submitted_at, Date))
                .order_by(cast(Vote.submitted_at, Date))
            )
        ).all()
        votes_per_day = [{"date": str(r.date), "count": r.count} for r in vpd2_rows]

        # users by role
        ubr_rows = (
            await session.execute(
                select(
                    User.role.label("role"),
                    func.count().label("count"),
                )
                .where(User.is_deleted == False)  # noqa: E712
                .group_by(User.role)
            )
        ).all()
        users_by_role = [{"role": str(r.role.value), "count": r.count} for r in ubr_rows]

        # top 5 votings by vote count
        top_rows = (
            await session.execute(
                select(
                    Voting.title,
                    func.count(Vote.id).label("votes_count"),
                )
                .outerjoin(Vote, Vote.voting_id == Voting.id)
                .where(Voting.is_deleted == False)  # noqa: E712
                .group_by(Voting.id, Voting.title)
                .order_by(func.count(Vote.id).desc())
                .limit(5)
            )
        ).all()
        top_votings = [{"title": r.title, "votes_count": r.votes_count} for r in top_rows]

        # blockchain stats
        blockchain_total: int = (
            await session.execute(select(func.count()).select_from(BlockchainRecord))
        ).scalar_one()

        blockchain_confirmed: int = (
            await session.execute(
                select(func.count())
                .select_from(BlockchainRecord)
                .where(BlockchainRecord.status == BlockchainRecordStatus.confirmed)
            )
        ).scalar_one()

        blockchain_failed: int = (
            await session.execute(
                select(func.count())
                .select_from(BlockchainRecord)
                .where(BlockchainRecord.status == BlockchainRecordStatus.failed)
            )
        ).scalar_one()

        # election-level blockchain anchors
        # blockchain_published = elections that have been anchored on publish (publish_tx_hash set)
        # blockchain_finalized = elections that have been anchored on finalize (finalize_tx_hash set)
        blockchain_published: int = (
            await session.execute(
                select(func.count())
                .select_from(Voting)
                .where(
                    Voting.is_deleted == False,  # noqa: E712
                    Voting.publish_tx_hash.is_not(None),
                )
            )
        ).scalar_one()

        blockchain_finalized: int = (
            await session.execute(
                select(func.count())
                .select_from(Voting)
                .where(
                    Voting.is_deleted == False,  # noqa: E712
                    Voting.finalize_tx_hash.is_not(None),
                )
            )
        ).scalar_one()

        # email stats
        # No EmailNotification persistence layer exists — emails are fire-and-forget via SMTP.
        # emails_total / emails_sent are proxied from VoterList rows (one invitation per entry).
        # emails_failed is not trackable from DB; always 0.
        emails_total: int = (
            await session.execute(select(func.count()).select_from(VoterList))
        ).scalar_one()
        emails_sent: int = emails_total
        emails_failed: int = 0

        return {
            "total_users": total_users,
            "total_votings": total_votings,
            "votes_cast": votes_cast,
            "active_votings": active_votings,
            "new_users_this_month": new_users_this_month,
            "avg_participation_pct": avg_participation_pct,
            "votings_per_day": votings_per_day,
            "votes_per_day": votes_per_day,
            "users_by_role": users_by_role,
            "top_votings": top_votings,
            "blockchain_total": blockchain_total,
            "blockchain_confirmed": blockchain_confirmed,
            "blockchain_failed": blockchain_failed,
            "blockchain_published": blockchain_published,
            "blockchain_finalized": blockchain_finalized,
            "emails_total": emails_total,
            "emails_sent": emails_sent,
            "emails_failed": emails_failed,
        }
