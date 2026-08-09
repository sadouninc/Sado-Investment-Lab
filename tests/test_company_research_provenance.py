from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts.company_research_provenance import (
    CompanyFactSpec,
    CompanyResearchProvenanceError,
    adapt_company_research_facts,
)

ROOT = Path(__file__).resolve().parents[1]
DAIHEN = ROOT / "data/research/company/6622/company-research-v1.json"
SOURCE_REF = "https://www.daihen.co.jp/ir/summary_pdf/2026_0804_kessan.pdf"


class CompanyResearchProvenanceAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.research = json.loads(DAIHEN.read_text(encoding="utf-8"))
        cls.source_catalog = {
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
        cls.specs = [
            CompanyFactSpec(
                path="facts.latest_financials.orders_million_jpy",
                field="orders",
                period="FY2027-Q1",
                unit="JPY_MN",
                source_ref=SOURCE_REF,
                as_of="2026-08-04",
                locator="Q1 summary / consolidated results",
            ),
            CompanyFactSpec(
                path="facts.latest_financials.revenue_million_jpy",
                field="revenue",
                period="FY2027-Q1",
                unit="JPY_MN",
                source_ref=SOURCE_REF,
                as_of="2026-08-04",
                locator="Q1 summary / consolidated results",
            ),
            CompanyFactSpec(
                path="facts.latest_financials.operating_profit_million_jpy",
                field="operating_profit",
                period="FY2027-Q1",
                unit="JPY_MN",
                source_ref=SOURCE_REF,
                as_of="2026-08-04",
                locator="Q1 summary / consolidated results",
            ),
            CompanyFactSpec(
                path="facts.latest_financials.net_income_attributable_million_jpy",
                field="net_income_attributable",
                period="FY2027-Q1",
                unit="JPY_MN",
                source_ref=SOURCE_REF,
                as_of="2026-08-04",
                locator="Q1 summary / consolidated results",
            ),
        ]

    def test_daihen_current_research_maps_to_explicit_fact_refs(self) -> None:
        result = adapt_company_research_facts(
            self.research,
            source_catalog=self.source_catalog,
            fact_specs=self.specs,
        )
        self.assertEqual(result["security_code"], "6622")
        self.assertEqual(len(result["ledger"]["sources"]), 1)
        self.assertEqual(len(result["ledger"]["facts"]), 4)
        values = {fact["field"]: fact["value"] for fact in result["ledger"]["facts"]}
        self.assertEqual(values["orders"], 86096)
        self.assertEqual(values["revenue"], 55507)
        self.assertEqual(values["operating_profit"], 4079)
        self.assertEqual(values["net_income_attributable"], 2779)
        self.assertTrue(all(ref["fact_id"].startswith("fact:") for ref in result["fact_refs"]))

    def test_rerun_is_deterministic_and_does_not_mutate_research(self) -> None:
        original = copy.deepcopy(self.research)
        first = adapt_company_research_facts(
            self.research,
            source_catalog=self.source_catalog,
            fact_specs=self.specs,
        )
        second = adapt_company_research_facts(
            self.research,
            source_catalog=self.source_catalog,
            fact_specs=self.specs,
        )
        self.assertEqual(first, second)
        self.assertEqual(self.research, original)

    def test_missing_source_metadata_fails_closed(self) -> None:
        with self.assertRaisesRegex(CompanyResearchProvenanceError, "source metadata unavailable"):
            adapt_company_research_facts(
                self.research,
                source_catalog={},
                fact_specs=self.specs,
            )

    def test_source_not_declared_by_research_is_rejected(self) -> None:
        bad_spec = CompanyFactSpec(
            path="facts.latest_financials.revenue_million_jpy",
            field="revenue",
            period="FY2027-Q1",
            unit="JPY_MN",
            source_ref="https://example.test/not-declared.pdf",
            as_of="2026-08-04",
        )
        with self.assertRaisesRegex(CompanyResearchProvenanceError, "not declared"):
            adapt_company_research_facts(
                self.research,
                source_catalog={bad_spec.source_ref: self.source_catalog[SOURCE_REF]},
                fact_specs=[bad_spec],
            )

    def test_missing_fact_path_is_not_imputed(self) -> None:
        bad_spec = CompanyFactSpec(
            path="facts.latest_financials.fabricated_metric",
            field="fabricated_metric",
            period="FY2027-Q1",
            unit="JPY_MN",
            source_ref=SOURCE_REF,
            as_of="2026-08-04",
        )
        with self.assertRaisesRegex(CompanyResearchProvenanceError, "fact path is unavailable"):
            adapt_company_research_facts(
                self.research,
                source_catalog=self.source_catalog,
                fact_specs=[bad_spec],
            )

    def test_incomplete_authority_metadata_is_not_inferred_from_url(self) -> None:
        incomplete = {SOURCE_REF: {"source_type": "IR", "canonical_ref": SOURCE_REF}}
        with self.assertRaisesRegex(CompanyResearchProvenanceError, "invalid source metadata"):
            adapt_company_research_facts(
                self.research,
                source_catalog=incomplete,
                fact_specs=[self.specs[0]],
            )

    def test_no_specs_does_not_claim_provenance_completion(self) -> None:
        with self.assertRaisesRegex(CompanyResearchProvenanceError, "at least one explicit fact spec"):
            adapt_company_research_facts(
                self.research,
                source_catalog=self.source_catalog,
                fact_specs=[],
            )


if __name__ == "__main__":
    unittest.main()
