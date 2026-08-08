from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from scripts.candidate_selector import build_selector
from scripts.candidate_selector_signal_sources import (
    build_all_candidate_sources,
    load_structured_candidates,
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


class CandidateSelectorSignalSourceTests(unittest.TestCase):
    def write_source(self, path: Path, rows: list[dict]) -> None:
        path.write_text(json.dumps({"schema_version": 1, "candidates": rows}, ensure_ascii=False), encoding="utf-8")

    def test_news_theme_maps_scores_and_reasons(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "news-theme.json"
            self.write_source(
                path,
                [{
                    "security_code": "5803",
                    "company_name": "フジクラ",
                    "reason": "AIデータセンター配線需要",
                    "signals": {"investment_relevance": 90, "change_signal": 70, "theme_relevance": 95},
                    "signal_reasons": {"theme_relevance": "AIインフラ重点テーマ"},
                }],
            )
            rows, status = load_structured_candidates(path, source="NEWS_THEME")
            self.assertEqual(status["status"], "OK")
            self.assertEqual(rows[0]["candidate_sources"], ["NEWS_THEME"])
            self.assertEqual(rows[0]["signals"]["theme_relevance"], 95.0)
            self.assertEqual(rows[0]["signal_reasons"]["theme_relevance"], ["AIインフラ重点テーマ"])
            self.assertIsNone(rows[0]["signals"]["valuation_interest"])

    def test_source_rejects_unowned_signal_axis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "news-theme.json"
            self.write_source(
                path,
                [{
                    "company_name": "テスト",
                    "reason": "test",
                    "signals": {"valuation_interest": 90},
                }],
            )
            with self.assertRaises(ValueError):
                load_structured_candidates(path, source="NEWS_THEME")

    def test_missing_source_is_explicit_not_zero_score(self) -> None:
        rows, status = load_structured_candidates(Path("does-not-exist.json"), source="QUANT_VALUATION")
        self.assertEqual(rows, [])
        self.assertEqual(status["status"], "MISSING")

    def test_all_five_candidate_source_families_merge_by_security_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            companies = base / "03_Companies" / "optical"
            companies.mkdir(parents=True)
            (companies / "5803-fujikura.md").write_text(
                "# フジクラ（5803）\n\n最終更新: 2026-08-08\n",
                encoding="utf-8",
            )
            current = base / "Current_Status.md"
            current.write_text(
                "# Current Status\n\n"
                "## Portfolio\n\n> as_of: 2026-08-08\n\n- フジクラ（信用買い100株）\n\n"
                "## Current Focus\n\n> as_of: 2026-08-08\n\n- フジクラ\n",
                encoding="utf-8",
            )
            owners = base / "owner-picks.json"
            owners.write_text(json.dumps({"owner_picks": [{"security_code": "5803", "company_name": "フジクラ", "reason": "Owner Pick"}]}, ensure_ascii=False), encoding="utf-8")
            news = base / "news-theme.json"
            earnings = base / "earnings-change.json"
            quant = base / "quant-valuation.json"
            self.write_source(news, [{"security_code": "5803", "company_name": "フジクラ", "reason": "AI配線", "signals": {"theme_relevance": 95, "change_signal": 60}}])
            self.write_source(earnings, [{"security_code": "5803", "company_name": "フジクラ", "reason": "利益成長", "signals": {"change_signal": 80, "investment_relevance": 85}}])
            self.write_source(quant, [{"security_code": "5803", "company_name": "フジクラ", "reason": "valuation", "signals": {"valuation_interest": 70}}])

            rows, statuses = build_all_candidate_sources(
                current_status=current,
                research_root=base / "03_Companies",
                owner_picks=owners,
                news_theme=news,
                earnings_change=earnings,
                quant_valuation=quant,
                as_of=date(2026, 8, 9),
            )
            result = build_selector(rows, config=CONFIG, as_of=date(2026, 8, 9))
            candidate = [row for row in result["candidates"] if row.get("security_code") == "5803"][0]
            self.assertTrue(candidate["owner_pick"])
            self.assertEqual(
                candidate["candidate_sources"],
                ["EARNINGS_CHANGE", "NEWS_THEME", "OWNER_PICK", "PORTFOLIO", "QUANT_VALUATION", "RESEARCH_INDEX", "WATCHLIST"],
            )
            self.assertEqual(candidate["signals"]["change_signal"], 80.0)
            self.assertEqual(candidate["signals"]["theme_relevance"], 95.0)
            self.assertEqual(candidate["signals"]["valuation_interest"], 70.0)
            self.assertEqual(statuses["NEWS_THEME"]["status"], "OK")
            self.assertEqual(statuses["EARNINGS_CHANGE"]["status"], "OK")
            self.assertEqual(statuses["QUANT_VALUATION"]["status"], "OK")


if __name__ == "__main__":
    unittest.main()
