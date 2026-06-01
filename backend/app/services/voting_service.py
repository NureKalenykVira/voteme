import asyncio
import csv
import io
import logging
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
    Role,
    VotingAccessType,
    VotingEvent,
    VotingStatus,
)
from app.models.ballot_option import BallotOption
from app.models.vote import Vote
from app.models.user import User
from app.models.voter_list import VoterList
from app.models.voting import Voting
from app.repositories.audit_repository import AuditRepository
from app.repositories.ballot_option_repository import BallotOptionRepository
from app.repositories.user_repository import UserRepository
from app.repositories.election_auditor_repository import (
    ElectionAuditorRepository,
)
from app.repositories.voter_list_repository import VoterListRepository
from app.repositories.voting_repository import VotingRepository
from app.repositories.vote_result_repository import VoteResultRepository
from app.schemas.voting import (
    BallotOptionCreateRequest,
    BallotOptionUpdateRequest,
    CsvImportInvalidRow,
    CsvImportResponse,
    ElectionResultsResponse,
    OptionResultResponse,
    TimelineBucket,
    TimelineResponse,
    VotingCreateRequest,
    VotingUpdateRequest,
)
from app.services.voting_fsm import (
    EVENT_AUDIT_ACTION,
    apply_transition,
)
from eth_utils import keccak

from app.blockchain.client import (
    election_id_to_uint256,
    finalize_election_on_chain,
    publish_election,
)
from app.database.session import AsyncSessionLocal
from app.repositories.vote_repository import VoteRepository
from app.utils.merkle import build_merkle_root
from app.services.email_service import EmailService
from app.core.config import settings


logger = logging.getLogger(__name__)

_MIN_OPTIONS_TO_PUBLISH = 2

_email_service = EmailService()


def _fire_and_forget_email(coro) -> None:
    async def _runner():
        try:
            await coro
        except Exception as exc:
            logger.error("Background voter email failed: %s", exc)

    try:
        asyncio.get_running_loop().create_task(_runner())
    except RuntimeError:
        logger.warning("No running event loop; voter email skipped")
        coro.close()



class VotingService:
    def __init__(self) -> None:
        self._votings = VotingRepository()
        self._options = BallotOptionRepository()
        self._users = UserRepository()
        self._voter_lists = VoterListRepository()
        self._audit = AuditRepository()
        self._auditors = ElectionAuditorRepository()

    async def _get_voting_or_404(
        self, session: AsyncSession, voting_id: uuid.UUID
    ) -> Voting:
        voting = await self._votings.get_by_id(session, voting_id)
        if voting is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Election not found"
            )
        return voting

    async def get_results(
        self,
        session: AsyncSession,
        voting_id: uuid.UUID,
        actor: Optional[User] = None,
    ) -> ElectionResultsResponse:
        voting = await self._get_voting_or_404(session, voting_id)

        if voting.status not in (
            VotingStatus.finished,
            VotingStatus.archived,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Election results are not available yet",
            )

        options = await self._options.list_for_voting(session, voting_id)
        result_rows = await VoteResultRepository().get_for_voting(
            session, voting_id
        )
        counts = {row.option_id: row.votes_count for row in result_rows}
        total_votes = sum(counts.values())

        option_results = [
            OptionResultResponse(
                option_id=option.id,
                title=option.title,
                description=option.description,
                photo_url=option.photo_url,
                votes_count=counts.get(option.id, 0),
                percentage=(
                    round(counts.get(option.id, 0) / total_votes * 100, 2)
                    if total_votes > 0
                    else 0.0
                ),
            )
            for option in options
        ]
        option_results.sort(key=lambda x: x.votes_count, reverse=True)

        voters_invited_result = await session.execute(
            select(func.count(VoterList.id)).where(VoterList.voting_id == voting_id)
        )
        voters_invited = voters_invited_result.scalar() or 0

        already_voted_result = await session.execute(
            select(func.count(Vote.id)).where(Vote.voting_id == voting_id)
        )
        already_voted = already_voted_result.scalar() or 0

        participation_pct = (
            round(already_voted / voters_invited * 100, 2) if voters_invited > 0 else 0.0
        )

        is_organizer = actor is not None and actor.id == voting.created_by

        organizer = await self._users.get_by_id(session, voting.created_by)
        organizer_name: Optional[str] = None
        if organizer is not None:
            organizer_name = organizer.full_name or organizer.email

        return ElectionResultsResponse(
            voting_id=voting.id,
            title=voting.title,
            status=voting.status.value,
            total_votes=total_votes,
            voters_invited=voters_invited,
            already_voted=already_voted,
            participation_pct=participation_pct,
            options=option_results,
            finalize_tx_hash=voting.finalize_tx_hash,
            is_organizer=is_organizer,
            start_date_time=voting.start_date_time,
            end_date_time=voting.end_date_time,
            organizer_name=organizer_name,
        )

    async def get_timeline(
        self,
        session: AsyncSession,
        voting_id: uuid.UUID,
        actor: User,
    ) -> TimelineResponse:
        voting = await self._get_voting_or_404(session, voting_id)
        self._ensure_owner_or_admin(voting, actor)

        result = await session.execute(
            select(Vote.submitted_at).where(Vote.voting_id == voting_id)
        )
        timestamps = [row[0] for row in result.fetchall()]

        if timestamps:
            span_start = min(timestamps)
            span_end = max(timestamps)
        else:
            span_start = voting.start_date_time
            span_end = voting.end_date_time

        # Ensure span_start and span_end are timezone-aware
        if span_start.tzinfo is None:
            span_start = span_start.replace(tzinfo=timezone.utc)
        if span_end.tzinfo is None:
            span_end = span_end.replace(tzinfo=timezone.utc)

        total_seconds = (span_end - span_start).total_seconds()

        if total_seconds < 3600:
            bucket_delta = timedelta(minutes=10)
            label_format = "time"
        elif total_seconds < 43200:
            bucket_delta = timedelta(hours=1)
            label_format = "time"
        elif total_seconds < 172800:
            bucket_delta = timedelta(hours=2)
            label_format = "time"
        elif total_seconds < 1209600:
            bucket_delta = timedelta(days=1)
            label_format = "date"
        else:
            bucket_delta = timedelta(weeks=1)
            label_format = "date"

        # Align span_start to the beginning of its bucket
        if label_format == "time":
            bucket_seconds = int(bucket_delta.total_seconds())
            epoch = span_start.replace(hour=0, minute=0, second=0, microsecond=0)
            elapsed = int((span_start - epoch).total_seconds())
            aligned_start = epoch + timedelta(seconds=(elapsed // bucket_seconds) * bucket_seconds)
        else:
            if bucket_delta.days == 1:
                aligned_start = span_start.replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                # Align to start of ISO week (Monday)
                aligned_start = span_start.replace(hour=0, minute=0, second=0, microsecond=0)
                aligned_start = aligned_start - timedelta(days=aligned_start.weekday())

        # Build bucket boundaries
        buckets: list[TimelineBucket] = []
        cursor = aligned_start
        while cursor <= span_end:
            next_cursor = cursor + bucket_delta
            if label_format == "time":
                label = cursor.strftime("%H:%M")
            else:
                # "Dec 5" style — use %-d on POSIX; use a portable approach
                day = cursor.day
                month_abbr = cursor.strftime("%b")
                label = f"{month_abbr} {day}"

            count = sum(
                1 for ts in timestamps
                if cursor <= (ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)) < next_cursor
            )
            buckets.append(TimelineBucket(label=label, votes=count))
            cursor = next_cursor

        # Edge case: 0, 1, or all-identical votes — ensure at least 3 buckets for a meaningful chart
        unique_timestamps = set(timestamps)
        if len(unique_timestamps) <= 1 and len(buckets) < 3:
            while len(buckets) < 3:
                extra_label: str
                if label_format == "time":
                    extra_label = cursor.strftime("%H:%M")
                else:
                    day = cursor.day
                    month_abbr = cursor.strftime("%b")
                    extra_label = f"{month_abbr} {day}"
                buckets.append(TimelineBucket(label=extra_label, votes=0))
                cursor = cursor + bucket_delta

        # date_range: "D MMM – D MMM, YYYY"
        def _fmt_date(dt: datetime) -> str:
            return f"{dt.day} {dt.strftime('%b')}"

        if span_start.year == span_end.year:
            date_range = f"{_fmt_date(span_start)} – {_fmt_date(span_end)}, {span_start.year}"
        else:
            date_range = (
                f"{_fmt_date(span_start)}, {span_start.year} – "
                f"{_fmt_date(span_end)}, {span_end.year}"
            )

        return TimelineResponse(buckets=buckets, date_range=date_range)

    def _ensure_owner_or_admin(self, voting: Voting, user: User) -> None:
        if user.role == Role.global_admin:
            return
        if voting.created_by != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not own this election",
            )

    def _ensure_draft(self, voting: Voting) -> None:
        if voting.status != VotingStatus.draft:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Operation allowed only for draft elections",
            )

    def _ensure_editable(self, voting: Voting) -> None:
        if voting.status not in (VotingStatus.draft, VotingStatus.published):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Operation allowed only for draft or published elections",
            )

    async def create_voting(
        self,
        session: AsyncSession,
        actor: User,
        data: VotingCreateRequest,
    ) -> Voting:
        if data.end_date_time <= data.start_date_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="end_date_time must be after start_date_time",
            )

        voting = await self._votings.create(
            session,
            title=data.title,
            description=data.description,
            access_type=data.access_type,
            is_anonymous=data.is_anonymous,
            start_date_time=data.start_date_time,
            end_date_time=data.end_date_time,
            created_by=actor.id,
            invitation_code=secrets.token_urlsafe(16),
        )
        await self._audit.create_entry(
            session,
            "ELECTION_CREATED",
            actor_id=actor.id,
            data={
                "voting_id": str(voting.id),
                "title": voting.title,
                "access_type": voting.access_type.value,
                "is_anonymous": voting.is_anonymous,
            },
        )
        await session.commit()
        await session.refresh(voting)
        return voting

    async def get_voting_detail(
        self,
        session: AsyncSession,
        actor: User,
        voting_id: uuid.UUID,
    ) -> tuple[Voting, list[BallotOption]]:
        voting = await self._get_voting_or_404(session, voting_id)

        if actor.role == Role.global_admin:
            pass
        elif voting.created_by == actor.id:
            pass
        else:
            if voting.status == VotingStatus.draft:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Election is not visible",
                )

        options = list(await self._options.list_for_voting(session, voting.id))
        return voting, options

    async def list_votings(
        self,
        session: AsyncSession,
        actor: User,
        status_filter: Optional[VotingStatus],
        page: int,
        page_size: int,
    ) -> tuple[list[Voting], int]:
        if actor.role == Role.global_admin:
            items, total = await self._votings.list_all(
                session, status_filter, page, page_size
            )
        elif actor.role == Role.voter:
            items, total = await self._votings.list_for_voter_union(
                session, actor.id, status_filter, page, page_size
            )
        elif actor.role == Role.auditor:
            items, total = await self._votings.list_for_voter_union(
                session, actor.id, status_filter, page, page_size
            )
        else:
            items, total = await self._votings.list_for_organizer(
                session, actor.id, status_filter, page, page_size
            )
        return list(items), total

    async def update_voting(
        self,
        session: AsyncSession,
        actor: User,
        voting_id: uuid.UUID,
        data: VotingUpdateRequest,
    ) -> Voting:
        voting = await self._get_voting_or_404(session, voting_id)
        self._ensure_owner_or_admin(voting, actor)
        self._ensure_editable(voting)

        updates: dict[str, object] = {}
        if data.title is not None and data.title != voting.title:
            updates["title"] = data.title
        if data.description is not None and data.description != voting.description:
            updates["description"] = data.description
        if data.access_type is not None and data.access_type != voting.access_type:
            updates["access_type"] = data.access_type

        new_start = data.start_date_time if data.start_date_time is not None else voting.start_date_time
        new_end = data.end_date_time if data.end_date_time is not None else voting.end_date_time
        if new_end <= new_start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="end_date_time must be after start_date_time",
            )
        if data.start_date_time is not None and data.start_date_time != voting.start_date_time:
            updates["start_date_time"] = data.start_date_time
        if data.end_date_time is not None and data.end_date_time != voting.end_date_time:
            updates["end_date_time"] = data.end_date_time

        if updates:
            voting = await self._votings.update(session, voting, **updates)
            await self._audit.create_entry(
                session,
                "ELECTION_UPDATED",
                actor_id=actor.id,
                data={
                    "voting_id": str(voting.id),
                    "updated_fields": sorted(updates.keys()),
                },
            )
        await session.commit()
        await session.refresh(voting)
        return voting

    async def delete_voting(
        self,
        session: AsyncSession,
        actor: User,
        voting_id: uuid.UUID,
    ) -> None:
        voting = await self._get_voting_or_404(session, voting_id)
        self._ensure_owner_or_admin(voting, actor)
        self._ensure_draft(voting)

        await self._audit.create_entry(
            session,
            "ELECTION_DELETED",
            actor_id=actor.id,
            data={"voting_id": str(voting.id), "title": voting.title},
        )
        await self._votings.update(
            session,
            voting,
            is_deleted=True,
            deleted_at=datetime.now(timezone.utc),
        )
        await session.commit()

    async def publish_voting(
        self,
        session: AsyncSession,
        actor: User,
        voting_id: uuid.UUID,
    ) -> Voting:
        voting = await self._get_voting_or_404(session, voting_id)
        self._ensure_owner_or_admin(voting, actor)

        if voting.status != VotingStatus.draft:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only draft elections can be published",
            )

        option_count = await self._options.count_for_voting(session, voting.id)
        if option_count < _MIN_OPTIONS_TO_PUBLISH:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"At least {_MIN_OPTIONS_TO_PUBLISH} ballot options are required",
            )

        now = datetime.now(timezone.utc)
        if voting.start_date_time <= now:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="start_date_time must be in the future",
            )

        try:
            target = apply_transition(voting.status, VotingEvent.publish)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            )

        updates: dict[str, object] = {"status": target}

        voting = await self._votings.update(session, voting, **updates)

        await self._audit.create_entry(
            session,
            EVENT_AUDIT_ACTION[VotingEvent.publish],
            actor_id=actor.id,
            data={
                "voting_id": str(voting.id),
                "access_type": voting.access_type.value,
                "is_anonymous": voting.is_anonymous,
            },
        )
        await session.commit()
        await session.refresh(voting)

        _fire_election_published(voting.id, voting.title)

        return voting

    async def archive_voting(
        self,
        session: AsyncSession,
        actor: User,
        voting_id: uuid.UUID,
    ) -> Voting:
        voting = await self._get_voting_or_404(session, voting_id)
        self._ensure_owner_or_admin(voting, actor)

        try:
            target = apply_transition(voting.status, VotingEvent.archive)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            )

        voting = await self._votings.update(session, voting, status=target)
        await self._audit.create_entry(
            session,
            EVENT_AUDIT_ACTION[VotingEvent.archive],
            actor_id=actor.id,
            data={"voting_id": str(voting.id)},
        )
        await session.commit()
        await session.refresh(voting)
        return voting

    async def _get_option_in_voting(
        self,
        session: AsyncSession,
        voting: Voting,
        option_id: uuid.UUID,
    ) -> BallotOption:
        option = await self._options.get_by_id(session, option_id)
        if option is None or option.voting_id != voting.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ballot option not found",
            )
        return option

    async def create_option(
        self,
        session: AsyncSession,
        actor: User,
        voting_id: uuid.UUID,
        data: BallotOptionCreateRequest,
    ) -> BallotOption:
        voting = await self._get_voting_or_404(session, voting_id)
        self._ensure_owner_or_admin(voting, actor)
        self._ensure_editable(voting)

        order_index = await self._options.next_order_index(session, voting.id)
        option = await self._options.create(
            session,
            voting_id=voting.id,
            title=data.title,
            description=data.description,
            order_index=order_index,
        )
        await self._audit.create_entry(
            session,
            "ELECTION_OPTION_CREATED",
            actor_id=actor.id,
            data={
                "voting_id": str(voting.id),
                "option_id": str(option.id),
                "title": option.title,
            },
        )
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ballot option with this order already exists",
            )
        await session.refresh(option)
        return option

    async def update_option(
        self,
        session: AsyncSession,
        actor: User,
        voting_id: uuid.UUID,
        option_id: uuid.UUID,
        data: BallotOptionUpdateRequest,
    ) -> BallotOption:
        voting = await self._get_voting_or_404(session, voting_id)
        self._ensure_owner_or_admin(voting, actor)
        self._ensure_editable(voting)
        option = await self._get_option_in_voting(session, voting, option_id)

        updates: dict[str, object] = {}
        if data.title is not None and data.title != option.title:
            updates["title"] = data.title
        if data.description is not None and data.description != option.description:
            updates["description"] = data.description
        if data.order_index is not None and data.order_index != option.order_index:
            updates["order_index"] = data.order_index

        if updates:
            option = await self._options.update(session, option, **updates)
            await self._audit.create_entry(
                session,
                "ELECTION_OPTION_UPDATED",
                actor_id=actor.id,
                data={
                    "voting_id": str(voting.id),
                    "option_id": str(option.id),
                    "updated_fields": sorted(updates.keys()),
                },
            )
        await session.commit()
        await session.refresh(option)
        return option

    async def delete_option(
        self,
        session: AsyncSession,
        actor: User,
        voting_id: uuid.UUID,
        option_id: uuid.UUID,
    ) -> None:
        voting = await self._get_voting_or_404(session, voting_id)
        self._ensure_owner_or_admin(voting, actor)
        self._ensure_editable(voting)
        option = await self._get_option_in_voting(session, voting, option_id)

        await self._audit.create_entry(
            session,
            "ELECTION_OPTION_DELETED",
            actor_id=actor.id,
            data={
                "voting_id": str(voting.id),
                "option_id": str(option.id),
                "title": option.title,
            },
        )
        await self._options.delete(session, option)
        await session.commit()

    async def set_option_photo(
        self,
        session: AsyncSession,
        actor: User,
        voting_id: uuid.UUID,
        option_id: uuid.UUID,
        photo_url: str,
    ) -> BallotOption:
        voting = await self._get_voting_or_404(session, voting_id)
        self._ensure_owner_or_admin(voting, actor)
        self._ensure_editable(voting)
        option = await self._get_option_in_voting(session, voting, option_id)

        option = await self._options.update(session, option, photo_url=photo_url)
        await self._audit.create_entry(
            session,
            "ELECTION_OPTION_PHOTO_UPLOADED",
            actor_id=actor.id,
            data={
                "voting_id": str(voting.id),
                "option_id": str(option.id),
                "photo_url": photo_url,
            },
        )
        await session.commit()
        await session.refresh(option)
        return option

    async def get_join_view(
        self,
        session: AsyncSession,
        code: str,
        actor: Optional[User] = None,
    ) -> tuple[Voting, int, Optional[str], list[BallotOption], bool, bool, int, float, bool]:
        voting = await self._votings.get_by_invitation_code(session, code)
        if voting is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Election not found",
            )

        is_organizer = actor is not None and voting.created_by == actor.id

        is_election_auditor_for = False
        if actor is not None and not is_organizer:
            is_election_auditor_for = await self._auditors.is_auditor_for(
                session, voting.id, actor.id
            )

        if actor is not None and not is_organizer and not is_election_auditor_for:
            await self._voter_lists.ensure_member(
                session, voting.id, actor.email, actor.id
            )
            await session.commit()

        already_voted = await self._votings.count_participants(session, voting.id)

        organizer = await self._users.get_by_id(session, voting.created_by)
        created_by_name: Optional[str] = None
        if organizer is not None:
            created_by_name = organizer.full_name or organizer.email

        options = list(await self._options.list_for_voting(session, voting.id))

        user_has_voted = (
            await self._votings.has_user_voted(session, voting.id, actor.id)
            if actor is not None
            else False
        )

        if actor is None or is_organizer:
            can_vote = False
        elif voting.access_type == VotingAccessType.public:
            can_vote = True
        elif is_election_auditor_for:
            can_vote = False
        else:
            can_vote = True

        voters_invited_count = await self._voter_lists.count_for_voting(session, voting.id)
        participation = (
            already_voted / voters_invited_count * 100.0
            if voters_invited_count > 0
            else 0.0
        )

        return (
            voting,
            already_voted,
            created_by_name,
            options,
            is_organizer,
            user_has_voted,
            voters_invited_count,
            participation,
            can_vote,
        )

    async def list_voters(
        self,
        session: AsyncSession,
        actor: User,
        voting_id: uuid.UUID,
        page: int,
        page_size: int,
    ) -> tuple[list[dict], int, int, int, float]:
        voting = await self._get_voting_or_404(session, voting_id)
        self._ensure_owner_or_admin(voting, actor)

        voter_records, total = await self._voter_lists.list_paginated(
            session, voting_id, page, page_size
        )
        voters_invited = await self._voter_lists.count_for_voting(session, voting_id)
        already_voted = await self._votings.count_participants(session, voting_id)
        participation_pct = (
            already_voted / voters_invited * 100.0 if voters_invited > 0 else 0.0
        )

        items: list[dict] = []
        for vl in voter_records:
            name: Optional[str] = None
            voted = False
            if vl.user_id:
                user = await self._users.get_by_id(session, vl.user_id)
                if user:
                    name = user.full_name or user.email
                    voted = await self._votings.has_user_voted(
                        session, voting_id, vl.user_id
                    )
            items.append(
                {
                    "id": vl.id,
                    "email": vl.email,
                    "name": name,
                    "status": "voted" if voted else "invited",
                }
            )
        return items, total, voters_invited, already_voted, participation_pct

    async def add_voter(
        self,
        session: AsyncSession,
        actor: User,
        voting_id: uuid.UUID,
        email: str,
    ) -> VoterList:
        voting = await self._get_voting_or_404(session, voting_id)
        self._ensure_owner_or_admin(voting, actor)
        self._ensure_editable(voting)

        normalized = email.lower().strip()

        existing = await self._voter_lists.get_by_email(session, voting_id, normalized)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is already on the voter list",
            )

        user = await self._users.get_by_email(session, normalized)
        user_id = user.id if user else None

        voter = await self._voter_lists.add(session, voting_id, normalized, user_id)
        await self._audit.create_entry(
            session,
            "VOTER_ADDED",
            actor_id=actor.id,
            data={"voting_id": str(voting_id), "email": normalized},
        )
        await session.commit()
        await session.refresh(voter)

        if voting.invitation_code:
            join_link = f"{settings.frontend_url}/join/{voting.invitation_code}"
            _fire_and_forget_email(
                _email_service.send_voter_invitation_email(
                    normalized, voting.title, join_link
                )
            )
        else:
            logger.warning(
                "Skipping voter invitation email; voting %s has no invitation_code",
                voting.id,
            )
        return voter

    async def remove_voter(
        self,
        session: AsyncSession,
        actor: User,
        voting_id: uuid.UUID,
        voter_id: uuid.UUID,
    ) -> None:
        voting = await self._get_voting_or_404(session, voting_id)
        self._ensure_owner_or_admin(voting, actor)
        self._ensure_editable(voting)

        voter = await self._voter_lists.get_by_id(session, voter_id)
        if voter is None or voter.voting_id != voting_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Voter not found"
            )

        if voter.user_id:
            voted = await self._votings.has_user_voted(
                session, voting_id, voter.user_id
            )
            if voted:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot remove a voter who has already voted",
                )

        removed_email = voter.email
        await self._voter_lists.delete(session, voter)
        await self._audit.create_entry(
            session,
            "VOTER_REMOVED",
            actor_id=actor.id,
            data={"voting_id": str(voting_id), "email": removed_email},
        )
        await session.commit()

        _fire_and_forget_email(
            _email_service.send_voter_removed_email(removed_email, voting.title)
        )

    async def list_auditors(
        self,
        session: AsyncSession,
        actor: User,
        voting_id: uuid.UUID,
    ) -> list[tuple[uuid.UUID, str]]:
        voting = await self._get_voting_or_404(session, voting_id)
        self._ensure_owner_or_admin(voting, actor)

        records = await self._auditors.list_for_voting(session, voting_id)
        items: list[tuple[uuid.UUID, str]] = []
        for record in records:
            user = await self._users.get_by_id(session, record.user_id)
            if user is not None:
                items.append((user.id, user.email))
        return items

    async def add_auditor(
        self,
        session: AsyncSession,
        actor: User,
        voting_id: uuid.UUID,
        email: str,
    ) -> tuple[uuid.UUID, str]:
        voting = await self._get_voting_or_404(session, voting_id)
        self._ensure_owner_or_admin(voting, actor)

        normalized = email.lower().strip()
        user = await self._users.get_by_email(session, normalized)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No user found with this email",
            )

        await self._auditors.add(session, voting_id, user.id)
        await self._audit.create_entry(
            session,
            "AUDITOR_ADDED",
            actor_id=actor.id,
            data={"voting_id": str(voting_id), "email": user.email},
        )
        await session.commit()

        event_log_url = f"{settings.frontend_url}/event-log"
        _fire_and_forget_email(
            _email_service.send_auditor_invitation_email(
                user.email, voting.title, event_log_url
            )
        )
        return user.id, user.email

    async def remove_auditor(
        self,
        session: AsyncSession,
        actor: User,
        voting_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        voting = await self._get_voting_or_404(session, voting_id)
        self._ensure_owner_or_admin(voting, actor)

        removed = await self._auditors.remove(session, voting_id, user_id)
        if not removed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Auditor not found for this election",
            )

        user = await self._users.get_by_id(session, user_id)
        await self._audit.create_entry(
            session,
            "AUDITOR_REMOVED",
            actor_id=actor.id,
            data={
                "voting_id": str(voting_id),
                "email": user.email if user is not None else None,
            },
        )
        await session.commit()

    async def import_voters_csv(
        self,
        session: AsyncSession,
        actor: User,
        voting_id: uuid.UUID,
        content: bytes,
    ) -> CsvImportResponse:
        voting = await self._get_voting_or_404(session, voting_id)
        self._ensure_owner_or_admin(voting, actor)
        self._ensure_editable(voting)

        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid file encoding — expected UTF-8",
            )

        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None or "email" not in [
            (f or "").strip().lower() for f in reader.fieldnames
        ]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail='CSV must have an "email" header column',
            )

        rows = list(reader)
        if len(rows) > 1000:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="CSV exceeds the 1000-row limit",
            )

        added_count = 0
        duplicate_count = 0
        invalid_rows: list[CsvImportInvalidRow] = []
        seen: set[str] = set()
        added_emails: list[str] = []

        email_col = next(
            f for f in (reader.fieldnames or []) if (f or "").strip().lower() == "email"
        )

        for i, row in enumerate(rows, start=2):
            raw = (row.get(email_col) or "").strip().lower()

            if not raw:
                invalid_rows.append(CsvImportInvalidRow(row=i, email="", reason="Missing email"))
                continue

            if not _EMAIL_RE.match(raw):
                invalid_rows.append(CsvImportInvalidRow(row=i, email=raw, reason="Invalid email format"))
                continue

            if raw in seen:
                duplicate_count += 1
                continue
            seen.add(raw)

            existing = await self._voter_lists.get_by_email(session, voting_id, raw)
            if existing is not None:
                duplicate_count += 1
                continue

            user = await self._users.get_by_email(session, raw)
            await self._voter_lists.add(session, voting_id, raw, user.id if user else None)
            added_count += 1
            added_emails.append(raw)

        if added_count:
            await self._audit.create_entry(
                session,
                "VOTER_BULK_IMPORTED",
                actor_id=actor.id,
                data={"voting_id": str(voting_id), "added": added_count},
            )

        await session.commit()

        if added_emails:
            if voting.invitation_code:
                join_link = f"{settings.frontend_url}/join/{voting.invitation_code}"
                for em in added_emails:
                    _fire_and_forget_email(
                        _email_service.send_voter_invitation_email(
                            em, voting.title, join_link
                        )
                    )
            else:
                logger.warning(
                    "Skipping bulk voter invitation emails; voting %s has no invitation_code",
                    voting.id,
                )

        return CsvImportResponse(
            total_rows=len(rows),
            added_count=added_count,
            duplicate_count=duplicate_count,
            invalid_count=len(invalid_rows),
            invalid_rows=invalid_rows,
        )

    async def apply_system_transition(
        self,
        session: AsyncSession,
        voting: Voting,
        event: VotingEvent,
    ) -> Voting:
        try:
            target = apply_transition(voting.status, event)
        except ValueError:
            return voting

        voting = await self._votings.update(session, voting, status=target)
        await self._audit.create_entry(
            session,
            EVENT_AUDIT_ACTION[event],
            actor_id=None,
            data={
                "voting_id": str(voting.id),
                "trigger": "scheduler",
                "event": event.value,
            },
        )

        if event == VotingEvent.start_tick and voting.status == VotingStatus.active:
            _fire_election_started_emails(voting.id)

        if event == VotingEvent.end_tick and voting.status == VotingStatus.finished:
            _fire_election_finalized(voting.id)
            _tally_votes(voting.id)

        return voting


def _fire_election_published(voting_id: uuid.UUID, title: str) -> None:
    """
    Fire-and-forget background task that submits ElectionPublished on-chain
    and stores the resulting tx hash in votings.publish_tx_hash.

    Never raises into the caller.
    """

    async def _runner() -> None:
        try:
            params_hash = keccak(primitive=voting_id.bytes + title.encode("utf-8"))
            election_id_int = election_id_to_uint256(voting_id)
            tx_hash = await publish_election(election_id_int, params_hash)
            if tx_hash is None:
                return
            async with AsyncSessionLocal() as bg_session:
                voting_row = await bg_session.get(Voting, voting_id)
                if voting_row is None:
                    logger.warning(
                        "election-published hook: voting %s not found when persisting tx_hash",
                        voting_id,
                    )
                    return
                voting_row.publish_tx_hash = tx_hash
                await AuditRepository().create_entry(
                    bg_session,
                    "BLOCKCHAIN_RECORD",
                    actor_id=None,
                    data={"voting_id": str(voting_id), "tx_hash": tx_hash},
                )
                await bg_session.commit()
        except Exception as exc:
            logger.error(
                "election-published background task failed for voting_id=%s: %s",
                voting_id,
                exc,
                exc_info=True,
            )

    try:
        asyncio.get_running_loop().create_task(_runner())
    except RuntimeError:
        logger.warning(
            "No running event loop; skipping election-published blockchain hook for voting %s",
            voting_id,
        )


def _fire_election_finalized(voting_id: uuid.UUID) -> None:
    """
    Fire-and-forget background task that computes the merkle root of all votes
    for this election, submits ElectionFinalized on-chain, and stores the
    resulting tx hash in votings.finalize_tx_hash.

    Reads votes via a fresh session to avoid coupling to the scheduler session
    lifecycle. Never raises into the caller.
    """

    async def _runner() -> None:
        vote_repo = VoteRepository()
        try:
            async with AsyncSessionLocal() as read_session:
                votes = await vote_repo.list_for_voting_ordered(read_session, voting_id)

            leaves: list[bytes] = []
            for v in votes:
                hex_value = v.commitment_hash
                if hex_value.startswith("0x"):
                    hex_value = hex_value[2:]
                try:
                    raw = bytes.fromhex(hex_value)
                except ValueError:
                    logger.error(
                        "finalize hook: invalid commitment_hash for vote %s; skipping",
                        v.id,
                    )
                    continue
                leaves.append(keccak(primitive=raw))

            merkle_root = build_merkle_root(leaves)
            results_hash = keccak(primitive=merkle_root)
            election_id_int = election_id_to_uint256(voting_id)
            tx_hash = await finalize_election_on_chain(
                election_id_int, merkle_root, results_hash
            )
            if tx_hash is None:
                return
            async with AsyncSessionLocal() as bg_session:
                voting_row = await bg_session.get(Voting, voting_id)
                if voting_row is None:
                    logger.warning(
                        "election-finalized hook: voting %s not found when persisting tx_hash",
                        voting_id,
                    )
                    return
                voting_row.finalize_tx_hash = tx_hash
                await AuditRepository().create_entry(
                    bg_session,
                    "BLOCKCHAIN_RECORD",
                    actor_id=None,
                    data={"voting_id": str(voting_id), "tx_hash": tx_hash},
                )
                await AuditRepository().create_entry(
                    bg_session,
                    "ELECTION_FINALIZED",
                    actor_id=None,
                    data={"voting_id": str(voting_id)},
                )
                await bg_session.commit()
        except Exception as exc:
            logger.error(
                "election-finalized background task failed for voting_id=%s: %s",
                voting_id,
                exc,
                exc_info=True,
            )

    try:
        asyncio.get_running_loop().create_task(_runner())
    except RuntimeError:
        logger.warning(
            "No running event loop; skipping election-finalized blockchain hook for voting %s",
            voting_id,
        )


def _fire_election_started_emails(voting_id: uuid.UUID) -> None:
    async def _runner() -> None:
        try:
            async with AsyncSessionLocal() as session:
                voting = await session.get(Voting, voting_id)
                if voting is None:
                    return
                join_link = f"{settings.frontend_url}/join/{voting.invitation_code}"
                # Get all voters on the whitelist
                result = await session.execute(
                    select(User.email)
                    .join(VoterList, VoterList.user_id == User.id)
                    .where(VoterList.voting_id == voting_id)
                )
                for (voter_email,) in result.all():
                    _fire_and_forget_email(
                        _email_service.send_election_started_email(
                            voter_email, voting.title, join_link
                        )
                    )
        except Exception as exc:
            logger.error(
                "election-started email task failed for voting_id=%s: %s",
                voting_id, exc, exc_info=True,
            )

    try:
        asyncio.get_running_loop().create_task(_runner())
    except RuntimeError:
        logger.warning(
            "No running event loop; skipping election-started emails for voting %s",
            voting_id,
        )


def _tally_votes(voting_id: uuid.UUID) -> None:
    """
    Fire-and-forget background task that counts votes per ballot option and
    upserts them into vote_results. VoteResult is a derived cache recomputable
    from the votes table, so the upsert is idempotent on re-tally.

    Reads via a fresh session to avoid coupling to the scheduler session
    lifecycle. Never raises into the caller.
    """

    async def _runner() -> None:
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Vote.option_id, func.count())
                    .where(Vote.voting_id == voting_id)
                    .group_by(Vote.option_id)
                )
                counts = {row[0]: int(row[1]) for row in result.all()}
                await VoteResultRepository().upsert_results(
                    session, voting_id, counts
                )
                await AuditRepository().create_entry(
                    session,
                    "RESULTS_TALLIED",
                    actor_id=None,
                    data={"voting_id": str(voting_id), "options_count": len(counts)},
                )
                await session.commit()

                # --- results email notification (fire-and-forget) ---
                try:
                    voting_row = await session.get(Voting, voting_id)
                    if voting_row is not None:
                        results_url = f"{settings.frontend_url}/elections/{voting_id}/results"
                        organizer = await UserRepository().get_by_id(session, voting_row.created_by)
                        if organizer is not None:
                            _fire_and_forget_email(
                                _email_service.send_results_email(
                                    organizer.email, voting_row.title, results_url
                                )
                            )
                        voter_emails_result = await session.execute(
                            select(User.email)
                            .join(Vote, Vote.user_id == User.id)
                            .where(Vote.voting_id == voting_id)
                        )
                        for (voter_email,) in voter_emails_result.all():
                            _fire_and_forget_email(
                                _email_service.send_results_email(
                                    voter_email, voting_row.title, results_url
                                )
                            )
                except Exception as email_exc:
                    logger.error(
                        "Failed to schedule results emails for voting_id=%s: %s",
                        voting_id,
                        email_exc,
                    )
                # --- end results email ---

                logger.info(
                    "vote tally complete for voting_id=%s: %d options counted",
                    voting_id,
                    len(counts),
                )
        except Exception as exc:
            logger.error(
                "vote tally background task failed for voting_id=%s: %s",
                voting_id,
                exc,
                exc_info=True,
            )

    try:
        asyncio.get_running_loop().create_task(_runner())
    except RuntimeError:
        logger.warning(
            "No running event loop; skipping vote tally for voting %s",
            voting_id,
        )
