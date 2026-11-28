"""#949: stale/unscored candidates must never be shown as a verified focus pick.

担当: ♦️ソラ
"""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ai_morning_analyst import candidate_focus_verification  # noqa: E402

MODULE_PATH = ROOT / ".github" / "pages" / "build_ai_morning_reports.py"
SPEC = importlib.util.spec_from_file_location("build_ai_morning_reports_949", MODULE_PATH)
assert SPEC and SPEC.loader
PAGES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PAGES)

LABEL = "今日の検証済み注目銘柄は未確定"


def _row(code: str, name: str, *, rank=None, priority=None, status="STALE", sources=("RESEARCH_INDEX",), last="2026-08-02"):
    return {
        "security_code": code,
        "company_name": name,
        "rank": rank,
        "status": status,
        "total_priority": priority,
        "owner_pick": "OWNER_PICK" in sources,
        "candidate_sources": list(sources),
        "selection_reason": "",
        "last_researched_at": last,
    }


def _dataset(rows, *, status="OK", as_of="2026-11-28"):
    return {
        "as_of": as_of,
        "source_status": [{"name": "candidates", "status": status, "as_of": as_of}],
        "candidates": rows,
    }


# The 2026-11-20 shape the Owner saw: six rows, all STALE, no priority.
ALL_STALE = [
    _row("3110", "日東紡", last="2026-08-06"),
    _row("4063", "信越化学工業", sources=("PORTFOLIO", "RESEARCH_INDEX")),
    _row("6232", "ACSL", sources=("OWNER_PICK", "RESEARCH_INDEX"), last="2026-08-13"),
    _row("6622", "ダイヘン", sources=("PORTFOLIO", "RESEARCH_INDEX"), last="2026-08-08"),
    _row("6758", "Sony Group", last="2026-07-31"),
    _row("9432", "NTT", sources=("PORTFOLIO",), last=None),
]


class CandidateFocusVerificationTests(unittest.TestCase):
    def test_six_stale_null_priority_candidates_are_not_verified(self):
        focus = candidate_focus_verification(_dataset(ALL_STALE, status="PARTIAL"))
        self.assertFalse(focus["verified_focus_available"])
        self.assertEqual(focus["candidate_count"], 6)
        self.assertEqual(focus["scored_count"], 0)

    def test_ok_source_with_only_unscored_rows_is_not_verified(self):
        # "Daily generation OK" must not be read as "analysis targets are fresh".
        focus = candidate_focus_verification(_dataset(ALL_STALE, status="OK"))
        self.assertFalse(focus["verified_focus_available"])
        self.assertEqual(focus["reason"], "優先度を算出できた候補がありません")

    def test_old_portfolio_and_old_research_shinetsu_is_not_verified(self):
        row = _row("4063", "信越化学工業", rank=1, priority=72.5, status="STALE", sources=("PORTFOLIO", "RESEARCH_INDEX"))
        focus = candidate_focus_verification(_dataset([row]))
        self.assertFalse(focus["verified_focus_available"])
        self.assertEqual(focus["scored_count"], 1)
        self.assertEqual(focus["current_scored_count"], 0)

    def test_fresh_owner_pick_alone_is_verified(self):
        pick = _row("6232", "ACSL", rank=1, priority=60, status="CURRENT", sources=("OWNER_PICK",), last="2026-11-27")
        focus = candidate_focus_verification(_dataset([pick]))
        self.assertTrue(focus["verified_focus_available"])
        self.assertIsNone(focus["reason"])

    def test_mixed_fresh_and_stale_is_verified_by_the_fresh_scored_row_only(self):
        rows = [
            _row("6622", "ダイヘン", rank=1, priority=80, status="CURRENT", last="2026-11-27"),
            _row("4063", "信越化学工業", rank=2, priority=70, status="STALE"),
            _row("3110", "日東紡"),
        ]
        focus = candidate_focus_verification(_dataset(rows))
        self.assertTrue(focus["verified_focus_available"])
        self.assertEqual(focus["current_scored_count"], 1)

    def test_stale_source_blocks_even_a_current_scored_row(self):
        row = _row("6622", "ダイヘン", rank=1, priority=80, status="CURRENT")
        focus = candidate_focus_verification(_dataset([row], status="STALE"))
        self.assertFalse(focus["verified_focus_available"])
        self.assertIn("STALE", focus["reason"])

    def test_zero_candidates_or_missing_data_is_not_verified(self):
        for dataset in (_dataset([], status="MISSING"), {"as_of": "2026-11-28"}, {"candidates": "broken"}):
            focus = candidate_focus_verification(dataset)
            self.assertFalse(focus["verified_focus_available"])
            self.assertEqual(focus["candidate_count"], 0)

    def test_non_finite_or_boolean_priority_is_not_a_score(self):
        rows = [
            _row("6622", "ダイヘン", rank=1, priority=math.nan, status="CURRENT"),
            _row("6758", "Sony Group", rank=2, priority=True, status="CURRENT"),
        ]
        self.assertFalse(candidate_focus_verification(_dataset(rows))["verified_focus_available"])

    def test_focus_record_is_json_serialisable_for_diagnostics(self):
        json.dumps(candidate_focus_verification(_dataset(ALL_STALE)), ensure_ascii=False)


REPORT = """---
dataset_status: PARTIAL
---

# AI Morning Report

## 市場概況
- 半導体は横ばい。

## 今日の戦略
- 様子見。

## 注目銘柄
- 4063 信越化学工業
  - 根拠: PORTFOLIO/RESEARCH_INDEXに存在（STALE）

## 次回確認時に見る条件
- 決算日程。
"""


class ReportFocusRenderingTests(unittest.TestCase):
    def _build(self, diagnostics_by_day):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_dir, diag_dir, site = root / "reports", root / "diag", root / "site"
            report_dir.mkdir()
            diag_dir.mkdir()
            for day, diagnostics in diagnostics_by_day.items():
                (report_dir / f"{day}.md").write_text(REPORT, encoding="utf-8")
                if diagnostics is not None:
                    (diag_dir / f"{day}.json").write_text(json.dumps(diagnostics), encoding="utf-8")
            saved = PAGES.REPORT_DIR, PAGES.DIAG_DIR, PAGES.SITE
            try:
                PAGES.REPORT_DIR, PAGES.DIAG_DIR, PAGES.SITE = report_dir, diag_dir, site
                PAGES.build()
            finally:
                PAGES.REPORT_DIR, PAGES.DIAG_DIR, PAGES.SITE = saved
            index = (site / "reports" / "morning" / "index.md").read_text(encoding="utf-8")
            pages = {
                day: (site / "reports" / "morning" / day / "index.md").read_text(encoding="utf-8")
                for day in diagnostics_by_day
            }
            return index, pages

    def test_history_cards_never_present_unverified_shinetsu_as_focus(self):
        stale = {"dataset_status": "PARTIAL", "candidate_focus": candidate_focus_verification(_dataset(ALL_STALE))}
        index, _ = self._build({"2026-11-19": stale, "2026-11-18": None, "2026-11-17": {"dataset_status": "OK"}})
        self.assertNotIn("注目: 4063", index)
        self.assertEqual(index.count(f"注目: {LABEL}（AI候補メモ・未検証: 4063 信越化学工業）"), 3)

    def test_verified_focus_keeps_the_ai_watch_line(self):
        fresh = _row("6622", "ダイヘン", rank=1, priority=80, status="CURRENT", last="2026-11-27")
        diagnostics = {"dataset_status": "OK", "candidate_focus": candidate_focus_verification(_dataset([fresh]))}
        index, pages = self._build({"2026-11-28": diagnostics})
        self.assertIn("注目: 4063 信越化学工業", index)
        self.assertNotIn(LABEL, index)
        self.assertNotIn(LABEL, pages["2026-11-28"])

    def test_detail_page_notice_preserves_historical_report_text(self):
        stale = {"dataset_status": "PARTIAL", "candidate_focus": candidate_focus_verification(_dataset(ALL_STALE))}
        _, pages = self._build({"2026-11-19": stale, "2026-11-18": None})
        for page in pages.values():
            notice = page.index(LABEL)
            self.assertLess(page.index("## 注目銘柄"), notice)
            self.assertLess(notice, page.index("- 4063 信越化学工業"))
            # Original AI text is kept verbatim (history is not rewritten).
            self.assertIn("  - 根拠: PORTFOLIO/RESEARCH_INDEXに存在（STALE）", page)
            self.assertIn("今日の推奨・新しい材料・現在の保有を示すものではありません", page)
        self.assertIn("優先度を算出できた候補がありません", pages["2026-11-19"])
        self.assertIn("検証済みかどうかの記録がありません", pages["2026-11-18"])

    def test_source_report_files_are_not_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_dir = root / "reports"
            report_dir.mkdir()
            source = report_dir / "2026-11-19.md"
            source.write_text(REPORT, encoding="utf-8")
            saved = PAGES.REPORT_DIR, PAGES.DIAG_DIR, PAGES.SITE
            try:
                PAGES.REPORT_DIR, PAGES.DIAG_DIR, PAGES.SITE = report_dir, root / "diag", root / "site"
                PAGES.build()
            finally:
                PAGES.REPORT_DIR, PAGES.DIAG_DIR, PAGES.SITE = saved
            self.assertEqual(source.read_text(encoding="utf-8"), REPORT)


if __name__ == "__main__":
    unittest.main()
