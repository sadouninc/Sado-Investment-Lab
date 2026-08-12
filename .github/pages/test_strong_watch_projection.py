import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECTION = ROOT / "docs" / "handoffs" / "ai-dc-strong-watch-3.md"
COMPANY_LINK = ROOT / "03_Companies" / "Infrastructure" / "AI_DC_Strong_Watch.md"
COMPANY_CARDS_PATH = ROOT / ".github" / "pages" / "company_cards.py"
SPEC = importlib.util.spec_from_file_location("strong_watch_company_cards", COMPANY_CARDS_PATH)
assert SPEC and SPEC.loader
company_cards = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = company_cards
SPEC.loader.exec_module(company_cards)


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
        self.assertIn("segment profitをe-Ribbon単独利益として扱いません", text)
        self.assertIn("Energy segment利益をAI/DC単独利益として扱いません", text)
        self.assertIn("受注先行と利益転換未確認を分離", text)

    def test_public_title_and_origin_story_make_comparison_intent_explicit(self):
        text = PROJECTION.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# データセンター電源・通信インフラ関連3社 比較レビュー"))
        self.assertIn("ジェンスン・フアン / NVIDIA", text)
        self.assertIn("先行シグナル（NVIDIA / AI投資） → 資本流入 → データセンター建設 → 電源・通信設備 → 3社の受注・増産 → 売上・利益", text)
        self.assertIn("先行シグナルが3社の業績へ実際に伝播したか", text)
        self.assertIn("SWCC (5805)", text)
        self.assertIn("富士電機 (6504)", text)
        self.assertIn("ダイヘン (6622)", text)
        self.assertNotIn("# AI/DC Strong Watch 3 — Investment Review Projection", text)

    def test_strong_watch_page_is_summary_first_and_mobile_stackable(self):
        text = PROJECTION.read_text(encoding="utf-8")
        summary = company_cards.summarize_company(
            "データセンター電源・通信インフラ関連3社 比較レビュー",
            "Infrastructure",
            COMPANY_LINK,
            text,
        )
        rendered = company_cards.render_company_page_summary(summary)
        detail = company_cards.render_company_detail(text)

        self.assertIn("Freshness: 2026-08-12", rendered)
        self.assertIn("STRONG WATCH / ENTRY REVIEW", rendered)
        self.assertIn("Valuation: 3社とも未接続 / UNKNOWN", rendered)
        for code in ("5805 SWCC", "6504 富士電機", "6622 ダイヘン"):
            self.assertIn(code, rendered)
        self.assertIn("Trigger / Risk / Checkpoint", rendered)
        self.assertNotIn("7 sections", rendered)
        self.assertNotIn('href="#company-detail"', rendered)

        self.assertNotIn('<details class="codex-disclosure"', detail)
        self.assertNotIn("| Bear EPS |", detail)
        self.assertNotIn("| 銘柄 | Why Watching |", detail)
        self.assertIn("3社ともValuation未接続 / UNKNOWN", detail)
        self.assertIn('id="watch-5805"', detail)
        self.assertIn('id="watch-6504"', detail)
        self.assertIn('id="watch-6622"', detail)


if __name__ == "__main__":
    unittest.main()
