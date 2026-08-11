from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "04_Market" / "Analysis" / "2026" / "Money_Flow_Detector.md"


class MoneyFlowPagesContractTests(unittest.TestCase):
    def test_page_is_published_by_existing_market_analysis_builder(self) -> None:
        self.assertTrue(PAGE.is_file())
        text = PAGE.read_text(encoding="utf-8")
        self.assertIn("# 💸 Money Flow Detector", text)
        self.assertIn("data/generated/public/money-flow/history.jsonl", text)
        self.assertIn("data/generated/public/money-flow/evaluation.json", text)

    def test_page_preserves_detector_safety_contract(self) -> None:
        text = PAGE.read_text(encoding="utf-8")
        for state in ("COLD", "WARMING", "INFLOW", "HOT", "OVERHEATED"):
            self.assertIn(state, text)
        self.assertIn("NO DATA", text)
        self.assertIn("0%", text)
        self.assertIn("null", text)
        self.assertIn("selection_signal", text)
        self.assertNotIn('const DEMO_', text)
        self.assertNotIn('sampleSnapshots', text)

    def test_page_uses_raw_ssot_and_no_embedded_market_snapshot(self) -> None:
        text = PAGE.read_text(encoding="utf-8")
        self.assertIn("raw.githubusercontent.com/sadouninc/Sado-Investment-Lab/main/", text)
        self.assertIn("cache: 'no-store'", text)
        self.assertNotIn('"theme:gaming"', text)
        self.assertNotIn('"sector:foods"', text)

    def test_page_reads_policy_lead_time_v2_without_reclassifying(self) -> None:
        text = PAGE.read_text(encoding="utf-8")
        self.assertIn("policy-lead-time-ai-dc-v2.json", text)
        self.assertIn("policy-lead-time-defense-drone-v2.json", text)
        self.assertIn("classification", text)
        self.assertIn("data_quality", text)
        self.assertIn("limitations", text)
        self.assertIn("Policy EvidenceはMoney Flow scoreへ混ぜず", text)
        self.assertIn("REACCELERATION_AFTER_POLICY", text)
        self.assertIn("MARKET_LEADS", text)
        self.assertNotIn("calculatePolicyClassification", text)
        self.assertNotIn("policyScore", text)

    def test_page_fail_closes_when_policy_artifact_is_missing(self) -> None:
        text = PAGE.read_text(encoding="utf-8")
        self.assertIn("Policy Lead-Time v2はまだ公開されていません", text)
        self.assertIn("DATA UNAVAILABLE", text)
        self.assertIn("response.status === 404", text)


if __name__ == "__main__":
    unittest.main()
