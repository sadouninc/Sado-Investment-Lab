import unittest

from scripts.catalyst_calendar import (
    CalendarValidationError,
    EventRecord,
    deterministic_event_id,
    mark_handled,
    mark_occurred,
    reschedule_event,
)


class CatalystCalendarTests(unittest.TestCase):
    def _event(self, **overrides):
        payload = {
            "event_key": "FY2027Q2",
            "event_type": "EARNINGS",
            "entity_type": "COMPANY",
            "entity_id": "6622",
            "title": "FY2027 Q2 earnings",
            "date_precision": "DATETIME",
            "scheduled_at": "2026-11-05T15:00:00+09:00",
            "source_ref": "ir://6622/earnings-calendar",
            "authority": "PRIMARY",
            "status": "SCHEDULED",
            "expected_review": ["REFRESH_RESEARCH", "REVIEW_THESIS", "UPDATE_VALUATION"],
            "related_refs": ["research:6622", "hypothesis:6622:dc-power-growth"],
        }
        payload.update(overrides)
        return EventRecord.from_mapping(payload)

    def test_same_identity_ignores_schedule_changes(self):
        first = deterministic_event_id(
            entity_type="COMPANY", entity_id="6622", event_type="EARNINGS", event_key="FY2027Q2"
        )
        second = self._event(scheduled_at="2026-11-06T15:00:00+09:00").event_id
        self.assertEqual(first, second)

    def test_exact_datetime_requires_timezone(self):
        with self.assertRaises(CalendarValidationError):
            self._event(scheduled_at="2026-11-05T15:00:00")

    def test_date_precision_variants(self):
        date_event = self._event(
            date_precision="DATE", scheduled_at=None, scheduled_date="2026-11-05"
        )
        month_event = self._event(
            date_precision="MONTH", scheduled_at=None, scheduled_month="2026-11"
        )
        window_event = self._event(
            date_precision="WINDOW",
            scheduled_at=None,
            window_start="2026-11-01",
            window_end="2026-11-15",
        )
        unknown_event = self._event(date_precision="UNKNOWN", scheduled_at=None, status="UNKNOWN")
        self.assertEqual(date_event.scheduled_date, "2026-11-05")
        self.assertEqual(month_event.scheduled_month, "2026-11")
        self.assertEqual(window_event.window_end, "2026-11-15")
        self.assertIsNone(unknown_event.scheduled_at)

    def test_unknown_date_is_not_fabricated(self):
        with self.assertRaises(CalendarValidationError):
            self._event(
                date_precision="UNKNOWN",
                scheduled_at=None,
                scheduled_date="2026-11-30",
                status="UNKNOWN",
            )

    def test_window_end_cannot_precede_start(self):
        with self.assertRaises(CalendarValidationError):
            self._event(
                date_precision="WINDOW",
                scheduled_at=None,
                window_start="2026-11-15",
                window_end="2026-11-01",
            )

    def test_reschedule_keeps_previous_schedule_history(self):
        event = self._event()
        moved = reschedule_event(
            event,
            {"date_precision": "DATETIME", "scheduled_at": "2026-11-07T15:00:00+09:00"},
            changed_at="2026-10-20T09:00:00+09:00",
            reason="company postponed announcement",
        )
        self.assertEqual(event.event_id, moved.event_id)
        self.assertEqual(moved.status, "SCHEDULED")
        self.assertEqual(moved.scheduled_at, "2026-11-07T15:00:00+09:00")
        self.assertEqual(len(moved.schedule_history), 1)
        self.assertEqual(moved.schedule_history[0].scheduled_at, "2026-11-05T15:00:00+09:00")
        self.assertEqual(moved.schedule_history[0].status, "DELAYED")

    def test_occurred_does_not_equal_handled(self):
        event = mark_occurred(self._event())
        self.assertEqual(event.status, "OCCURRED")
        handled = mark_handled(event)
        self.assertEqual(handled.status, "HANDLED")

    def test_cannot_handle_before_occurrence(self):
        with self.assertRaises(CalendarValidationError):
            mark_handled(self._event())

    def test_duplicate_review_and_refs_are_deduplicated(self):
        event = self._event(
            expected_review=["REVIEW_THESIS", "REVIEW_THESIS", "REFRESH_RESEARCH"],
            related_refs=["research:6622", "research:6622"],
        )
        self.assertEqual(event.expected_review, ("REFRESH_RESEARCH", "REVIEW_THESIS"))
        self.assertEqual(event.related_refs, ("research:6622",))

    def test_supplied_wrong_event_id_fails_closed(self):
        with self.assertRaises(CalendarValidationError):
            self._event(event_id="event:not-the-right-id")


if __name__ == "__main__":
    unittest.main()
