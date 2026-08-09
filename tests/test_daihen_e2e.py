from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.daihen_e2e import DaihenE2EError, run_daihen_first_e2e

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "data/research/company/6622/company-research-v1.json"


class DaihenFirstE2ECompletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    def test_missing_market_quote_blocks_without_fabricating_price(self):
        result = run_daihen_first_e2e(
            self.raw,
            market_quote=None,
            scenario_net_income_unit="JPY_MN",
        )
        self.assertEqual(result["status"], "BLOCKED_MARKET_PRICE_UNAVAILABLE")
        self.assertIsNone(result["valuation"])
        self.assertIn("market_quote.value", result["missing"])

    def test_explicit_quote_completes_research_to_valuation_to_hypothesis(self):
        # Deliberately a deterministic test fixture, not a claim about the current market price.
        quote = {
            "value": 8000,
            "as_of": "2026-08-07",
            "source": "TEST_FIXTURE_EXPLICIT_QUOTE",
            "share_basis": "PRE_SPLIT",
        }
        result = run_daihen_first_e2e(
            self.raw,
            market_quote=quote,
            scenario_net_income_unit="JPY_MN",
            target_pers=[15, 20, 25],
        )
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["security_code"], "6622")
        valuation = result["valuation"]
        self.assertEqual(valuation["target_fiscal_year"], "FY2027")
        self.assertEqual(valuation["price"]["source"], "TEST_FIXTURE_EXPLICIT_QUOTE")
        self.assertAlmostEqual(valuation["scenario_results"]["base"]["eps"], 720.1, places=1)
        self.assertAlmostEqual(valuation["scenario_results"]["base"]["forward_per"], 11.11, places=2)
        self.assertAlmostEqual(valuation["scenario_results"]["base"]["implied_prices"]["per_20"], 14401.95, places=2)
        self.assertTrue(result["hypothesis"]["must_happen"])
        self.assertIn("issue:172#issuecomment-5229957439", result["provenance"]["candidate"])
        self.assertTrue(result["provenance"]["research_sources"])
        self.assertTrue(result["provenance"]["hypothesis_sources"])

    def test_net_income_unit_is_explicit_and_fail_closed(self):
        with self.assertRaises(DaihenE2EError):
            run_daihen_first_e2e(
                self.raw,
                market_quote=None,
                scenario_net_income_unit="JPY",
            )

    def test_quote_requires_source_as_of_and_matching_share_basis(self):
        with self.assertRaises(DaihenE2EError):
            run_daihen_first_e2e(
                self.raw,
                market_quote={"value": 8000, "as_of": "2026-08-07", "source": "TEST", "share_basis": "POST_SPLIT"},
                scenario_net_income_unit="JPY_MN",
            )


if __name__ == "__main__":
    unittest.main()
