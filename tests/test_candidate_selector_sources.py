from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from scripts.candidate_selector import build_selector
from scripts.candidate_selector_sources import (
    build_source_candidates,
    load_owner_picks,
    normalize_name,
    research_index_candidates,
    research_name_map,
)


CONFIG = {
    "schema_version": 1,
    "freshness_days": 90,
    "major_change_threshold": 80,
    "weights": {
        "investment_relevance": 0.30,
        "change_signal": 0.25,
        "research_gap": 0.20,
        "theme_relevance": 0.15,
        "valuation_interest": 0.10,
    },
}


class CandidateSelectorSourceTests(unittest.TestCase):
    def test_research_index_extracts_code_name_and_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "03_Companies" / "semiconductor"
            root.mkdir(parents=True)
            (root / "4063-shinetsu.md").write_text(
                "# 信越化学工業（4063）\n\n最終更新: 2026-08-08\n",
                encoding="utf-8",
            )
            rows = research_index_candidates(Path(tmp) / "03_Companies")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["security_code"], "4063")
            self.assertEqual(rows[0]["company_name"], "信越化学工業")
            self.assertEqual(rows[0]["research_status"], "CURRENT")
            self.assertEqual(rows[0]["last_researched_at"], "2026-08-08")

    def test_year_prefixed_theme_note_is_not_a_security_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "03_Companies" / "themes"
            root.mkdir(parents=True)
            (root / "2026_data_center_comparison.md").write_text(
                "# データセンター電源通信インフラ比較\n"
                "更新日: 2026-11-20\n"
                "比較対象 4063 / 6622\n",
                encoding="utf-8",
            )
            rows = research_index_candidates(Path(tmp) / "03_Companies")
            self.assertEqual(1, len(rows))
            self.assertIsNone(rows[0]["security_code"])
            self.assertEqual("データセンター電源通信インフラ比較", rows[0]["company_name"])

    def test_explicit_heading_ticker_is_not_suppressed_by_year_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "03_Companies" / "companies"
            root.mkdir(parents=True)
            (root / "2026_report.md").write_text(
                "# サンプル企業（2026）\n最終更新: 2026-11-20\n",
                encoding="utf-8",
            )
            rows = research_index_candidates(Path(tmp) / "03_Companies")
            self.assertEqual("2026", rows[0]["security_code"])

    def test_legitimate_20xx_filename_codes_are_not_suppressed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "03_Companies" / "food"
            root.mkdir(parents=True)
            for code in ("2002", "2060"):
                (root / f"{code}-company.md").write_text(
                    f"# Company {code}\n最終更新: 2026-11-23\n",
                    encoding="utf-8",
                )
            rows = research_index_candidates(Path(tmp) / "03_Companies")
            self.assertEqual({"2002", "2060"}, {row["security_code"] for row in rows})

    def test_parenthesized_year_in_theme_heading_is_not_security_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "03_Companies" / "research"
            root.mkdir(parents=True)
            (root / "market_research.md").write_text(
                "# データセンター比較（2026）\n最終更新: 2026-11-23\n",
                encoding="utf-8",
            )
            rows = research_index_candidates(Path(tmp) / "03_Companies")
            self.assertEqual(1, len(rows))
            self.assertIsNone(rows[0]["security_code"])

    def test_ticker_filename_in_theme_directory_is_not_company(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "03_Companies" / "themes"
            root.mkdir(parents=True)
            (root / "2060_theme_notes.md").write_text(
                "# 食料産業の比較\n最終更新: 2026-11-23\n",
                encoding="utf-8",
            )
            rows = research_index_candidates(Path(tmp) / "03_Companies")
            self.assertIsNone(rows[0]["security_code"])

    def test_research_without_freshness_is_conservatively_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "03_Companies" / "power"
            root.mkdir(parents=True)
            (root / "6622-daihen.md").write_text("# ダイヘン（6622）\n", encoding="utf-8")
            rows = research_index_candidates(Path(tmp) / "03_Companies")
            self.assertEqual(rows[0]["research_status"], "STALE")
            self.assertIsNone(rows[0]["last_researched_at"])

    def test_name_map_uses_nfkc_and_does_not_guess_ambiguous_codes(self) -> None:
        rows = [
            {"company_name": "ＡＢＣ", "security_code": "1111"},
            {"company_name": "ABC", "security_code": "2222"},
        ]
        self.assertEqual(normalize_name("ＡＢＣ"), "ABC")
        self.assertNotIn("ABC", research_name_map(rows))

    def test_owner_pick_is_explicit_structured_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "owner-picks.json"
            path.write_text(
                json.dumps({"owner_picks": [{"security_code": "5803", "company_name": "フジクラ", "reason": "比較したい"}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            rows, status = load_owner_picks(path)
            self.assertTrue(rows[0]["owner_pick"])
            self.assertEqual(rows[0]["candidate_sources"], ["OWNER_PICK"])
            self.assertEqual(status["status"], "OK")

    def test_stale_portfolio_reason_names_historical_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            current = base / "Current_Status.md"
            current.write_text(
                "# Current Status\n\n"
                "## Portfolio\n\n"
                "> as_of: 2026-08-08\n\n"
                "- 信越化学工業（信用買い100株）\n",
                encoding="utf-8",
            )
            rows, statuses = build_source_candidates(
                current_status=current,
                research_root=base / "not-found",
                owner_picks=None,
                as_of=date(2026, 11, 28),
            )
            self.assertEqual("STALE", statuses["PORTFOLIO"]["status"])
            self.assertEqual("2026-08-08", statuses["PORTFOLIO"]["as_of"])
            self.assertEqual(1, len(rows))
            reason = rows[0]["source_reasons"]["PORTFOLIO"][0]
            self.assertIn("Portfolio snapshot holding", reason)
            self.assertIn("as_of=2026-08-08", reason)
            self.assertIn("source_status=STALE", reason)
            self.assertIn("NOT current-position verification", reason)
            self.assertIn("信用買い100株", reason)
            self.assertNotIn("Current portfolio holding", reason)

    def test_repository_sources_merge_by_resolved_security_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            companies = base / "03_Companies" / "semiconductor"
            companies.mkdir(parents=True)
            (companies / "4063-shinetsu.md").write_text(
                "# 信越化学工業（4063）\n\n最終更新: 2026-08-08\n",
                encoding="utf-8",
            )
            current = base / "Current_Status.md"
            current.write_text(
                "# Current Status\n\n"
                "## Portfolio\n\n"
                "> as_of: 2026-08-08\n\n"
                "- 信越化学工業（信用買い100株）\n\n"
                "## Current Focus\n\n"
                "> as_of: 2026-08-08\n\n"
                "- 信越化学工業\n",
                encoding="utf-8",
            )
            owners = base / "owner-picks.json"
            owners.write_text('{"owner_picks": []}\n', encoding="utf-8")
            rows, statuses = build_source_candidates(
                current_status=current,
                research_root=base / "03_Companies",
                owner_picks=owners,
                as_of=date(2026, 8, 9),
            )
            result = build_selector(rows, config=CONFIG, as_of=date(2026, 8, 9))
            candidates = [row for row in result["candidates"] if row.get("security_code") == "4063"]
            self.assertEqual(len(candidates), 1)
            self.assertEqual(
                candidates[0]["candidate_sources"],
                ["PORTFOLIO", "RESEARCH_INDEX", "WATCHLIST"],
            )
            self.assertEqual(statuses["PORTFOLIO"]["status"], "OK")
            self.assertEqual(statuses["WATCHLIST"]["status"], "OK")
            self.assertIsNone(candidates[0]["total_priority"])


if __name__ == "__main__":
    unittest.main()
