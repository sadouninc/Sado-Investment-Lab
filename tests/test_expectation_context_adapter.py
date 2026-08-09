from __future__ import annotations

import copy
import unittest

from scripts.expectation_context_adapter import (
    ExpectationContextError,
    attach_expectation_to_forward_per,
    build_company_research_expectation_view,
    build_research_expectation_context,
    latest_external_expectation,
)


RESEARCH = {
    "security_code": "6622",
    "company_name": "ダイヘン",
    "as_of": "2026-08-09",
    "status": "CURRENT",
    "selection_context": {
        "candidate_sources": ["OWNER_PICK"],
        "selection_reason": "FIRST_E2E_VALIDATION",
        "owner_pick": True,
    },
    "facts": {
        "latest_financials": {"revenue": 100, "source_ref": "ir:q1", "as_of": "2026-08-01"},
        "earnings_engine": {"drivers": ["power infrastructure"]},
    },
    "interpretation": {
        "growth_drivers": ["data-center power demand"],
        "risks": ["capex slowdown"],
    },
    "scenarios": {
        "bear": {
            "target_fiscal_year": "FY2029",
            "eps": 300,
            "share_basis": {"basis": "BASIC", "shares": 100_000_000},
            "assumptions": ["bear"],
            "source_type": "SADO_BEAR",
            "source_refs": ["ir:q1"],
        },
        "base": {
            "target_fiscal_year": "FY2029",
            "eps": 500,
            "share_basis": {"basis": "BASIC", "shares": 100_000_000},
            "assumptions": ["base"],
            "source_type": "SADO_BASE",
            "source_refs": ["ir:q1"],
        },
        "bull": {
            "target_fiscal_year": "FY2029",
            "eps": 650,
            "share_basis": {"basis": "BASIC", "shares": 100_000_000},
            "assumptions": ["bull"],
            "source_type": "SADO_BULL",
            "source_refs": ["ir:q1"],
        },
    },
    "hypothesis": {
        "what_market_may_be_underestimating": "earnings durability",
        "must_happen": ["orders grow"],
        "key_kpis": ["orders"],
        "invalidation_conditions": ["orders fall"],
        "expected_time_horizon": "FY2027-FY2029",
        "current_confidence": "MEDIUM",
    },
    "source_refs": ["ir:q1"],
    "data_completeness": "COMPLETE",
}


def consensus(*, as_of: str, observed_at: str, value: float | None, status: str = "OK", period: str = "FY2029", unit: str = "JPY", basis: str = "BASIC"):
    return {
        "security_code": "6622",
        "target_fiscal_period": period,
        "as_of": as_of,
        "expectation_type": "CONSENSUS",
        "metric": "EPS",
        "value": value,
        "unit": unit,
        "source_ref": f"consensus:{as_of}",
        "source_authority": "SECONDARY",
        "observed_at": observed_at,
        "coverage": {"analyst_count": 8, "dispersion": 25, "status": status},
        "provenance": {"share_basis": {"basis": basis, "shares": 100_000_000}},
    }


HISTORY = [
    consensus(as_of="2026-07-01", observed_at="2026-07-01T09:00:00+09:00", value=400),
    consensus(as_of="2026-08-01", observed_at="2026-08-01T09:00:00+09:00", value=420),
]


VALUATION = {
    "security_code": "6622",
    "company_name": "ダイヘン",
    "research_as_of": "2026-08-09",
    "target_fiscal_year": "FY2029",
    "price": {"value": 10000, "as_of": "2026-08-07", "source": "market"},
    "scenario_results": {
        "base": {"eps": 500, "forward_per": 20, "implied_prices": {"per_20": 10000}}
    },
    "warnings": [],
}


class ExpectationContextAdapterTests(unittest.TestCase):
    def test_latest_external_expectation_tracks_revision_direction(self):
        result = latest_external_expectation(
            HISTORY,
            security_code="6622",
            target_fiscal_period="FY2029",
            metric="EPS",
            unit="JPY",
        )
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["snapshot"]["value"], 420)
        self.assertEqual(result["direction"], "UP")
        self.assertEqual(result["observation_count"], 2)

    def test_sado_base_vs_consensus_is_separate_context(self):
        original = copy.deepcopy(RESEARCH)
        context = build_research_expectation_context(
            RESEARCH,
            HISTORY,
            metric="EPS",
            unit="JPY",
            sado_value_unit="JPY",
        )
        self.assertEqual(context["status"], "OK")
        self.assertEqual(context["sado_value"], 500)
        self.assertEqual(context["external_expectation"]["snapshot"]["value"], 420)
        self.assertAlmostEqual(context["sado_vs_consensus_pct"], 500 / 420 - 1)
        self.assertEqual(context["sado_source_type"], "SADO_BASE")
        self.assertEqual(RESEARCH, original)

    def test_unit_mismatch_fails_closed_without_gap(self):
        context = build_research_expectation_context(
            RESEARCH,
            HISTORY,
            metric="EPS",
            unit="JPY",
            sado_value_unit="JPY_MN",
        )
        self.assertEqual(context["status"], "NEEDS_REVIEW")
        self.assertIsNone(context["sado_vs_consensus_pct"])
        self.assertIn("UNIT_MISMATCH", context["reason_codes"])

    def test_share_basis_mismatch_fails_closed(self):
        history = [consensus(as_of="2026-08-01", observed_at="2026-08-01T09:00:00+09:00", value=420, basis="DILUTED")]
        context = build_research_expectation_context(
            RESEARCH,
            history,
            metric="EPS",
            unit="JPY",
            sado_value_unit="JPY",
        )
        self.assertEqual(context["status"], "NEEDS_REVIEW")
        self.assertIsNone(context["sado_vs_consensus_pct"])
        self.assertIn("SHARE_BASIS_MISMATCH", context["reason_codes"])

    def test_stale_expectation_is_preserved_as_warning_context(self):
        history = [consensus(as_of="2026-06-01", observed_at="2026-06-01T09:00:00+09:00", value=410, status="STALE")]
        context = build_research_expectation_context(
            RESEARCH,
            history,
            metric="EPS",
            unit="JPY",
            sado_value_unit="JPY",
        )
        self.assertEqual(context["status"], "OK")
        self.assertIn("STALE_EXPECTATION", context["reason_codes"])
        self.assertAlmostEqual(context["sado_vs_consensus_pct"], 500 / 410 - 1)

    def test_unavailable_is_not_zero_gap(self):
        history = [consensus(as_of="2026-08-01", observed_at="2026-08-01T09:00:00+09:00", value=None, status="UNAVAILABLE")]
        context = build_research_expectation_context(
            RESEARCH,
            history,
            metric="EPS",
            unit="JPY",
            sado_value_unit="JPY",
        )
        self.assertEqual(context["status"], "UNAVAILABLE")
        self.assertIsNone(context["sado_vs_consensus_abs"])
        self.assertIsNone(context["sado_vs_consensus_pct"])

    def test_forward_per_attachment_does_not_change_calculation(self):
        context = build_research_expectation_context(
            RESEARCH,
            HISTORY,
            metric="EPS",
            unit="JPY",
            sado_value_unit="JPY",
        )
        enriched = attach_expectation_to_forward_per(VALUATION, context)
        self.assertEqual(enriched["scenario_results"], VALUATION["scenario_results"])
        self.assertEqual(enriched["expectation_context"], context)
        self.assertNotIn("expectation_context", VALUATION)

    def test_company_research_view_keeps_fundamental_and_expectation_separate(self):
        context = build_research_expectation_context(
            RESEARCH,
            HISTORY,
            metric="EPS",
            unit="JPY",
            sado_value_unit="JPY",
        )
        view = build_company_research_expectation_view(RESEARCH, context)
        self.assertEqual(view["fundamental_context"]["research_status"], "CURRENT")
        self.assertEqual(view["fundamental_context"]["hypothesis_confidence"], "MEDIUM")
        self.assertEqual(view["external_expectation_context"]["external_expectation"]["direction"], "UP")

    def test_target_period_mismatch_rejected_on_forward_attachment(self):
        context = build_research_expectation_context(
            RESEARCH,
            HISTORY,
            metric="EPS",
            unit="JPY",
            sado_value_unit="JPY",
        )
        wrong = dict(VALUATION)
        wrong["target_fiscal_year"] = "FY2030"
        with self.assertRaises(ExpectationContextError):
            attach_expectation_to_forward_per(wrong, context)

    def test_deterministic_rerun(self):
        first = build_research_expectation_context(
            RESEARCH,
            HISTORY,
            metric="EPS",
            unit="JPY",
            sado_value_unit="JPY",
        )
        second = build_research_expectation_context(
            RESEARCH,
            HISTORY,
            metric="EPS",
            unit="JPY",
            sado_value_unit="JPY",
        )
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
