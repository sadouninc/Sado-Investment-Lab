from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("company_cards.py")
SPEC = importlib.util.spec_from_file_location("company_cards", MODULE_PATH)
assert SPEC and SPEC.loader
company_cards = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = company_cards
SPEC.loader.exec_module(company_cards)


class CompanyCardContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.content = (
            "# ダイヘン（6622）\n\n"
            "Updated: 2026-08-08\n\n"
            "## AIサマリー\n\n既存研究。\n\n"
            "## 1. Research Provenance\n\nSource。\n\n"
            "## 5. Research Status / Missing Data\n\n未補完。\n"
        )
        self.summary = company_cards.summarize_company(
            "ダイヘン（6622）",
            "Infrastructure",
            Path("6622_Daihen.md"),
            self.content,
        )

    def test_summary_uses_only_source_metadata(self) -> None:
        self.assertEqual(self.summary.freshness, "2026-08-08")
        self.assertEqual(len(self.summary.sections), 3)
        self.assertIn("Research Status / Missing Data", self.summary.sections[-1])

    def test_summary_surface_uses_canonical_design_system_primitives(self) -> None:
        rendered = company_cards.render_company_page_summary(self.summary)
        for primitive in (
            "codex-page-shell",
            "codex-page-header",
            "codex-status-chip",
            "codex-summary-grid",
            "codex-summary-card",
            "codex-action-row",
        ):
            self.assertIn(primitive, rendered)
        self.assertIn("Freshness: 2026-08-08", rendered)
        self.assertIn("推測しない", rendered)
        self.assertIn("未接続値はUNAVAILABLE", rendered)
        self.assertNotIn("96 / 100", rendered)

    def test_long_research_is_progressively_disclosed_without_duplicate_h1(self) -> None:
        rendered = company_cards.render_company_detail(self.content)
        self.assertIn('<details class="codex-disclosure"', rendered)
        self.assertIn("Company Research 詳細", rendered)
        self.assertIn("## AIサマリー", rendered)
        self.assertNotIn("# ダイヘン（6622）", rendered)

    def test_missing_freshness_is_explicit_and_unavailable(self) -> None:
        summary = company_cards.summarize_company(
            "Example",
            "Test",
            Path("example.md"),
            "# Example\n\n## Thesis\n\nText\n",
        )
        rendered = company_cards.render_company_page_summary(summary)
        self.assertIn("更新日未記録", rendered)
        self.assertIn('data-state="unavailable"', rendered)

    def test_index_card_is_compact_and_category_aware(self) -> None:
        rendered = company_cards.render_company_index_card(
            "ダイヘン（6622）",
            "Infrastructure",
            "/companies/infrastructure/6622-daihen/",
            "6622_Daihen.md",
        )
        self.assertIn("codex-summary-card", rendered)
        self.assertIn("Infrastructure", rendered)
        self.assertIn("6622_Daihen.md", rendered)


if __name__ == "__main__":
    unittest.main()
