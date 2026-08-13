from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.company_research_provenance import CompanyFactSpec, adapt_company_research_facts
from scripts.primary_evidence_coverage_audit import audit_primary_evidence_coverage

ROOT = Path(__file__).resolve().parents[1]
DAIHEN = ROOT / "data/research/company/6622/company-research-v1.json"
DAIHEN_SOURCE = "https://www.daihen.co.jp/ir/summary_pdf/2026_0804_kessan.pdf"
TARGETS = [
    {"security_code": "3110", "company_name": "日東紡"},
    {"security_code": "6622", "company_name": "ダイヘン"},
    {"security_code": "6504", "company_name": "富士電機"},
    {"security_code": "5805", "company_name": "SWCC"},
    {"security_code": "6758", "company_name": "ソニーグループ"},
    {"security_code": "6376", "company_name": "日機装"},
]


class CoverageAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.daihen = json.loads(DAIHEN.read_text(encoding="utf-8"))
        source_catalog = {
            DAIHEN_SOURCE: {
                "source_type": "IR",
                "publisher": "株式会社ダイヘン",
                "published_at": "2026-08-04T15:00:00+09:00",
                "observed_at": "2026-08-09T09:00:00+09:00",
                "canonical_ref": DAIHEN_SOURCE,
                "content_hash": None,
                "authority": "PRIMARY",
                "status": "CURRENT",
            }
        }
        projection = adapt_company_research_facts(
            cls.daihen,
            source_catalog=source_catalog,
            fact_specs=[CompanyFactSpec(
                path="facts.latest_financials.revenue_million_jpy",
                field="revenue",
                period="FY2027-Q1",
                unit="JPY_MN",
                source_ref=DAIHEN_SOURCE,
                as_of="2026-08-04",
            )],
        )
        cls.source_id = projection["ledger"]["sources"][0]["source_id"]

    def row(self, report: dict, code: str) -> dict:
        return next(row for row in report["targets"] if row["security_code"] == code)

    def test_initial_targets_do_not_impute_missing_research(self) -> None:
        report = audit_primary_evidence_coverage(
            targets=TARGETS,
            research_catalog={"6622": self.daihen},
            source_ids_by_ref={DAIHEN_SOURCE: self.source_id},
            archive_records=[],
        )
        self.assertEqual("URL_ONLY", self.row(report, "6622")["coverage_state"])
        for code in ("3110", "6504", "5805", "6758", "6376"):
            self.assertEqual("RESEARCH_MISSING", self.row(report, code)["coverage_state"])

    def test_archived_daihen_becomes_complete(self) -> None:
        report = audit_primary_evidence_coverage(
            targets=TARGETS,
            research_catalog={"6622": self.daihen},
            source_ids_by_ref={DAIHEN_SOURCE: self.source_id},
            archive_records=[{
                "source_id": self.source_id,
                "access_status": "ARCHIVED",
                "archive_ref": "https://github.com/sadouninc/Sado-Investment-Lab/releases/download/evidence/test.pdf",
                "ingress_ref": None,
                "original_url": DAIHEN_SOURCE,
                "sha256": "a" * 64,
                "original_filename": "2026_0804_kessan.pdf",
                "received_at": "2026-08-13T01:00:00+09:00",
                "received_by": "SADO",
            }],
        )
        row = self.row(report, "6622")
        self.assertEqual("ARCHIVED", row["coverage_state"])
        self.assertEqual(1, row["archived_count"])

    def test_missing_144_source_identity_is_explicit(self) -> None:
        report = audit_primary_evidence_coverage(
            targets=TARGETS,
            research_catalog={"6622": self.daihen},
            source_ids_by_ref={},
            archive_records=[],
        )
        self.assertEqual("SOURCE_ID_MISSING", self.row(report, "6622")["coverage_state"])

    def test_explicit_recovery_state_is_preserved(self) -> None:
        report = audit_primary_evidence_coverage(
            targets=TARGETS,
            research_catalog={"6622": self.daihen},
            source_ids_by_ref={DAIHEN_SOURCE: self.source_id},
            archive_records=[{
                "source_id": self.source_id,
                "access_status": "NEEDS_RECOVERY",
                "archive_ref": None,
                "ingress_ref": "chat-upload:missing",
                "original_url": DAIHEN_SOURCE,
                "sha256": None,
                "original_filename": "2026_0804_kessan.pdf",
                "received_at": "2026-08-09T09:00:00+09:00",
                "received_by": "ASAHI",
            }],
        )
        self.assertEqual("NEEDS_RECOVERY", self.row(report, "6622")["coverage_state"])


if __name__ == "__main__":
    unittest.main()
