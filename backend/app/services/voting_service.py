import asyncio
import csv
import io
import logging
import re
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
    Role,
    VotingEvent,
    VotingStatus,
)
from app.models.ballot_option import BallotOption
from app.models.user import User
from app.models.voter_list import VoterList
from app.models.voting import Voting
from app.repositories.audit_repository import AuditRepository
from app.repositories.ballot_option_repository import BallotOptionRepository
from app.repositories.user_repository import UserRepository
from app.repositories.voter_list_repository import VoterListRepository
from app.repositories.voting_repository import VotingRepository
from app.schemas.voting import (
    BallotOptionCreateRequest,
    BallotOptionUpdateRequest,
    CsvImportInvalidRow,
    CsvImportResponse,
    VotingCreateRequest,
    VotingUpdateRequest,
)
from app.services.voting_fsm import (
    EVENT_AUDIT_ACTION,
    apply_transition,
)
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

    async def _get_voting_or_404(
        self, session: AsyncSession, voting_id: uuid.UUID
    ) -> Voting:
        voting = await self._votings.get_by_id(session, voting_id)
        if voting is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Election not found"
            )
        return voting

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
    ) -> tuple[Voting, int, Optional[str], list[BallotOption], bool, bool, int, float]:
        voting = await self._votings.get_by_invitation_code(session, code)
        if voting is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Election not found",
            )
        already_voted = await self._votings.count_participants(session, voting.id)

        organizer = await self._users.get_by_id(session, voting.created_by)
        created_by_name: Optional[str] = None
        if organizer is not None:
            created_by_name = organizer.full_name or organizer.email

        options = list(await self._options.list_for_voting(session, voting.id))

        is_organizer = actor is not None and voting.created_by == actor.id
        user_has_voted = (
            await self._votings.has_user_voted(session, voting.id, actor.id)
            if actor is not None
            else False
        )

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
        return voting
