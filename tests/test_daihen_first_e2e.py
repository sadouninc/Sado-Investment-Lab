from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.investment_e2e import InvestmentE2EError, build_simulator_input, run_first_e2e

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "data/research/company/6622/company-research-v1.json"
VALUATION_INPUT = ROOT / "data/research/company/6622/e2e-valuation-input-v1.json"


class DaihenFirstE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.research = json.loads(RESEARCH.read_text(encoding="utf-8"))
        cls.valuation_input = json.loads(VALUATION_INPUT.read_text(encoding="utf-8"))

    def test_candidate_queue_research_forward_per_hypothesis_all_connect(self):
        result = run_first_e2e(self.research, self.valuation_input)
        self.assertEqual(result["security_code"], "6622")
        self.assertTrue(result["candidate"]["owner_pick"])
        self.assertEqual(result["queue"]["identity"], "company-research:6622")
        self.assertEqual(result["queue"]["first_enqueue"], "INSERTED")
        self.assertEqual(result["queue"]["second_enqueue"], "UNCHANGED")
        self.assertEqual(result["queue"]["start_status"], "IN_PROGRESS")
        self.assertEqual(result["queue"]["final_status"], "CURRENT")
        self.assertEqual(result["hypothesis"]["monitor_status"], "MONITOR_READY")
        self.assertEqual(result["hypothesis"]["system_status"], "INTACT")

    def test_million_jpy_is_explicitly_normalized_before_eps_calculation(self):
        simulator_input = build_simulator_input(self.research, self.valuation_input)
        self.assertEqual(simulator_input["scenarios"]["base"]["net_income"], 17_000_000_000)
        self.assertEqual(simulator_input["share_basis"]["diluted_shares"], 23_607_976)
        provenance = simulator_input["scenarios"]["base"]["provenance"]
        self.assertEqual(provenance["net_income_unit_input"], "million_jpy")
        self.assertEqual(provenance["net_income_unit_output"], "jpy")
        self.assertTrue(provenance["unit_source"])

    def test_forward_per_and_implied_price_are_calculated_for_all_scenarios(self):
        result = run_first_e2e(self.research, self.valuation_input)
        scenarios = result["valuation"]["scenario_results"]
        self.assertEqual(scenarios["bear"]["eps"], 571.84)
        self.assertEqual(scenarios["base"]["eps"], 720.1)
        self.assertEqual(scenarios["bull"]["eps"], 847.17)
        self.assertEqual(scenarios["bear"]["forward_per"], 20.81)
        self.assertEqual(scenarios["base"]["forward_per"], 16.53)
        self.assertEqual(scenarios["bull"]["forward_per"], 14.05)
        self.assertEqual(scenarios["base"]["implied_prices"]["per_20"], 14401.91)

    def test_stale_reference_price_is_explicit_not_silently_current(self):
        result = run_first_e2e(self.research, self.valuation_input)
        self.assertEqual(result["valuation"]["price"]["value"], 11900)
        self.assertEqual(result["valuation"]["price"]["as_of"], "2026-07-29")
        self.assertIn("PRICE_STALE_FOR_E2E", result["valuation"]["warnings"])

    def test_monitor_ready_contract_keeps_research_and_valuation_refs(self):
        result = run_first_e2e(self.research, self.valuation_input)
        hypothesis = result["hypothesis"]
        self.assertGreaterEqual(len(hypothesis["must_happen"]), 1)
        self.assertGreaterEqual(len(hypothesis["invalidation_conditions"]), 1)
        self.assertGreaterEqual(len(hypothesis["next_checkpoints"]), 1)
        self.assertTrue(hypothesis["source_research_ref"].startswith("company-research:6622:"))
        self.assertTrue(hypothesis["source_valuation_ref"].startswith("forward-per:6622:FY2027:"))
        self.assertEqual(result["provenance_chain"][0], "OWNER_DECISION")
        self.assertEqual(result["provenance_chain"][-1], "MONITOR_READY")

    def test_unknown_income_unit_fails_closed(self):
        valuation = dict(self.valuation_input)
        valuation["scenario_net_income_unit"] = "unknown"
        with self.assertRaises(InvestmentE2EError):
            build_simulator_input(self.research, valuation)

    def test_rerun_is_deterministic(self):
        first = run_first_e2e(self.research, self.valuation_input)
        second = run_first_e2e(self.research, self.valuation_input)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
