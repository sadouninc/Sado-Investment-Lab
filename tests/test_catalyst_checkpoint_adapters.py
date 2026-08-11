from __future__ import annotations

import unittest

from scripts.catalyst_calendar import CalendarValidationError
from scripts.catalyst_checkpoint_adapters import (
    build_decision_review_event,
    build_hypothesis_checkpoint_event,
)


class CatalystCheckpointAdapterTests(unittest.TestCase):
    def test_string_hypothesis_checkpoint_stays_unknown(self):
        hypothesis = {
            "security_code": "6622",
            "source_research_ref": "company-research:6622:2026-08-09",
        }
        event = build_hypothesis_checkpoint_event(hypothesis, "次回決算で受注成長を確認")
        self.assertEqual(event.event_type, "HYPOTHESIS_CHECKPOINT")
        self.assertEqual(event.entity_type, "HYPOTHESIS")
        self.assertEqual(event.date_precision, "UNKNOWN")
        self.assertEqual(event.status, "DISCOVERED")
        self.assertEqual(event.expected_review, ("REVIEW_THESIS",))

    def test_explicit_hypothesis_date_is_preserved(self):
        hypothesis = {
            "security_code": "6622",
            "hypothesis_id": "hypothesis:6622:dc-power-growth",
        }
        event = build_hypothesis_checkpoint_event(
            hypothesis,
            {
                "checkpoint_key": "orders-q2",
                "title": "Q2受注確認",
                "date_precision": "DATE",
                "scheduled_date": "2026-11-06",
                "source_ref": "research:6622",
                "authority": "INTERNAL",
            },
        )
        self.assertEqual(event.date_precision, "DATE")
        self.assertEqual(event.scheduled_date, "2026-11-06")
        self.assertEqual(event.status, "SCHEDULED")

    def test_decision_review_requires_explicit_schedule_not_decided_at(self):
        decision = {
            "decision_id": "decision:6622:abc123",
            "security_code": "6622",
            "decided_at": "2026-08-11T10:00:00+09:00",
        }
        event = build_decision_review_event(
            decision,
            {
                "title": "次回決算後に判断を再確認",
                "date_precision": "UNKNOWN",
            },
        )
        self.assertEqual(event.date_precision, "UNKNOWN")
        self.assertEqual(event.status, "DISCOVERED")
        self.assertIsNone(event.scheduled_at)
        self.assertEqual(event.expected_review, ("REVIEW_DECISION",))

    def test_decision_review_date_is_deterministic(self):
        decision = {
            "decision_id": "decision:6622:abc123",
            "security_code": "6622",
        }
        checkpoint = {
            "event_key": "post-q2-review",
            "title": "Q2後Decision Review",
            "date_precision": "DATE",
            "scheduled_date": "2026-11-07",
        }
        a = build_decision_review_event(decision, checkpoint)
        b = build_decision_review_event(decision, checkpoint)
        self.assertEqual(a.event_id, b.event_id)
        self.assertEqual(a.related_refs, ("company:6622", "decision:6622:abc123"))

    def test_missing_security_fails_closed(self):
        with self.assertRaises(CalendarValidationError):
            build_hypothesis_checkpoint_event(
                {"hypothesis_id": "hypothesis:6622:x"},
                "次回決算",
            )

    def test_unknown_precision_fails_closed(self):
        with self.assertRaises(CalendarValidationError):
            build_decision_review_event(
                {"decision_id": "decision:6622:x", "security_code": "6622"},
                {
                    "title": "review",
                    "date_precision": "QUARTER",
                },
            )


if __name__ == "__main__":
    unittest.main()
