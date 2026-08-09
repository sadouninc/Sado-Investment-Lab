from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.company_research import CompanyResearchRecord, build_forward_valuation_handoff
from scripts.company_research_queue import ResearchQueueRecord, start_research


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "data/research/company/7974/company-research-v1.json"


class NintendoCompanyResearchE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    def test_real_artifact_passes_current_quality_gate(self):
        record = CompanyResearchRecord.from_mapping(self.raw)
        self.assertEqual(record.security_code, "7974")
        self.assertEqual(record.status, "CURRENT")
        self.assertEqual(record.data_completeness, "COMPLETE")

    def test_discovery_provenance_and_explicit_start_research_gate_are_preserved(self):
        selection = self.raw["selection_context"]
        queue = ResearchQueueRecord.from_candidate_handoff(
            {
                "security_code": self.raw["security_code"],
                "company_name": self.raw["company_name"],
                "candidate_sources": selection["candidate_sources"],
                "selection_reason": selection["selection_reason"],
                "owner_pick": selection["owner_pick"],
                "candidate_as_of": selection["candidate_as_of"],
                "research_status": selection["research_status_before"],
                "research_gap": selection["research_gap"],
                "money_flow_context": selection["money_flow_context"],
            }
        )
        self.assertEqual(queue.status, "QUEUED")
        started = start_research(queue, command=selection["research_gate"]["command"])
        self.assertEqual(started.status, "IN_PROGRESS")
        self.assertIn("MONEY_FLOW_THEME_MEMBERSHIP", started.candidate_sources)
        self.assertEqual(started.money_flow_context["state"], "UNKNOWN")

    def test_company_guidance_is_fact_anchor_not_sado_base_identity(self):
        guidance = self.raw["facts"]["earnings_engine"]["company_guidance_fy2027"]
        base = self.raw["scenarios"]["base"]
        self.assertEqual(guidance["net_income_million_jpy"], 310000)
        self.assertEqual(base["source_type"], "SADO_BASE")
        self.assertNotEqual(base["net_income"], guidance["net_income_million_jpy"])
        self.assertIn("not the Sado Base itself", base["assumptions"][0])

    def test_forward_valuation_handoff_preserves_net_income_and_share_basis(self):
        handoff = build_forward_valuation_handoff(self.raw)
        self.assertEqual(handoff["security_code"], "7974")
        for name in ("bear", "base", "bull"):
            scenario = handoff["scenarios"][name]
            self.assertIsNone(scenario["eps"])
            self.assertIsNotNone(scenario["net_income"])
            self.assertEqual(scenario["share_basis"]["shares"], 1152828616)
            self.assertTrue(scenario["source_refs"])
        self.assertEqual(handoff["scenarios"]["base"]["source_type"], "SADO_BASE")

    def test_market_price_is_not_fabricated_inside_research(self):
        valuation = self.raw["interpretation"]["valuation_context"]
        self.assertIsNone(valuation["price"])
        self.assertIsNone(valuation["price_as_of"])


if __name__ == "__main__":
    unittest.main()
