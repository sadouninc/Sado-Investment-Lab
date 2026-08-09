from __future__ import annotations

import copy
import unittest

from scripts.expectation_earnings_reaction_adapter import (
    ExpectationReactionAdapterError,
    attach_expectation_to_earnings_reaction,
    build_earnings_reaction_expectation_context,
)


EVENT = {
    "event_id": "earnings:6622:FY2027Q1:2026-08-04",
    "security_code": "6622",
    "fiscal_period": "FY2027Q1",
    "announcement_at": "2026-08-04T15:30:00+09:00",
    "announcement_time_quality": "EXACT",
    "source_ref": "ir:6622:fy2027q1",
}

ACTUAL = {
    "security_code": "6622",
    "target_fiscal_period": "FY2027Q1",
    "metric": "EPS",
    "unit": "JPY",
    "value": 110,
    "source_ref": "ir:6622:actual",
    "share_basis": {"basis": "BASIC_PRE_SPLIT"},
}


def consensus(*, as_of: str, observed_at: str, value: float | None, status: str = "OK", unit: str = "JPY"):
    return {
        "security_code": "6622",
        "target_fiscal_period": "FY2027Q1",
        "as_of": as_of,
        "expectation_type": "CONSENSUS",
        "metric": "EPS",
        "value": value,
        "unit": unit,
        "source_ref": f"consensus:{as_of}:{observed_at}",
        "source_authority": "SECONDARY",
        "observed_at": observed_at,
        "coverage": {"analyst_count": 7, "dispersion": 8, "status": status},
        "provenance": {"share_basis": {"basis": "BASIC_PRE_SPLIT"}},
    }


HISTORY = [
    consensus(as_of="2026-07-01", observed_at="2026-07-01T09:00:00+09:00", value=90),
    consensus(as_of="2026-08-04", observed_at="2026-08-04T10:00:00+09:00", value=100),
    consensus(as_of="2026-08-04", observed_at="2026-08-04T18:00:00+09:00", value=120),
]


class ExpectationEarningsReactionAdapterTests(unittest.TestCase):
    def test_pre_event_revision_and_surprise_are_separate_axes(self):
        context = build_earnings_reaction_expectation_context(
            EVENT,
            HISTORY,
            ACTUAL,
            metric="EPS",
            unit="JPY",
            share_basis={"basis": "BASIC_PRE_SPLIT"},
        )
        axis = context["expectation_axis"]
        self.assertEqual(axis["freeze_status"], "FROZEN")
        self.assertEqual(axis["latest_pre_event_value"], 100)
        self.assertEqual(axis["pre_event_revision_direction"], "UP")
        self.assertEqual(axis["pre_event_observation_count"], 2)
        surprise = context["expectation_surprise"]
        self.assertEqual(surprise["expectation_value"], 100)
        self.assertEqual(surprise["actual_value"], 110)
        self.assertAlmostEqual(surprise["surprise_pct"], 0.10)
        self.assertTrue(context["boundary"]["expectation_context_only"])
        self.assertEqual(context["boundary"]["fundamental_quality"], "NOT_CALCULATED_HERE")

    def test_post_event_consensus_is_excluded_from_revision_and_surprise(self):
        context = build_earnings_reaction_expectation_context(
            EVENT,
            HISTORY,
            ACTUAL,
            metric="EPS",
            unit="JPY",
            share_basis={"basis": "BASIC_PRE_SPLIT"},
        )
        self.assertEqual(context["expectation_axis"]["latest_pre_event_value"], 100)
        self.assertEqual(context["expectation_surprise"]["expectation_value"], 100)
        self.assertIn("POST_EVENT_EXPECTATION_EXCLUDED", context["warning_codes"])

    def test_unknown_announcement_time_fails_closed(self):
        event = dict(EVENT)
        event["announcement_time_quality"] = "UNKNOWN"
        context = build_earnings_reaction_expectation_context(
            event,
            HISTORY,
            ACTUAL,
            metric="EPS",
            unit="JPY",
            share_basis={"basis": "BASIC_PRE_SPLIT"},
        )
        self.assertEqual(context["status"], "NEEDS_REVIEW")
        self.assertEqual(context["expectation_axis"]["pre_event_observation_count"], 0)
        self.assertIsNone(context["expectation_surprise"]["surprise_pct"])

    def test_stale_pre_event_expectation_keeps_warning(self):
        history = [consensus(as_of="2026-07-01", observed_at="2026-07-01T09:00:00+09:00", value=100, status="STALE")]
        context = build_earnings_reaction_expectation_context(
            EVENT,
            history,
            ACTUAL,
            metric="EPS",
            unit="JPY",
            share_basis={"basis": "BASIC_PRE_SPLIT"},
        )
        self.assertEqual(context["status"], "OK")
        self.assertIn("STALE_EXPECTATION", context["warning_codes"])

    def test_unit_mismatch_does_not_create_surprise(self):
        context = build_earnings_reaction_expectation_context(
            EVENT,
            HISTORY,
            ACTUAL,
            metric="EPS",
            unit="JPY_MN",
            share_basis={"basis": "BASIC_PRE_SPLIT"},
        )
        self.assertNotEqual(context["status"], "OK")
        self.assertIsNone(context["expectation_surprise"]["surprise_pct"])

    def test_attachment_is_non_mutating(self):
        context = build_earnings_reaction_expectation_context(
            EVENT,
            HISTORY,
            ACTUAL,
            metric="EPS",
            unit="JPY",
            share_basis={"basis": "BASIC_PRE_SPLIT"},
        )
        reaction = {
            "event_id": EVENT["event_id"],
            "security_code": "6622",
            "fundamental_quality": {"status": "STRONG"},
            "next_1d_return": None,
        }
        original = copy.deepcopy(reaction)
        enriched = attach_expectation_to_earnings_reaction(reaction, context)
        self.assertEqual(reaction, original)
        self.assertEqual(enriched["fundamental_quality"], {"status": "STRONG"})
        self.assertEqual(enriched["expectation_context"]["expectation_surprise"]["surprise_pct"], 0.1)

    def test_attachment_identity_mismatch_fails_closed(self):
        context = build_earnings_reaction_expectation_context(
            EVENT,
            HISTORY,
            ACTUAL,
            metric="EPS",
            unit="JPY",
            share_basis={"basis": "BASIC_PRE_SPLIT"},
        )
        with self.assertRaises(ExpectationReactionAdapterError):
            attach_expectation_to_earnings_reaction(
                {"event_id": EVENT["event_id"], "security_code": "7974"},
                context,
            )

    def test_deterministic_rerun(self):
        first = build_earnings_reaction_expectation_context(
            EVENT,
            HISTORY,
            ACTUAL,
            metric="EPS",
            unit="JPY",
            share_basis={"basis": "BASIC_PRE_SPLIT"},
        )
        second = build_earnings_reaction_expectation_context(
            EVENT,
            HISTORY,
            ACTUAL,
            metric="EPS",
            unit="JPY",
            share_basis={"basis": "BASIC_PRE_SPLIT"},
        )
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
