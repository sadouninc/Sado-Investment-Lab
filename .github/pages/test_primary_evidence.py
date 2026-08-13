from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("build_primary_evidence.py")
SPEC = importlib.util.spec_from_file_location("build_primary_evidence", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PrimaryEvidencePagesTests(unittest.TestCase):
    def test_url_only_row_is_visible_without_claiming_archive(self) -> None:
        rows = MODULE.source_rows(
            [],
            {
                "6622": {
                    "security_code": "6622",
                    "company_name": "株式会社ダイヘン",
                    "research_as_of": "2026-08-09",
                    "source_refs": ["https://example.test/results.pdf"],
                }
            },
        )
        self.assertEqual("URL_ONLY", rows[0]["access_status"])
        self.assertIsNone(rows[0]["archive_ref"])
        page = MODULE.render_library(rows)
        self.assertIn("`URL_ONLY`", page)
        self.assertNotIn("[open]", page)

    def test_archived_row_exposes_archive_and_digest(self) -> None:
        rows = MODULE.source_rows(
            [{
                "source_id": "source:111111111111111111111111",
                "access_status": "ARCHIVED",
                "archive_ref": "https://github.com/sadouninc/Sado-Investment-Lab/releases/download/evidence/test.pdf",
                "original_url": "https://example.test/results.pdf",
                "sha256": "a" * 64,
                "original_filename": "results.pdf",
            }],
            {
                "6622": {
                    "security_code": "6622",
                    "company_name": "株式会社ダイヘン",
                    "research_as_of": "2026-08-09",
                    "source_refs": ["https://example.test/results.pdf"],
                }
            },
        )
        page = MODULE.render_library(rows)
        self.assertIn("`ARCHIVED`", page)
        self.assertIn("[open](https://github.com/", page)
        self.assertIn("aaaaaaaaaaaa…", page)

    def test_company_index_gets_sources_navigation(self) -> None:
        original_site = MODULE.SITE
        try:
            with tempfile.TemporaryDirectory() as tmp:
                MODULE.SITE = Path(tmp)
                company = MODULE.SITE / "companies" / "index.md"
                company.parent.mkdir(parents=True)
                company.write_text("# Companies\n", encoding="utf-8")
                MODULE.append_company_source_link()
                content = company.read_text(encoding="utf-8")
                self.assertIn("## Primary Evidence", content)
                self.assertIn("/sources/", content)
                MODULE.append_company_source_link()
                self.assertEqual(content, company.read_text(encoding="utf-8"))
        finally:
            MODULE.SITE = original_site


if __name__ == "__main__":
    unittest.main()
