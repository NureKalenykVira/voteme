import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import VotingEvent
from app.database.session import AsyncSessionLocal
from app.repositories.voting_repository import VotingRepository
from app.services.voting_fsm import (
    compute_expected_status,
    transitions_for_catch_up,
)
from app.services.voting_service import VotingService

logger = logging.getLogger(__name__)

_TICK_SECONDS = 30

_voting_service = VotingService()
_voting_repo = VotingRepository()


async def _run_tick(session: AsyncSession) -> int:
    now = datetime.now(timezone.utc)
    transitions_applied = 0

    due_start = await _voting_repo.find_due_for_start(session, now)
    for voting in due_start:
        before = voting.status
        voting = await _voting_service.apply_system_transition(
            session, voting, VotingEvent.start_tick
        )
        if voting.status != before:
            transitions_applied += 1

    due_end = await _voting_repo.find_due_for_end(session, now)
    for voting in due_end:
        before = voting.status
        voting = await _voting_service.apply_system_transition(
            session, voting, VotingEvent.end_tick
        )
        if voting.status != before:
            transitions_applied += 1

    if transitions_applied > 0:
        await session.commit()
    return transitions_applied


async def tick() -> None:
    try:
        async with AsyncSessionLocal() as session:
            applied = await _run_tick(session)
            if applied:
                logger.info("voting scheduler tick: %d transitions applied", applied)
    except Exception:
        logger.exception("voting scheduler tick failed")


async def _run_catch_up(session: AsyncSession) -> int:
    now = datetime.now(timezone.utc)
    transitions_applied = 0

    pending = await _voting_repo.find_pending_lifecycle(session)
    for voting in pending:
        expected = compute_expected_status(
            voting.status,
            voting.start_date_time,
            voting.end_date_time,
            now,
        )
        events = transitions_for_catch_up(voting.status, expected)
        if not events:
            continue

        original_status = voting.status
        for event in events:
            voting = await _voting_service.apply_system_transition(
                session, voting, event
            )
        if voting.status != original_status:
            transitions_applied += 1
            logger.info(
                "catch_up: voting %s %s -> %s (now=%s)",
                voting.id,
                original_status.value,
                voting.status.value,
                now.isoformat(),
            )

    if transitions_applied > 0:
        await session.commit()
    return transitions_applied


async def catch_up_on_boot() -> None:
    try:
        async with AsyncSessionLocal() as session:
            applied = await _run_catch_up(session)
            logger.info("catch_up_on_boot: %d overdue voting(s) reconciled", applied)
    except Exception:
        logger.exception("catch_up_on_boot failed")


def schedule_tick() -> None:
    from app.scheduler import get_scheduler

    scheduler = get_scheduler()
    scheduler.add_job(
        tick,
        trigger="interval",
        seconds=_TICK_SECONDS,
        id="voting_lifecycle_tick",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
