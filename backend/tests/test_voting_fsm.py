from datetime import datetime, timedelta, timezone

import pytest

from app.core.enums import VotingEvent, VotingStatus
from app.services.voting_fsm import (
    EVENT_AUDIT_ACTION,
    apply_transition,
    compute_expected_status,
    next_status,
    transitions_for_catch_up,
)


_ALL_STATES = list(VotingStatus)
_ALL_EVENTS = list(VotingEvent)


_VALID = {
    (VotingStatus.draft, VotingEvent.publish): VotingStatus.published,
    (VotingStatus.published, VotingEvent.start_tick): VotingStatus.active,
    (VotingStatus.active, VotingEvent.end_tick): VotingStatus.finished,
    (VotingStatus.finished, VotingEvent.archive): VotingStatus.archived,
}


class TestDeltaTable:
    @pytest.mark.parametrize(
        "current,event,expected",
        [
            (s, e, _VALID.get((s, e))) for s in _ALL_STATES for e in _ALL_EVENTS
        ],
    )
    def test_full_matrix(self, current, event, expected):
        assert next_status(current, event) == expected

    def test_apply_transition_valid(self):
        assert (
            apply_transition(VotingStatus.draft, VotingEvent.publish)
            == VotingStatus.published
        )

    def test_apply_transition_invalid_raises(self):
        with pytest.raises(ValueError):
            apply_transition(VotingStatus.draft, VotingEvent.start_tick)

    def test_archived_is_terminal_for_all_events(self):
        for event in _ALL_EVENTS:
            assert next_status(VotingStatus.archived, event) is None

    def test_audit_action_map_covers_all_events(self):
        for event in _ALL_EVENTS:
            assert event in EVENT_AUDIT_ACTION
            assert EVENT_AUDIT_ACTION[event].startswith("ELECTION_")


class TestComputeExpectedStatus:
    def _times(self, start_offset_sec: int, end_offset_sec: int):
        now = datetime(2026, 5, 21, 12, 0, 0, tzinfo=timezone.utc)
        start = now + timedelta(seconds=start_offset_sec)
        end = now + timedelta(seconds=end_offset_sec)
        return now, start, end

    def test_draft_stays_draft_regardless_of_time(self):
        now, start, end = self._times(-3600, +3600)
        assert (
            compute_expected_status(VotingStatus.draft, start, end, now)
            == VotingStatus.draft
        )

    def test_archived_stays_archived(self):
        now, start, end = self._times(-3600, -1800)
        assert (
            compute_expected_status(VotingStatus.archived, start, end, now)
            == VotingStatus.archived
        )

    def test_finished_stays_finished(self):
        now, start, end = self._times(-3600, -1800)
        assert (
            compute_expected_status(VotingStatus.finished, start, end, now)
            == VotingStatus.finished
        )

    def test_published_before_start_stays_published(self):
        now, start, end = self._times(+3600, +7200)
        assert (
            compute_expected_status(VotingStatus.published, start, end, now)
            == VotingStatus.published
        )

    def test_published_after_start_becomes_active(self):
        now, start, end = self._times(-300, +3600)
        assert (
            compute_expected_status(VotingStatus.published, start, end, now)
            == VotingStatus.active
        )

    def test_published_after_end_jumps_to_finished(self):
        now, start, end = self._times(-3600, -1800)
        assert (
            compute_expected_status(VotingStatus.published, start, end, now)
            == VotingStatus.finished
        )

    def test_active_after_end_becomes_finished(self):
        now, start, end = self._times(-3600, -60)
        assert (
            compute_expected_status(VotingStatus.active, start, end, now)
            == VotingStatus.finished
        )

    def test_active_before_end_stays_active(self):
        now, start, end = self._times(-3600, +60)
        assert (
            compute_expected_status(VotingStatus.active, start, end, now)
            == VotingStatus.active
        )

    def test_idempotent_on_repeated_invocation(self):
        now, start, end = self._times(-3600, -60)
        first = compute_expected_status(VotingStatus.active, start, end, now)
        second = compute_expected_status(first, start, end, now)
        assert first == second == VotingStatus.finished


class TestCatchUpEvents:
    def test_no_events_when_aligned(self):
        assert (
            transitions_for_catch_up(VotingStatus.draft, VotingStatus.draft)
            == []
        )

    def test_published_to_active(self):
        assert transitions_for_catch_up(
            VotingStatus.published, VotingStatus.active
        ) == [VotingEvent.start_tick]

    def test_published_to_finished_emits_two_events(self):
        assert transitions_for_catch_up(
            VotingStatus.published, VotingStatus.finished
        ) == [VotingEvent.start_tick, VotingEvent.end_tick]

    def test_active_to_finished(self):
        assert transitions_for_catch_up(
            VotingStatus.active, VotingStatus.finished
        ) == [VotingEvent.end_tick]
