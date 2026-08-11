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


if __name__ == "__main__":
    unittest.main()
