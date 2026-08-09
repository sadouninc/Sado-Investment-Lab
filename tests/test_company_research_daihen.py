from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.company_research import CompanyResearchRecord, build_forward_valuation_handoff

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "data/research/company/6622/company-research-v1.json"


class DaihenCompanyResearchE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    def test_owner_fixed_identity_and_current_quality_gate(self):
        record = CompanyResearchRecord.from_mapping(self.raw)
        self.assertEqual(record.security_code, "6622")
        self.assertEqual(record.status, "CURRENT")
        self.assertIn("OWNER_DECISION", record.selection_context["candidate_sources"])

    def test_business_is_not_flattened_into_ai_dc_only(self):
        segments = self.raw["facts"]["earnings_engine"]["segment_q1"]
        self.assertEqual(set(segments), {"energy_management", "factory_automation", "material_processing"})
        self.assertGreater(segments["energy_management"]["orders_million_jpy"], segments["material_processing"]["orders_million_jpy"])

    def test_q1_primary_facts_and_guidance_are_preserved(self):
        latest = self.raw["facts"]["latest_financials"]
        self.assertEqual(latest["revenue_million_jpy"], 55507)
        self.assertEqual(latest["operating_profit_million_jpy"], 4079)
        self.assertEqual(latest["net_income_attributable_million_jpy"], 2779)
        guidance = self.raw["facts"]["earnings_engine"]["company_guidance_fy2027"]
        self.assertEqual(guidance["net_income_million_jpy"], 16500)
        self.assertFalse(guidance["guidance_revised_at_q1"])

    def test_forward_handoff_keeps_net_income_and_pre_split_share_basis(self):
        handoff = build_forward_valuation_handoff(self.raw)
        self.assertEqual(handoff["security_code"], "6622")
        for name in ("bear", "base", "bull"):
            scenario = handoff["scenarios"][name]
            self.assertIsNone(scenario["eps"])
            self.assertIsNotNone(scenario["net_income"])
            self.assertEqual(scenario["share_basis"]["shares"], 23607976)
        self.assertNotEqual(handoff["scenarios"]["base"]["net_income"], 16500)

    def test_missing_market_price_is_not_fabricated(self):
        valuation = self.raw["interpretation"]["valuation_context"]
        self.assertIsNone(valuation["price"])
        self.assertIsNone(valuation["price_as_of"])


if __name__ == "__main__":
    unittest.main()
