import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SONY_COMPANY_LINK = ROOT / "03_Companies" / "AI" / "6758_Sony.md"
SONY_HANDOFF = ROOT / "docs" / "handoffs" / "sony-6758-investment-review.md"


class SonyInvestmentReviewPublicationContractTest(unittest.TestCase):
    def test_company_source_reuses_canonical_handoff_without_copying_research(self):
        self.assertTrue(SONY_COMPANY_LINK.is_symlink())
        self.assertEqual(SONY_COMPANY_LINK.resolve(), SONY_HANDOFF.resolve())
        self.assertIn(SONY_COMPANY_LINK, list((ROOT / "03_Companies").glob("*/*.md")))

    def test_entry_review_and_fail_closed_valuation_survive_company_projection(self):
        text = SONY_COMPANY_LINK.read_text(encoding="utf-8")
        self.assertIn("STRONG WATCH / ENTRY REVIEW", text)
        self.assertIn("Bear EPS: `UNKNOWN`", text)
        self.assertIn("Base EPS: `UNKNOWN`", text)
        self.assertIn("Bull EPS: `UNKNOWN`", text)
        self.assertIn("Forward PER: `UNKNOWN`", text)
        self.assertIn("must not independently generate BUY/SELL", text)


if __name__ == "__main__":
    unittest.main()
