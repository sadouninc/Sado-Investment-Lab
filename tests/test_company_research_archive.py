from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.company_research_archive import CompanyResearchArchiveError, link_company_research_evidence
from scripts.company_research_provenance import CompanyFactSpec, adapt_company_research_facts

ROOT = Path(__file__).resolve().parents[1]
DAIHEN = ROOT / "data/research/company/6622/company-research-v1.json"
SOURCE_REF = "https://www.daihen.co.jp/ir/summary_pdf/2026_0804_kessan.pdf"


class CompanyResearchArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.research = json.loads(DAIHEN.read_text(encoding="utf-8"))
        source_catalog = {
            SOURCE_REF: {
                "source_type": "IR",
                "publisher": "株式会社ダイヘン",
                "published_at": "2026-08-04T15:00:00+09:00",
                "observed_at": "2026-08-09T09:00:00+09:00",
                "canonical_ref": SOURCE_REF,
                "content_hash": None,
                "authority": "PRIMARY",
                "status": "CURRENT",
            }
        }
        projection = adapt_company_research_facts(
            cls.research,
            source_catalog=source_catalog,
            fact_specs=[CompanyFactSpec(
                path="facts.latest_financials.revenue_million_jpy",
                field="revenue",
                period="FY2027-Q1",
                unit="JPY_MN",
                source_ref=SOURCE_REF,
                as_of="2026-08-04",
            )],
        )
        cls.source_id = projection["ledger"]["sources"][0]["source_id"]
        cls.source_ids = {SOURCE_REF: cls.source_id}

    def archived_record(self) -> dict:
        return {
            "source_id": self.source_id,
            "access_status": "ARCHIVED",
            "archive_ref": "https://github.com/sadouninc/Sado-Investment-Lab/releases/download/evidence/test.pdf",
            "ingress_ref": None,
            "original_url": SOURCE_REF,
            "sha256": "1" * 64,
            "original_filename": "2026_0804_kessan.pdf",
            "received_at": "2026-08-13T01:00:00+09:00",
            "received_by": "SADO",
        }

    def test_archived_source_becomes_retrievable_research_evidence_link(self) -> None:
        result = link_company_research_evidence(
            self.research,
            source_ids_by_ref=self.source_ids,
            archive_records=[self.archived_record()],
        )
        link = next(item for item in result["evidence_links"] if item["source_ref"] == SOURCE_REF)
        self.assertEqual("ARCHIVED", link["access_status"])
        self.assertTrue(link["archive_ref"].startswith("https://github.com/"))
        self.assertEqual(self.source_id, link["source_id"])

    def test_missing_archive_record_stays_url_only(self) -> None:
        result = link_company_research_evidence(
            self.research,
            source_ids_by_ref=self.source_ids,
            archive_records=[],
        )
        link = next(item for item in result["evidence_links"] if item["source_ref"] == SOURCE_REF)
        self.assertEqual("URL_ONLY", link["access_status"])
        self.assertIsNone(link["archive_ref"])

    def test_missing_source_identity_fails_closed(self) -> None:
        with self.assertRaisesRegex(CompanyResearchArchiveError, "source_id unavailable"):
            link_company_research_evidence(
                self.research,
                source_ids_by_ref={},
                archive_records=[],
            )

    def test_archive_identity_must_match_144_source_id(self) -> None:
        wrong = self.archived_record()
        wrong["source_id"] = "source:ffffffffffffffffffffffff"
        result = link_company_research_evidence(
            self.research,
            source_ids_by_ref=self.source_ids,
            archive_records=[wrong],
        )
        link = next(item for item in result["evidence_links"] if item["source_ref"] == SOURCE_REF)
        self.assertEqual("URL_ONLY", link["access_status"])
        self.assertIsNone(link["archive_ref"])


if __name__ == "__main__":
    unittest.main()
