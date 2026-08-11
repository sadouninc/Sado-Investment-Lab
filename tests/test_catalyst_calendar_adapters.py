from __future__ import annotations

import unittest

from scripts.catalyst_calendar import CalendarValidationError
from scripts.catalyst_calendar_adapters import (
    build_company_event,
    build_review_candidate,
    event_has_certainly_passed,
    merge_same_event,
    project_company_event,
    project_event_passage,
)


class CatalystCalendarAdapterTests(unittest.TestCase):
    def earnings(self, **overrides):
        payload = {
            "security_code": "6622",
            "event_key": "fy2027-q2-results",
            "event_type": "EARNINGS",
            "title": "ダイヘン FY2027 Q2 決算",
            "date_precision": "DATETIME",
            "scheduled_at": "2026-11-06T15:00:00+09:00",
            "source_ref": "ir:6622:fy2027-q2-schedule",
            "authority": "PRIMARY",
            "status": "SCHEDULED",
            "expected_review": ["REFRESH_RESEARCH", "REVIEW_THESIS", "UPDATE_VALUATION"],
            "related_refs": ["research:6622", "hypothesis:6622:dc-power-growth"],
        }
        payload.update(overrides)
        return payload

    def test_company_event_is_deterministic(self):
        a = build_company_event(self.earnings())
        b = build_company_event(self.earnings())
        self.assertEqual(a.event_id, b.event_id)
        self.assertEqual(a.entity_type, "COMPANY")
        self.assertEqual(a.entity_id, "6622")

    def test_same_earnings_identity_unions_consumers_without_duplicate(self):
        research = build_company_event(self.earnings(related_refs=["research:6622"]))
        reaction = build_company_event(
            self.earnings(
                related_refs=["earnings-reaction:6622:fy2027-q2"],
                expected_review=["REVIEW_DECISION"],
            )
        )
        merged = merge_same_event([research, reaction])
        self.assertEqual(merged.event_id, research.event_id)
        self.assertEqual(
            merged.related_refs,
            ("earnings-reaction:6622:fy2027-q2", "research:6622"),
        )
        self.assertIn("REVIEW_DECISION", merged.expected_review)

    def test_conflicting_schedule_for_same_identity_fails_closed(self):
        first = build_company_event(self.earnings())
        second = build_company_event(self.earnings(scheduled_at="2026-11-07T15:00:00+09:00"))
        with self.assertRaises(CalendarValidationError):
            merge_same_event([first, second])

    def test_datetime_passage_marks_occurred_but_not_handled(self):
        event = build_company_event(self.earnings())
        projected = project_event_passage(event, as_of="2026-11-06T15:00:01+09:00")
        self.assertEqual(projected.status, "OCCURRED")
        self.assertNotEqual(projected.status, "HANDLED")

    def test_datetime_before_event_stays_scheduled(self):
        event = build_company_event(self.earnings())
        projected = project_event_passage(event, as_of="2026-11-06T14:59:59+09:00")
        self.assertEqual(projected.status, "SCHEDULED")

    def test_date_precision_is_conservative_on_same_date(self):
        event = build_company_event(
            self.earnings(
                date_precision="DATE",
                scheduled_at=None,
                scheduled_date="2026-11-06",
            )
        )
        self.assertFalse(event_has_certainly_passed(event, as_of="2026-11-06T23:59:59+09:00"))
        self.assertTrue(event_has_certainly_passed(event, as_of="2026-11-07T00:00:00+09:00"))

    def test_month_and_window_do_not_fabricate_exact_time(self):
        month = build_company_event(
            self.earnings(
                date_precision="MONTH",
                scheduled_at=None,
                scheduled_month="2026-11",
            )
        )
        self.assertFalse(event_has_certainly_passed(month, as_of="2026-11-30T23:59:59+09:00"))
        self.assertTrue(event_has_certainly_passed(month, as_of="2026-12-01T00:00:00+09:00"))

        window = build_company_event(
            self.earnings(
                date_precision="WINDOW",
                scheduled_at=None,
                window_start="2026-11-01",
                window_end="2026-11-10",
            )
        )
        self.assertFalse(event_has_certainly_passed(window, as_of="2026-11-10T23:59:59+09:00"))
        self.assertTrue(event_has_certainly_passed(window, as_of="2026-11-11T00:00:00+09:00"))

    def test_unknown_date_never_auto_occurs(self):
        event = build_company_event(
            self.earnings(date_precision="UNKNOWN", scheduled_at=None, status="SCHEDULED")
        )
        self.assertFalse(event_has_certainly_passed(event, as_of="2030-01-01T00:00:00+09:00"))
        self.assertEqual(
            project_event_passage(event, as_of="2030-01-01T00:00:00+09:00").status,
            "SCHEDULED",
        )

    def test_review_candidate_keeps_event_occurred(self):
        event, candidate = project_company_event(
            self.earnings(), as_of="2026-11-06T16:00:00+09:00"
        )
        self.assertEqual(event.status, "OCCURRED")
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.event_ref, event.event_id)
        self.assertEqual(candidate.event_status, "OCCURRED")
        self.assertIn("REFRESH_RESEARCH", candidate.expected_review)

    def test_review_candidate_requires_occurred(self):
        with self.assertRaises(CalendarValidationError):
            build_review_candidate(build_company_event(self.earnings()))

    def test_timezone_naive_as_of_fails_closed(self):
        event = build_company_event(self.earnings())
        with self.assertRaisesRegex(CalendarValidationError, "timezone"):
            project_event_passage(event, as_of="2026-11-06T16:00:00")

    def test_unknown_input_fields_fail_closed(self):
        payload = self.earnings()
        payload["owner_decision"] = "BUY"
        with self.assertRaises(CalendarValidationError):
            build_company_event(payload)


if __name__ == "__main__":
    unittest.main()
