from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


PAGES = Path(__file__).resolve().parent
if str(PAGES) not in sys.path:
    sys.path.insert(0, str(PAGES))

MODULE_PATH = PAGES / "build_architecture.py"
SPEC = importlib.util.spec_from_file_location("build_architecture_company_test", MODULE_PATH)
assert SPEC and SPEC.loader
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class CompanyCardIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.original_company_site = builder.COMPANY_SITE
        builder.COMPANY_SITE = Path(self.temp_dir.name) / "companies"
        self.addCleanup(setattr, builder, "COMPANY_SITE", self.original_company_site)

    def test_publish_company_cards_overwrites_legacy_long_form_output(self) -> None:
        builder.publish_company_cards()

        dai = builder.COMPANY_SITE / "infrastructure" / "6622-daihen" / "index.md"
        index = builder.COMPANY_SITE / "index.md"
        self.assertTrue(dai.is_file())
        self.assertTrue(index.is_file())

        page = dai.read_text(encoding="utf-8")
        landing = index.read_text(encoding="utf-8")

        self.assertIn("company-decision-surface", page)
        self.assertIn("Freshness: 2026-08-08", page)
        self.assertIn("Company Research 詳細", page)
        self.assertIn("Research Status / Missing Data", page)
        self.assertIn("未接続値はUNAVAILABLE", page)
        self.assertNotIn("<p class=\"breadcrumb\"", page)
        self.assertIn("codex-summary-grid", landing)
        self.assertIn("6622_Daihen.md", landing)

    def test_existing_canonical_company_score_is_not_promoted_into_generated_summary(self) -> None:
        builder.publish_company_cards()
        nittobo = builder.COMPANY_SITE / "semiconductor" / "3110-nittobo" / "index.md"
        page = nittobo.read_text(encoding="utf-8")
        summary, _, detail = page.partition('<details class="codex-disclosure"')

        self.assertIn("推測しない", summary)
        self.assertNotIn("96 / 100", summary)
        self.assertIn("96 / 100", detail)


if __name__ == "__main__":
    unittest.main()
