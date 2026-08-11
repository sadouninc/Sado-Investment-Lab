from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "04_Market" / "Analysis" / "2026" / "Sector_Rotation.md"


class SectorRotationPagesContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = PAGE.read_text(encoding="utf-8")

    def test_reads_canonical_sector_history_separately(self) -> None:
        self.assertIn("data/generated/public/money-flow/sector-history.jsonl", self.text)
        self.assertIn("row.kind === 'SECTOR'", self.text)
        self.assertNotIn("data/generated/public/money-flow/history.jsonl", self.text)

    def test_previous_to_current_transition_is_visible(self) -> None:
        self.assertIn("previous_state", self.text)
        self.assertIn("COLD->WARMING", self.text)
        self.assertIn("WARMING->INFLOW", self.text)
        self.assertIn("前回 → 現在", self.text)

    def test_missing_axes_are_not_zero_filled(self) -> None:
        self.assertIn("value == null", self.text)
        self.assertIn("? '—'", self.text)
        self.assertIn("Breadth —", self.text)
        self.assertIn("0へ変換しません", self.text)

    def test_latest_confirmed_as_of_only_and_no_demo_signal(self) -> None:
        self.assertIn("String(row.as_of) === newest", self.text)
        self.assertIn("Latest confirmed", self.text)
        self.assertIn("NO DATA", self.text)
        self.assertNotIn("sampleSnapshots", self.text)
        self.assertNotIn("DEMO_", self.text)

    def test_page_is_read_only_not_trade_advice(self) -> None:
        self.assertIn("BUY / SELLを生成しません", self.text)
        self.assertIn("Detector thresholdやscoreをブラウザ側で再計算せず", self.text)


if __name__ == "__main__":
    unittest.main()
