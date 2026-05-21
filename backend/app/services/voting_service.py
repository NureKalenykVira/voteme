import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
    Role,
    VotingAccessType,
    VotingEvent,
    VotingStatus,
)
from app.models.ballot_option import BallotOption
from app.models.user import User
from app.models.voting import Voting
from app.repositories.audit_repository import AuditRepository
from app.repositories.ballot_option_repository import BallotOptionRepository
from app.repositories.voting_repository import VotingRepository
from app.schemas.voting import (
    BallotOptionCreateRequest,
    BallotOptionUpdateRequest,
    VotingCreateRequest,
    VotingUpdateRequest,
)
from app.services.voting_fsm import (
    EVENT_AUDIT_ACTION,
    apply_transition,
)


logger = logging.getLogger(__name__)

_MIN_OPTIONS_TO_PUBLISH = 2


class VotingService:
    def __init__(self) -> None:
        self._votings = VotingRepository()
        self._options = BallotOptionRepository()
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
        self._ensure_draft(voting)

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
        if voting.access_type == VotingAccessType.private and not voting.invitation_code:
            updates["invitation_code"] = secrets.token_urlsafe(16)

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
        self._ensure_draft(voting)

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
        await session.commit()
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
        self._ensure_draft(voting)
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
        self._ensure_draft(voting)
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
        self._ensure_draft(voting)
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
