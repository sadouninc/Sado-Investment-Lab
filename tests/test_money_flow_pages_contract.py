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


if __name__ == "__main__":
    unittest.main()
