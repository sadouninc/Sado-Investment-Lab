import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECTION = ROOT / "docs" / "handoffs" / "ai-dc-strong-watch-3.md"
COMPANY_LINK = ROOT / "03_Companies" / "Infrastructure" / "AI_DC_Strong_Watch.md"


class StrongWatchProjectionPublicationContractTest(unittest.TestCase):
    def test_company_projection_reuses_canonical_handoff(self):
        self.assertTrue(COMPANY_LINK.is_symlink())
        self.assertEqual(COMPANY_LINK.resolve(), PROJECTION.resolve())
        self.assertIn(COMPANY_LINK, list((ROOT / "03_Companies").glob("*/*.md")))

    def test_projection_preserves_research_and_fail_closed_contract(self):
        text = PROJECTION.read_text(encoding="utf-8")
        for code in ("5805 SWCC", "6504 富士電機", "6622 ダイヘン"):
            self.assertIn(code, text)
        self.assertIn("Demand → Capacity → Revenue → Segment Profit = CONFIRMED", text)
        self.assertIn("Demand → Order → Capacity → Revenue → Profit = STRONG / CONFIRMED broadly", text)
        self.assertIn("Revenue/Profit conversion = PENDING", text)
        self.assertIn("Forward PER", text)
        self.assertIn("`UNKNOWN`", text)
        self.assertIn("BUY / SELL / 買値を生成しません", text)
        self.assertIn("SWCCのsegment profit", text)
        self.assertIn("Energy segment利益をAI/DC単独利益として扱いません", text)
        self.assertIn("受注先行と利益転換未確認を分離", text)


if __name__ == "__main__":
    unittest.main()
