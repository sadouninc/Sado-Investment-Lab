from __future__ import annotations

import copy
import unittest

from scripts.company_research import CompanyResearchError
from scripts.forward_per_research_adapter import (
    ForwardPerAdapterError,
    research_to_simulator_input,
    simulate_research,
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
            "net_income": None,
            "share_basis": {"diluted_shares": 100_000_000, "as_of": "2026-08-01"},
            "assumptions": ["bear"],
            "confidence": "LOW",
            "source_type": "SADO_BEAR",
            "source_refs": ["ir:q1"],
            "as_of": "2026-08-09",
        },
        "base": {
            "target_fiscal_year": "FY2029",
            "eps": 400,
            "net_income": None,
            "share_basis": {"diluted_shares": 100_000_000, "as_of": "2026-08-01"},
            "assumptions": ["base"],
            "confidence": "MEDIUM",
            "source_type": "SADO_BASE",
            "source_refs": ["ir:q1"],
            "as_of": "2026-08-09",
        },
        "bull": {
            "target_fiscal_year": "FY2029",
            "eps": 500,
            "net_income": None,
            "share_basis": {"diluted_shares": 100_000_000, "as_of": "2026-08-01"},
            "assumptions": ["bull"],
            "confidence": "LOW",
            "source_type": "SADO_BULL",
            "source_refs": ["ir:q1"],
            "as_of": "2026-08-09",
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

PRICE = {"value": 10000, "as_of": "2026-08-07", "source": "MARKET_DATA"}


class ForwardPerResearchAdapterTests(unittest.TestCase):
    def test_current_research_maps_to_simulator_and_preserves_owner_pick_provenance(self):
        mapped = research_to_simulator_input(RESEARCH, price=PRICE)
        self.assertEqual(mapped["security_code"], "6622")
        self.assertEqual(mapped["target_fiscal_year"], "FY2029")
        self.assertEqual(mapped["share_basis"]["diluted_shares"], 100_000_000)
        self.assertEqual(mapped["provenance"]["selection_context"]["candidate_sources"], ["OWNER_PICK"])

    def test_research_simulation_uses_core_calculation(self):
        result = simulate_research(RESEARCH, price=PRICE, target_pers=[20])
        self.assertEqual(result["scenario_results"]["base"]["forward_per"], 25)
        self.assertEqual(result["scenario_results"]["base"]["implied_prices"]["per_20"], 8000)
        self.assertEqual(result["provenance"]["selection_context"]["selection_reason"], "FIRST_E2E_VALIDATION")

    def test_adapter_does_not_mutate_research(self):
        original = copy.deepcopy(RESEARCH)
        simulate_research(RESEARCH, price=PRICE, custom_price=8000)
        self.assertEqual(RESEARCH, original)

    def test_non_current_research_is_rejected_by_canonical_gate(self):
        payload = copy.deepcopy(RESEARCH)
        payload["status"] = "IN_PROGRESS"
        with self.assertRaises(CompanyResearchError):
            research_to_simulator_input(payload, price=PRICE)

    def test_target_fiscal_year_mismatch_fails_closed(self):
        payload = copy.deepcopy(RESEARCH)
        payload["scenarios"]["bull"]["target_fiscal_year"] = "FY2030"
        with self.assertRaises(ForwardPerAdapterError):
            research_to_simulator_input(payload, price=PRICE)

    def test_missing_price_as_of_fails_closed(self):
        with self.assertRaises(ForwardPerAdapterError):
            research_to_simulator_input(RESEARCH, price={"value": 10000})


if __name__ == "__main__":
    unittest.main()
