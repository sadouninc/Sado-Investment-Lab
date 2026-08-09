from __future__ import annotations

import copy
import unittest

from scripts.forward_per_simulator import sensitivity_matrix, simulate


INPUT = {
    "security_code": "6622",
    "company_name": "ダイヘン",
    "research_as_of": "2026-08-09",
    "target_fiscal_year": "FY2029",
    "price": {"value": 10000, "as_of": "2026-08-07", "source": "MARKET_DATA"},
    "share_basis": {"diluted_shares": 100_000_000, "as_of": "2026-08-09", "assumption": "CURRENT_DILUTED_SHARES"},
    "scenarios": {
        "bear": {"net_income": 30_000_000_000, "assumptions": ["bear"], "confidence": "LOW"},
        "base": {"eps": 400, "net_income": 40_000_000_000, "assumptions": ["base"], "confidence": "MEDIUM"},
        "bull": {"eps": 500, "assumptions": ["bull"], "confidence": "LOW"},
    },
}


class ForwardPerSimulatorTests(unittest.TestCase):
    def test_bear_base_bull_current_price(self):
        result = simulate(INPUT)
        self.assertEqual(result["scenario_results"]["bear"]["eps"], 300)
        self.assertEqual(result["scenario_results"]["bear"]["forward_per"], 33.33)
        self.assertEqual(result["scenario_results"]["base"]["forward_per"], 25)
        self.assertEqual(result["scenario_results"]["bull"]["forward_per"], 20)

    def test_custom_price_does_not_mutate_canonical_input(self):
        original = copy.deepcopy(INPUT)
        result = simulate(INPUT, price=8000)
        self.assertEqual(result["price"]["mode"], "CUSTOM")
        self.assertEqual(result["scenario_results"]["base"]["forward_per"], 20)
        self.assertEqual(INPUT, original)

    def test_target_per_implied_price(self):
        result = simulate(INPUT, target_pers=[15, 20, 25])
        self.assertEqual(result["scenario_results"]["base"]["implied_prices"]["per_20"], 8000)

    def test_missing_eps_and_net_income_remains_unavailable(self):
        payload = copy.deepcopy(INPUT)
        payload["scenarios"]["bear"] = {}
        result = simulate(payload)
        self.assertIsNone(result["scenario_results"]["bear"]["forward_per"])
        self.assertIn("BEAR:EPS_UNAVAILABLE", result["warnings"])

    def test_negative_and_zero_eps_are_not_meaningful(self):
        for eps in (-10, 0):
            payload = copy.deepcopy(INPUT)
            payload["scenarios"]["bear"] = {"eps": eps}
            result = simulate(payload)
            self.assertEqual(result["scenario_results"]["bear"]["forward_per"], "N/M")

    def test_eps_net_income_share_inconsistency_warning(self):
        payload = copy.deepcopy(INPUT)
        payload["scenarios"]["base"]["eps"] = 500
        result = simulate(payload)
        self.assertIn("BASE:EPS_NET_INCOME_SHARE_INCONSISTENCY", result["warnings"])

    def test_missing_share_basis_does_not_guess_eps(self):
        payload = copy.deepcopy(INPUT)
        payload["share_basis"]["diluted_shares"] = None
        payload["scenarios"]["bear"] = {"net_income": 30_000_000_000}
        result = simulate(payload)
        self.assertIsNone(result["scenario_results"]["bear"]["eps"])
        self.assertIn("DILUTED_SHARES_UNAVAILABLE", result["warnings"])

    def test_deterministic_rerun(self):
        self.assertEqual(simulate(INPUT), simulate(INPUT))

    def test_sensitivity_matrix(self):
        rows = sensitivity_matrix([300, 400], [15, 20])
        self.assertEqual(rows[1]["implied_prices"]["per_20"], 8000)


if __name__ == "__main__":
    unittest.main()
