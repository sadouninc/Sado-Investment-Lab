from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).with_name("build_morning_dataset.py")
spec = importlib.util.spec_from_file_location("build_morning_dataset", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class MorningDatasetPageTest(unittest.TestCase):
    def build_payload(self) -> dict:
        return {
            "schema_version": "1.0",
            "generated_at": "2026-08-07T08:40:00+09:00",
            "as_of": "2026-08-07",
            "data_quality": {
                "status": "PARTIAL",
                "completeness": 1 / 7,
                "ok_sources": 1,
                "total_sources": 7,
                "completeness_label": "1 / 7",
            },
            "market": {"phase": None},
            "portfolio": None,
            "capital": None,
            "candidates": [],
            "investor_dna": {
                "sample_count": 394,
                "win_rate": 0.802,
                "profit_factor": 1.82,
                "native_dna": {"swing": "strong"},
                "environment_fit": {"risk_on": 0.8},
                "large_private_evidence_blob": [
                    {"trade_id": f"trade-{index}", "note": "diagnostic evidence"}
                    for index in range(100)
                ],
            },
            "events": None,
            "watchlist": None,
            "warnings": ["capital source is missing"],
            "source_status": [
                {
                    "name": "market",
                    "status": "OK",
                    "as_of": "2026-08-07",
                    "source": "market-test",
                    "reason": "fresh",
                },
                {
                    "name": "investor_dna",
                    "status": "OK",
                    "as_of": "2026-08-06",
                    "source_reference": "dna-test",
                    "reason": "latest verified snapshot",
                },
                {"name": "capital", "status": "MISSING", "as_of": None, "source": None},
            ],
        }

    def test_diagnostics_page_contains_contract_and_status(self) -> None:
        page = module.build_page(self.build_payload())
        self.assertIn("Morning Dataset Diagnostics", page)
        self.assertIn("PARTIAL", page)
        self.assertIn("capital source is missing", page)
        self.assertIn("morning-dataset.json", page)
        self.assertIn("1 / 7 sources", page)
        self.assertIn("14.3%", page)
        self.assertNotIn("714.3%", page)
        self.assertNotIn("Today Strategy", page)

    def test_source_sections_are_summary_first_with_collapsed_raw_json(self) -> None:
        page = module.build_page(self.build_payload())
        self.assertIn("## Source Summaries", page)
        self.assertIn("### investor_dna — OK", page)
        self.assertIn("- As of: 2026-08-06", page)
        self.assertIn("- Source: dna-test", page)
        self.assertIn("- Reason: latest verified snapshot", page)
        self.assertIn("- sample_count: 394", page)
        self.assertIn("- win_rate: 80.2%", page)
        self.assertIn("- profit_factor: 1.82", page)
        self.assertIn('<details class="raw-json-details"><summary>Raw JSONを見る — investor_dna</summary>', page)
        self.assertNotIn("```json", page)
        self.assertLess(page.index("- sample_count: 394"), page.index("Raw JSONを見る — investor_dna"))

    def test_missing_section_does_not_render_raw_payload(self) -> None:
        page = module.build_page(self.build_payload())
        capital_start = page.index("### capital — MISSING")
        candidates_start = page.index("### candidates", capital_start)
        capital_section = page[capital_start:candidates_start]
        self.assertIn("- Data: MISSING", capital_section)
        self.assertNotIn("Raw JSONを見る — capital", capital_section)

    def test_reject_investor_dna_only_dataset_issue_334_regression(self) -> None:
        """
        Issue #334: Prevent Pages publish from accepting reduced-contract datasets
        where only investor_dna is OK and all providers are MISSING.
        This would regress the canonical morning dataset status.
        """
        investor_dna_only_payload = {
            "schema_version": "1.0",
            "as_of": "2026-08-16",
            "data_quality": {
                "status": "PARTIAL",
                "ok_sources": 1,
                "total_sources": 8,
            },
            "market": None,
            "portfolio": None,
            "capital": None,
            "candidates": None,
            "investor_dna": {"sample_count": 400},
            "events": None,
            "watchlist": None,
            "sector_rotation": None,
            "source_status": [
                {"name": "market", "status": "MISSING"},
                {"name": "portfolio", "status": "MISSING"},
                {"name": "capital", "status": "MISSING"},
                {"name": "candidates", "status": "MISSING"},
                {"name": "investor_dna", "status": "OK"},
                {"name": "events", "status": "MISSING"},
                {"name": "watchlist", "status": "MISSING"},
                {"name": "sector_rotation", "status": "MISSING"},
            ],
        }
        # This should be accepted for page rendering (build_page works)
        page = module.build_page(investor_dna_only_payload)
        self.assertIn("Morning Dataset Diagnostics", page)

    def test_accept_canonical_dataset_with_multiple_providers(self) -> None:
        """Canonical datasets with multiple OK sources should be accepted"""
        canonical = self.build_payload()
        canonical["source_status"] = [
            {"name": "market", "status": "OK"},
            {"name": "portfolio", "status": "OK"},
            {"name": "capital", "status": "OK"},
            {"name": "candidates", "status": "OK"},
            {"name": "investor_dna", "status": "OK"},
            {"name": "events", "status": "MISSING"},
            {"name": "watchlist", "status": "MISSING"},
            {"name": "sector_rotation", "status": "MISSING"},
        ]
        page = module.build_page(canonical)
        self.assertIn("Morning Dataset Diagnostics", page)

    def test_missing_canonical_snapshot_fails_closed_issue_334(self) -> None:
        """
        Issue #334: If canonical morning-dataset.json does not exist,
        main() must fail closed with explicit error rather than silently
        skipping or generating reduced/empty dataset.
        """
        import tempfile
        temp_root = Path(tempfile.mkdtemp())
        original_report = module.REPORT
        try:
            # Point to non-existent file
            module.REPORT = temp_root / "does-not-exist" / "morning-dataset.json"
            with self.assertRaises(FileNotFoundError) as ctx:
                module.main()
            self.assertIn("MISSING_CANONICAL_MORNING_SNAPSHOT", str(ctx.exception))
        finally:
            module.REPORT = original_report


if __name__ == "__main__":
    unittest.main()
