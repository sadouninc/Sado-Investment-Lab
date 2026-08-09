from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.forward_per_research_adapter import (
    ForwardPerAdapterError,
    research_to_simulator_input,
    simulate_research,
)
from scripts.investment_e2e import run_first_e2e


ROOT = Path(__file__).resolve().parents[1]
RESEARCH_PATH = ROOT / "data/research/company/6622/company-research-v1.json"
VALUATION_INPUT_PATH = ROOT / "data/research/company/6622/e2e-valuation-input-v1.json"


class DaihenForwardPerRealDataAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.research = json.loads(RESEARCH_PATH.read_text(encoding="utf-8"))
        cls.valuation_input = json.loads(VALUATION_INPUT_PATH.read_text(encoding="utf-8"))
        reference = cls.valuation_input["reference_price"]
        cls.price = {
            "value": reference["value_jpy"],
            "as_of": reference["as_of"],
            "source": reference["source"],
        }
        cls.normalization = {
            "scenario_net_income_unit": cls.valuation_input["scenario_net_income_unit"],
            "scenario_net_income_unit_source": cls.valuation_input["scenario_net_income_unit_source"],
            "share_basis_field": "shares",
            "share_basis_role": "valuation_denominator",
        }

    def test_real_company_research_maps_through_canonical_adapter(self):
        mapped = research_to_simulator_input(
            self.research,
            price=self.price,
            normalization=self.normalization,
        )
        self.assertEqual(mapped["security_code"], "6622")
        self.assertEqual(mapped["target_fiscal_year"], "FY2027")
        self.assertEqual(mapped["share_basis"]["diluted_shares"], 23_607_976)
        self.assertEqual(mapped["share_basis"]["source_field"], "shares")
        self.assertEqual(mapped["share_basis"]["denominator_role"], "valuation_denominator")
        self.assertEqual(mapped["scenarios"]["base"]["net_income"], 17_000_000_000)
        provenance = mapped["scenarios"]["base"]["provenance"]
        self.assertEqual(provenance["net_income_unit_input"], "million_jpy")
        self.assertEqual(provenance["net_income_unit_output"], "jpy")
        self.assertTrue(provenance["net_income_unit_source"])

    def test_real_data_bear_base_bull_reaches_forward_per_core(self):
        result = simulate_research(
            self.research,
            price=self.price,
            target_pers=[15, 20, 25],
            normalization=self.normalization,
        )
        scenarios = result["scenario_results"]
        self.assertEqual(scenarios["bear"]["eps"], 571.84)
        self.assertEqual(scenarios["base"]["eps"], 720.1)
        self.assertEqual(scenarios["bull"]["eps"], 847.17)
        self.assertEqual(scenarios["bear"]["forward_per"], 20.81)
        self.assertEqual(scenarios["base"]["forward_per"], 16.53)
        self.assertEqual(scenarios["bull"]["forward_per"], 14.05)
        self.assertEqual(scenarios["base"]["implied_prices"]["per_20"], 14401.91)
        self.assertTrue(result["provenance"]["selection_context"]["owner_pick"])

    def test_canonical_adapter_matches_full_first_e2e_valuation(self):
        canonical = simulate_research(
            self.research,
            price=self.price,
            target_pers=[15, 20, 25],
            normalization=self.normalization,
        )
        full = run_first_e2e(self.research, self.valuation_input)
        self.assertEqual(canonical["scenario_results"], full["valuation"]["scenario_results"])
        self.assertEqual(full["hypothesis"]["monitor_status"], "MONITOR_READY")
        self.assertEqual(full["hypothesis"]["system_status"], "INTACT")
        self.assertEqual(full["provenance_chain"][0], "OWNER_DECISION")
        self.assertEqual(full["provenance_chain"][-1], "MONITOR_READY")

    def test_reference_price_is_preserved_not_promoted_to_current(self):
        result = simulate_research(
            self.research,
            price=self.price,
            normalization=self.normalization,
        )
        self.assertEqual(result["price"]["value"], 11900)
        self.assertEqual(result["price"]["as_of"], "2026-07-29")
        self.assertIn("monex", result["price"]["source"])

    def test_missing_explicit_share_role_fails_closed(self):
        normalization = dict(self.normalization)
        normalization.pop("share_basis_role")
        with self.assertRaises(ForwardPerAdapterError):
            research_to_simulator_input(
                self.research,
                price=self.price,
                normalization=normalization,
            )

    def test_unknown_income_unit_fails_closed(self):
        normalization = dict(self.normalization)
        normalization["scenario_net_income_unit"] = "unknown"
        with self.assertRaises(ForwardPerAdapterError):
            research_to_simulator_input(
                self.research,
                price=self.price,
                normalization=normalization,
            )

    def test_real_data_rerun_is_deterministic(self):
        first = simulate_research(
            self.research,
            price=self.price,
            target_pers=[15, 20, 25],
            normalization=self.normalization,
        )
        second = simulate_research(
            self.research,
            price=self.price,
            target_pers=[15, 20, 25],
            normalization=self.normalization,
        )
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
