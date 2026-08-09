from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts.company_research import CompanyResearchError
from scripts.forward_per_research_adapter import (
    ForwardPerAdapterError,
    research_to_simulator_input,
    simulate_research,
)


ROOT = Path(__file__).resolve().parents[1]
DAIHEN_RESEARCH = ROOT / "data/research/company/6622/company-research-v1.json"
DAIHEN_VALUATION = ROOT / "data/research/company/6622/e2e-valuation-input-v1.json"

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
    @classmethod
    def setUpClass(cls):
        cls.daihen_research = json.loads(DAIHEN_RESEARCH.read_text(encoding="utf-8"))
        cls.daihen_valuation = json.loads(DAIHEN_VALUATION.read_text(encoding="utf-8"))

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

    def test_net_income_without_explicit_unit_fails_closed(self):
        payload = copy.deepcopy(RESEARCH)
        payload["scenarios"]["base"]["eps"] = None
        payload["scenarios"]["base"]["net_income"] = 17_000
        with self.assertRaises(ForwardPerAdapterError):
            research_to_simulator_input(payload, price=PRICE)

    def test_canonical_daihen_research_normalizes_unit_and_share_basis(self):
        valuation = self.daihen_valuation
        normalization = {
            "scenario_net_income_unit": valuation["scenario_net_income_unit"],
            "scenario_net_income_unit_source": valuation["scenario_net_income_unit_source"],
            "share_basis_field": valuation["share_basis_field"],
            "share_basis_role": valuation["share_basis_role"],
        }
        reference = valuation["reference_price"]
        price = {
            "value": reference["value_jpy"],
            "as_of": reference["as_of"],
            "source": reference["source"],
        }
        mapped = research_to_simulator_input(
            self.daihen_research,
            price=price,
            normalization=normalization,
        )
        self.assertEqual(mapped["scenarios"]["base"]["net_income"], 17_000_000_000)
        self.assertEqual(mapped["share_basis"]["diluted_shares"], 23_607_976)
        self.assertEqual(mapped["scenarios"]["base"]["provenance"]["net_income_unit_input"], "million_jpy")
        self.assertEqual(mapped["share_basis"]["source_field"], "shares")

        result = simulate_research(
            self.daihen_research,
            price=price,
            target_pers=[20],
            normalization=normalization,
        )
        scenarios = result["scenario_results"]
        self.assertEqual(scenarios["bear"]["eps"], 571.84)
        self.assertEqual(scenarios["base"]["eps"], 720.1)
        self.assertEqual(scenarios["bull"]["eps"], 847.17)
        self.assertEqual(scenarios["base"]["forward_per"], 16.53)
        self.assertEqual(scenarios["base"]["implied_prices"]["per_20"], 14401.91)


if __name__ == "__main__":
    unittest.main()
