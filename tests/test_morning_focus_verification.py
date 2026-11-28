"""#949: stale/unscored candidates must never be shown as a verified focus pick.

Each displayed AI watch item must be bound to the deterministic verified
security-code set for the same report date; a dataset-level flag is not enough.

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
DAY = "2026-11-28"


def _row(code, name, *, rank=None, priority=None, status="STALE", sources=("RESEARCH_INDEX",), last="2026-08-02"):
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


def _fresh(code="6622", name="ダイヘン", rank=1, priority=80.0):
    return _row(code, name, rank=rank, priority=priority, status="CURRENT", last="2026-11-27")


def _dataset(rows, *, status="OK", as_of=DAY):
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
        self.assertEqual(focus["verified_security_codes"], [])
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
        self.assertEqual(focus["verified_security_codes"], [])

    def test_fresh_owner_pick_alone_is_verified_by_code(self):
        pick = _row("6232", "ACSL", rank=1, priority=60, status="CURRENT", sources=("OWNER_PICK",), last="2026-11-27")
        focus = candidate_focus_verification(_dataset([pick]))
        self.assertTrue(focus["verified_focus_available"])
        self.assertEqual(focus["verified_security_codes"], ["6232"])
        self.assertEqual(focus["as_of"], DAY)
        self.assertIsNone(focus["reason"])

    def test_mixed_fresh_and_stale_verifies_only_the_fresh_scored_code(self):
        rows = [_fresh(), _row("4063", "信越化学工業", rank=2, priority=70, status="STALE"), _row("3110", "日東紡")]
        focus = candidate_focus_verification(_dataset(rows))
        self.assertEqual(focus["verified_security_codes"], ["6622"])
        self.assertNotIn("4063", focus["verified_security_codes"])

    def test_new_format_code_is_accepted_and_malformed_code_is_not(self):
        rows = [_fresh("278A", "テラドローン"), _fresh("ABCD", "bad"), _fresh("62322", "bad"), _fresh(None, "no code")]
        self.assertEqual(candidate_focus_verification(_dataset(rows))["verified_security_codes"], ["278A"])

    def test_current_status_needs_a_dated_evidence_not_after_as_of(self):
        undated = _row("6622", "ダイヘン", rank=1, priority=80, status="CURRENT", last=None)
        future = _row("6758", "Sony Group", rank=2, priority=70, status="CURRENT", last="2026-12-01")
        garbage = _row("3110", "日東紡", rank=3, priority=60, status="CURRENT", last="unknown")
        focus = candidate_focus_verification(_dataset([undated, future, garbage]))
        self.assertFalse(focus["verified_focus_available"])

    def test_stale_source_blocks_even_a_current_scored_row(self):
        focus = candidate_focus_verification(_dataset([_fresh()], status="STALE"))
        self.assertFalse(focus["verified_focus_available"])
        self.assertEqual(focus["verified_security_codes"], [])
        self.assertIn("STALE", focus["reason"])

    def test_zero_candidates_or_missing_data_is_not_verified(self):
        for dataset in (_dataset([], status="MISSING"), {"as_of": DAY}, {"candidates": "broken"}):
            focus = candidate_focus_verification(dataset)
            self.assertFalse(focus["verified_focus_available"])
            self.assertEqual(focus["candidate_count"], 0)

    def test_malformed_payloads_fail_closed_without_raising(self):
        rows = [_fresh()]
        malformed = [
            None,
            "OK",
            [],
            {"as_of": DAY, "source_status": 5, "candidates": rows},
            {"as_of": DAY, "source_status": "OK", "candidates": rows},
            {"as_of": DAY, "source_status": [None, "candidates"], "candidates": rows},
            {"as_of": None, "source_status": [{"name": "candidates", "status": "OK"}], "candidates": rows},
            {"as_of": DAY, "source_status": [{"name": "candidates", "status": "OK"}], "candidates": [None, 1, "x"]},
        ]
        for dataset in malformed:
            focus = candidate_focus_verification(dataset)
            self.assertFalse(focus["verified_focus_available"], dataset)
            self.assertEqual(focus["verified_security_codes"], [], dataset)

    def test_non_finite_or_boolean_priority_is_not_a_score(self):
        rows = [_fresh(priority=math.nan), _fresh("6758", "Sony Group", rank=2, priority=True), _fresh("3110", "日東紡", rank=math.inf)]
        self.assertFalse(candidate_focus_verification(_dataset(rows))["verified_focus_available"])

    def test_focus_record_is_json_serialisable_for_diagnostics(self):
        json.dumps(candidate_focus_verification(_dataset([_fresh(), *ALL_STALE])), ensure_ascii=False)


def _report(watch_section: str) -> str:
    return (
        "---\ndataset_status: PARTIAL\n---\n\n# AI Morning Report\n\n"
        "## 市場概況\n- 半導体は横ばい。\n\n## 今日の戦略\n- 様子見。\n\n"
        f"## 注目銘柄\n{watch_section}\n## 次回確認時に見る条件\n- 決算日程。\n"
    )


SHINETSU = "- 4063 信越化学工業\n  - 根拠: PORTFOLIO/RESEARCH_INDEXに存在（STALE）\n"
DAIHEN = "- 6622 ダイヘン（最終リサーチ 2026-11-27）\n  - 根拠: CURRENT・priority 80\n"


def _diag(rows, *, as_of=DAY):
    return {"dataset_status": "OK", "candidate_focus": candidate_focus_verification(_dataset(rows, as_of=as_of))}


class ReportFocusRenderingTests(unittest.TestCase):
    def _build(self, reports):
        """reports: {day: (report_text, diagnostics_or_None)}"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_dir, diag_dir, site = root / "reports", root / "diag", root / "site"
            report_dir.mkdir()
            diag_dir.mkdir()
            for day, (text, diagnostics) in reports.items():
                (report_dir / f"{day}.md").write_text(text, encoding="utf-8")
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
                for day in reports
            }
            return index, pages

    def _assert_notice_before_items(self, page):
        notice = page.index(LABEL)
        self.assertLess(page.index("## 注目銘柄"), notice)
        self.assertLess(notice, page.index("## 次回確認時に見る条件"))

    def test_rei_blocker_sole_fresh_daihen_does_not_verify_ai_shinetsu(self):
        # Exact #949 failure: an unrelated CURRENT row must not launder 4063.
        index, pages = self._build({DAY: (_report(SHINETSU), _diag([_fresh()]))})
        self.assertNotIn("注目: 4063", index)
        self.assertIn(f"注目: {LABEL}（AI候補メモ・未検証: 4063 信越化学工業）", index)
        self._assert_notice_before_items(pages[DAY])
        self.assertIn("この日の検証済み候補は 6622 のみです", pages[DAY])

    def test_valid_same_code_item_is_displayed_without_warning(self):
        index, pages = self._build({DAY: (_report(DAIHEN), _diag([_fresh()]))})
        self.assertIn("注目: 6622 ダイヘン（最終リサーチ 2026-11-27）", index)
        self.assertNotIn(LABEL, index)
        self.assertNotIn(LABEL, pages[DAY])

    def test_mixed_valid_and_invalid_items_keep_the_detail_warning(self):
        index, pages = self._build({DAY: (_report(DAIHEN + SHINETSU), _diag([_fresh()]))})
        # Card shows the first item, which is verified...
        self.assertIn("注目: 6622 ダイヘン", index)
        # ...but the detail page is not cleared just because one item qualifies.
        self._assert_notice_before_items(pages[DAY])

    def test_mixed_codes_in_one_line_fail_closed(self):
        index, _ = self._build({DAY: (_report("- 6622 ダイヘン / 4063 信越化学工業\n"), _diag([_fresh()]))})
        self.assertNotIn("注目: 6622", index)
        self.assertIn(LABEL, index)

    def test_name_only_item_without_identifier_fails_closed(self):
        index, pages = self._build({DAY: (_report("- ダイヘン\n  - 根拠: CURRENT\n"), _diag([_fresh()]))})
        self.assertIn(f"注目: {LABEL}（AI候補メモ・未検証: ダイヘン）", index)
        self._assert_notice_before_items(pages[DAY])

    def test_verification_for_a_different_report_date_is_not_reused(self):
        index, pages = self._build({DAY: (_report(DAIHEN), _diag([_fresh()], as_of="2026-11-27"))})
        self.assertIn(LABEL, index)
        self._assert_notice_before_items(pages[DAY])

    def test_legacy_and_unscored_history_never_present_shinetsu_as_focus(self):
        index, pages = self._build({
            "2026-11-19": (_report(SHINETSU), _diag(ALL_STALE, as_of="2026-11-19")),
            "2026-11-18": (_report(SHINETSU), None),
            "2026-11-17": (_report(SHINETSU), {"dataset_status": "OK"}),
        })
        self.assertNotIn("注目: 4063", index)
        self.assertEqual(index.count(f"注目: {LABEL}（AI候補メモ・未検証: 4063 信越化学工業）"), 3)
        self.assertIn("優先度を算出できた候補がありません", pages["2026-11-19"])
        self.assertIn("検証済みかどうかの記録がありません", pages["2026-11-18"])
        for page in pages.values():
            self._assert_notice_before_items(page)
            # Original AI text is kept verbatim (history is not rewritten).
            self.assertIn("  - 根拠: PORTFOLIO/RESEARCH_INDEXに存在（STALE）", page)
            self.assertIn("今日の推奨・新しい材料・現在の保有を示すものではありません", page)

    def test_tampered_or_malformed_focus_record_fails_closed(self):
        tampered = [
            {"candidate_focus": {"as_of": DAY, "verified_focus_available": True, "verified_security_codes": "6622"}},
            {"candidate_focus": {"as_of": DAY, "verified_focus_available": "true", "verified_security_codes": ["6622"]}},
            {"candidate_focus": {"as_of": DAY, "verified_focus_available": True, "verified_security_codes": ["66 22"]}},
            {"candidate_focus": ["6622"]},
        ]
        for diagnostics in tampered:
            self.assertEqual(PAGES.verified_codes(diagnostics, DAY), frozenset(), diagnostics)

    def test_calendar_dates_are_not_read_as_security_codes(self):
        self.assertEqual(PAGES.mentioned_codes("6622 ダイヘン（最終 2026-11-27、2026/8/2、2026年）"), {"6622"})

    def test_source_report_files_are_not_modified(self):
        text = _report(SHINETSU)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_dir = root / "reports"
            report_dir.mkdir()
            source = report_dir / f"{DAY}.md"
            source.write_text(text, encoding="utf-8")
            saved = PAGES.REPORT_DIR, PAGES.DIAG_DIR, PAGES.SITE
            try:
                PAGES.REPORT_DIR, PAGES.DIAG_DIR, PAGES.SITE = report_dir, root / "diag", root / "site"
                PAGES.build()
            finally:
                PAGES.REPORT_DIR, PAGES.DIAG_DIR, PAGES.SITE = saved
            self.assertEqual(source.read_text(encoding="utf-8"), text)


if __name__ == "__main__":
    unittest.main()
