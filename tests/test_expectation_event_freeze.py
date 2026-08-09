from __future__ import annotations

import copy
import unittest

from scripts.expectation_event_freeze import calculate_surprise, freeze_pre_event_expectation
from scripts.expectation_revision import validate_snapshot


EVENT = {
    "event_id": "earnings:6622:FY2027Q1:2026-08-04",
    "security_code": "6622",
    "fiscal_period": "FY2027Q1",
    "announcement_at": "2026-08-04T15:30:00+09:00",
    "announcement_time_quality": "EXACT",
    "source_ref": "fixture://ir/6622/fy2027q1",
}


def snapshot(
    *,
    as_of: str = "2026-08-04",
    observed_at: str = "2026-08-04T10:00:00+09:00",
    value: float | None = 100.0,
    fiscal_period: str = "FY2027Q1",
    metric: str = "EPS",
    unit: str = "JPY",
    status: str = "OK",
    share_basis: str = "BASIC_PRE_SPLIT",
):
    return validate_snapshot(
        {
            "security_code": "6622",
            "target_fiscal_period": fiscal_period,
            "as_of": as_of,
            "expectation_type": "CONSENSUS",
            "metric": metric,
            "value": value,
            "unit": unit,
            "source_ref": f"fixture://consensus/{observed_at}/{value}",
            "source_authority": "SECONDARY",
            "observed_at": observed_at,
            "coverage": {"analyst_count": 8, "dispersion": None, "status": status},
            "provenance": {"share_basis": {"basis": share_basis}},
        }
    )


def actual(*, value=110.0, fiscal_period="FY2027Q1", metric="EPS", unit="JPY", share_basis="BASIC_PRE_SPLIT"):
    return {
        "security_code": "6622",
        "target_fiscal_period": fiscal_period,
        "metric": metric,
        "unit": unit,
        "value": value,
        "share_basis": {"basis": share_basis},
        "source_ref": "fixture://actual/6622/fy2027q1",
    }


class ExpectationEventFreezeTests(unittest.TestCase):
    def test_pre_event_eps_100_actual_110_is_plus_10_percent(self):
        frozen = freeze_pre_event_expectation(EVENT, [snapshot()], metric="EPS", unit="JPY", share_basis={"basis": "BASIC_PRE_SPLIT"})
        result = calculate_surprise(EVENT, frozen, actual())
        self.assertEqual(frozen["freeze_status"], "FROZEN")
        self.assertEqual(result["surprise_abs"], 10.0)
        self.assertEqual(result["surprise_pct"], 0.1)
        self.assertEqual(result["status"], "OK")

    def test_post_event_revision_is_excluded_and_frozen_ref_does_not_change(self):
        before = snapshot(observed_at="2026-08-04T10:00:00+09:00", value=100.0)
        after = snapshot(observed_at="2026-08-04T16:00:00+09:00", value=120.0)
        first = freeze_pre_event_expectation(EVENT, [before], metric="EPS", unit="JPY")
        second = freeze_pre_event_expectation(EVENT, [before, after], metric="EPS", unit="JPY")
        self.assertEqual(first["pre_event_expectation_ref"], second["pre_event_expectation_ref"])
        self.assertIn("POST_EVENT_EXPECTATION_EXCLUDED", second["reason_codes"])
        self.assertEqual(calculate_surprise(EVENT, second, actual())["surprise_pct"], 0.1)

    def test_unknown_or_date_only_announcement_time_fails_closed(self):
        for quality in ("UNKNOWN", "DATE_ONLY"):
            event = dict(EVENT, announcement_time_quality=quality)
            frozen = freeze_pre_event_expectation(event, [snapshot()], metric="EPS", unit="JPY")
            self.assertEqual(frozen["freeze_status"], "NEEDS_REVIEW")
            self.assertIn("ANNOUNCEMENT_TIME_UNKNOWN", frozen["reason_codes"])
            self.assertIsNone(calculate_surprise(event, frozen, actual())["surprise_pct"])

    def test_fiscal_period_mismatch_does_not_compare(self):
        frozen = freeze_pre_event_expectation(EVENT, [snapshot(fiscal_period="FY2027")], metric="EPS", unit="JPY")
        self.assertEqual(frozen["freeze_status"], "UNAVAILABLE")
        self.assertIn("FISCAL_PERIOD_MISMATCH", frozen["reason_codes"])

    def test_unit_mismatch_does_not_compare(self):
        frozen = freeze_pre_event_expectation(EVENT, [snapshot(unit="JPY_MN")], metric="EPS", unit="JPY")
        self.assertEqual(frozen["freeze_status"], "UNAVAILABLE")
        self.assertIn("UNIT_MISMATCH", frozen["reason_codes"])

    def test_share_basis_mismatch_fails_closed(self):
        frozen = freeze_pre_event_expectation(EVENT, [snapshot()], metric="EPS", unit="JPY")
        result = calculate_surprise(EVENT, frozen, actual(share_basis="DILUTED_PRE_SPLIT"))
        self.assertEqual(result["status"], "NEEDS_REVIEW")
        self.assertIn("SHARE_BASIS_MISMATCH", result["warning_codes"])
        self.assertIsNone(result["surprise_pct"])

    def test_no_pre_event_snapshot_is_unavailable_not_zero(self):
        after = snapshot(observed_at="2026-08-04T16:00:00+09:00", value=120.0)
        frozen = freeze_pre_event_expectation(EVENT, [after], metric="EPS", unit="JPY")
        result = calculate_surprise(EVENT, frozen, actual())
        self.assertEqual(frozen["freeze_status"], "UNAVAILABLE")
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertIsNone(result["surprise_abs"])
        self.assertIsNone(result["surprise_pct"])

    def test_identical_rerun_is_deterministic(self):
        rows = [snapshot(observed_at="2026-08-04T09:00:00+09:00", value=98.0), snapshot(value=100.0)]
        first = freeze_pre_event_expectation(EVENT, rows, metric="EPS", unit="JPY")
        second = freeze_pre_event_expectation(EVENT, copy.deepcopy(rows), metric="EPS", unit="JPY")
        self.assertEqual(first, second)
        self.assertEqual(calculate_surprise(EVENT, first, actual()), calculate_surprise(EVENT, second, actual()))

    def test_same_timestamp_conflicting_snapshot_requires_review(self):
        first = snapshot(observed_at="2026-08-04T10:00:00+09:00", value=100.0)
        second = snapshot(observed_at="2026-08-04T10:00:00+09:00", value=101.0)
        frozen = freeze_pre_event_expectation(EVENT, [first, second], metric="EPS", unit="JPY")
        self.assertEqual(frozen["freeze_status"], "NEEDS_REVIEW")
        self.assertIn("CONFLICTING_SNAPSHOT", frozen["reason_codes"])

    def test_stale_snapshot_remains_visible_as_warning(self):
        stale = snapshot(status="STALE")
        frozen = freeze_pre_event_expectation(EVENT, [stale], metric="EPS", unit="JPY")
        result = calculate_surprise(EVENT, frozen, actual())
        self.assertEqual(frozen["freeze_status"], "FROZEN")
        self.assertIn("STALE_EXPECTATION", frozen["reason_codes"])
        self.assertIn("STALE_EXPECTATION", result["warning_codes"])

    def test_guidance_and_sado_comparisons_keep_separate_identity(self):
        frozen = freeze_pre_event_expectation(EVENT, [snapshot()], metric="EPS", unit="JPY")
        guidance = calculate_surprise(EVENT, frozen, actual(value=105.0), comparison_kind="company_guidance_vs_consensus")
        sado = calculate_surprise(EVENT, frozen, actual(value=125.0), comparison_kind="sado_base_vs_consensus")
        self.assertEqual(guidance["comparison_kind"], "company_guidance_vs_consensus")
        self.assertEqual(sado["comparison_kind"], "sado_base_vs_consensus")
        self.assertNotEqual(guidance["surprise_pct"], sado["surprise_pct"])

    def test_zero_expectation_denominator_is_not_divided(self):
        frozen = freeze_pre_event_expectation(EVENT, [snapshot(value=0.0)], metric="EPS", unit="JPY")
        result = calculate_surprise(EVENT, frozen, actual())
        self.assertEqual(result["status"], "NEEDS_REVIEW")
        self.assertIn("ZERO_EXPECTATION_DENOMINATOR", result["warning_codes"])
        self.assertIsNone(result["surprise_pct"])


if __name__ == "__main__":
    unittest.main()
