from datetime import datetime
from typing import Optional

from app.core.enums import VotingEvent, VotingStatus


# Delta table: (current_status, event) -> next_status or None (bottom = invalid)
_TRANSITIONS: dict[tuple[VotingStatus, VotingEvent], VotingStatus] = {
    (VotingStatus.draft, VotingEvent.publish): VotingStatus.published,
    (VotingStatus.published, VotingEvent.start_tick): VotingStatus.active,
    (VotingStatus.active, VotingEvent.end_tick): VotingStatus.finished,
    (VotingStatus.finished, VotingEvent.archive): VotingStatus.archived,
}


# Audit action names mapped from FSM events
EVENT_AUDIT_ACTION: dict[VotingEvent, str] = {
    VotingEvent.publish: "ELECTION_PUBLISHED",
    VotingEvent.start_tick: "ELECTION_ACTIVATED",
    VotingEvent.end_tick: "ELECTION_FINISHED",
    VotingEvent.archive: "ELECTION_ARCHIVED",
}


def next_status(
    current: VotingStatus, event: VotingEvent
) -> Optional[VotingStatus]:
    """Return target status for (current, event), or None for invalid (bottom) transition."""
    return _TRANSITIONS.get((current, event))


def apply_transition(
    current_status: VotingStatus, event: VotingEvent
) -> VotingStatus:
    """
    Pure FSM step. Returns the next status.
    Raises ValueError if the transition is invalid (bottom).
    Callers translate ValueError into HTTPException(409).
    """
    target = _TRANSITIONS.get((current_status, event))
    if target is None:
        raise ValueError(
            f"Invalid transition: {current_status.value} --{event.value}--> bottom"
        )
    return target


def compute_expected_status(
    current_status: VotingStatus,
    start_date_time: datetime,
    end_date_time: datetime,
    now: datetime,
) -> VotingStatus:
    """
    Used by catch_up_on_boot() to determine where a voting should be
    given the current wall clock. Idempotent: passing an already-correct
    status returns the same status.
    """
    if current_status in (VotingStatus.draft, VotingStatus.archived):
        return current_status

    if current_status == VotingStatus.finished:
        return current_status

    if current_status == VotingStatus.published:
        if now >= end_date_time:
            return VotingStatus.finished
        if now >= start_date_time:
            return VotingStatus.active
        return VotingStatus.published

    if current_status == VotingStatus.active:
        if now >= end_date_time:
            return VotingStatus.finished
        return VotingStatus.active

    return current_status


def transitions_for_catch_up(
    current_status: VotingStatus, expected_status: VotingStatus
) -> list[VotingEvent]:
    """
    Return the ordered list of events needed to move from current to expected.
    Used by catch_up_on_boot for overdue votings.
    """
    if current_status == expected_status:
        return []

    if current_status == VotingStatus.published and expected_status == VotingStatus.active:
        return [VotingEvent.start_tick]

    if current_status == VotingStatus.published and expected_status == VotingStatus.finished:
        return [VotingEvent.start_tick, VotingEvent.end_tick]

    if current_status == VotingStatus.active and expected_status == VotingStatus.finished:
        return [VotingEvent.end_tick]

    return []
