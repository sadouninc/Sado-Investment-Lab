"""#949: stale/unscored candidates must never be shown as a verified focus pick.

A verified focus is rendered only from canonical (security_code, company_name)
pairs recorded for the same report date. AI watch prose is never identity
evidence and is always labelled as an unverified memo.

担当: ♦️ソラ
"""
from __future__ import annotations

from datetime import date
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ai_morning_analyst import _verified_row_code, candidate_focus_verification  # noqa: E402

MODULE_PATH = ROOT / ".github" / "pages" / "build_ai_morning_reports.py"
SPEC = importlib.util.spec_from_file_location("build_ai_morning_reports_949", MODULE_PATH)
assert SPEC and SPEC.loader
PAGES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PAGES)

LABEL = "今日の検証済み注目銘柄は未確定"
DATED_LABEL = "当日時点の検証済み注目銘柄は未確定"
POINTER = "（未検証のAI候補メモは詳細ページで確認）"
VERIFIED = "注目（候補データで検証済み・投資推奨ではありません）"
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

    def test_verified_candidates_are_canonical_code_name_pairs(self):
        rows = [_fresh(), _fresh("278A", "テラ  ドローン", rank=2), _row("4063", "信越化学工業", rank=3, priority=70)]
        focus = candidate_focus_verification(_dataset(rows))
        self.assertEqual(
            focus["verified_candidates"],
            [{"security_code": "278A", "company_name": "テラ ドローン"}, {"security_code": "6622", "company_name": "ダイヘン"}],
        )

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



class CandidateFocusStrictnessTests(unittest.TestCase):
    """#966: positive integer rank, strict dates, ambiguous codes, abnormal values."""

    def _codes(self, rows, **kwargs):
        return candidate_focus_verification(_dataset(rows, **kwargs))["verified_security_codes"]

    def test_rank_must_be_a_positive_integer(self):
        for rank in (0, -1, 1.5, True, "1", None, math.nan, math.inf, 10**400):
            self.assertEqual(self._codes([_fresh(rank=rank)]), [], rank)
        # Same rule as #951: an integral float rank is accepted.
        self.assertEqual(self._codes([_fresh(rank=1.0)]), ["6622"])
        self.assertEqual(self._codes([_fresh(rank=3)]), ["6622"])

    def test_huge_or_abnormal_priority_never_raises_and_is_not_a_score(self):
        for priority in (10**400, -(10**400), "80", [80], {"v": 80}):
            focus = candidate_focus_verification(_dataset([_fresh(priority=priority)]))
            self.assertEqual(focus["verified_security_codes"], [], priority)
            self.assertEqual(focus["scored_count"], 0, priority)

    def test_research_date_and_as_of_must_be_strict_calendar_dates(self):
        for last in ("2026-11-27T00:00:00", "2026-11-27garbage", "20261127", "2026-02-30", " 2026-11-27", 20261127):
            row = _row("6622", "ダイヘン", rank=1, priority=80, status="CURRENT", last=last)
            self.assertEqual(self._codes([row]), [], last)
        for as_of in ("2026-11-28T09:00:00", "2026-11-28 ", "2026/11/28", None):
            focus = candidate_focus_verification(_dataset([_fresh()], as_of=as_of))
            self.assertFalse(focus["verified_focus_available"], as_of)
            self.assertIsNone(focus["as_of"], as_of)

    def test_status_must_be_exactly_current_and_source_exactly_ok(self):
        row = _row("6622", "ダイヘン", rank=1, priority=80, status="current", last="2026-11-27")
        self.assertEqual(self._codes([row]), [])
        self.assertEqual(self._codes([_fresh()], status="ok"), [])
        self.assertEqual(self._codes([_fresh()], status=None), [])

    def test_same_code_with_different_names_is_never_verified(self):
        rows = [
            _fresh("6622", "ダイヘン"),
            _row("6622", "信越化学工業", rank=2, priority=70, status="STALE"),
            _fresh("278A", "テラドローン", rank=3),
        ]
        focus = candidate_focus_verification(_dataset(rows))
        self.assertEqual(focus["verified_security_codes"], ["278A"])  # unrelated valid row is kept
        self.assertEqual(focus["conflicting_security_codes"], ["6622"])
        both_current = [_fresh("6622", "ダイヘン"), _fresh("6622", "別会社", rank=2)]
        self.assertEqual(self._codes(both_current), [])

    def test_identical_pairs_collapse_and_whitespace_is_not_a_conflict(self):
        rows = [_fresh("6622", "ダイヘン"), _fresh("6622", "ダイヘン", rank=2), _fresh("6622", " ダイヘン ", rank=3)]
        focus = candidate_focus_verification(_dataset(rows))
        self.assertEqual(focus["verified_candidates"], [{"security_code": "6622", "company_name": "ダイヘン"}])
        self.assertEqual(focus["conflicting_security_codes"], [])

    def test_missing_or_abnormal_identity_fields_fail_closed_per_row(self):
        rows = [
            _fresh("6622", ""),
            _fresh("6758", None),
            _fresh(6758, "Sony Group", rank=2),
            _fresh("67 58", "Sony Group", rank=3),
            _fresh("3110", "日東紡", rank=4),
        ]
        self.assertEqual(self._codes(rows), ["3110"])

    def test_row_contract_matches_pages_review_preflight(self):
        # #951 audits the same rows statically; the two judgements must agree row by row.
        from scripts.pages_review_preflight import _verified_candidate

        as_of = date.fromisoformat(DAY)
        matrix = [
            _fresh(),
            _fresh(rank=1.0),
            _fresh(rank=0),
            _fresh(rank=1.5),
            _fresh(rank=True),
            _fresh(rank=10**400),
            _fresh(priority=10**400),
            _fresh(priority=math.nan),
            _fresh(name=""),
            _fresh(code="ABCD"),
            _fresh(code=" 6622 "),
            _row("6622", "ダイヘン", rank=1, priority=80, status="current", last="2026-11-27"),
            _row("6622", "ダイヘン", rank=1, priority=80, status="STALE", last="2026-11-27"),
            _row("6622", "ダイヘン", rank=1, priority=80, status="CURRENT", last="2026-11-29"),
            _row("6622", "ダイヘン", rank=1, priority=80, status="CURRENT", last="2026-11-27T00:00:00"),
            _row("6622", "ダイヘン", rank=1, priority=80, status="CURRENT", last=None),
        ]
        for row in matrix:
            self.assertEqual(
                _verified_row_code(row, as_of) is not None,
                _verified_candidate(row, as_of),
                row,
            )

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

    def _memo_notice_precedes_ai_items(self, page):
        notice = page.index("銘柄ごとの照合はしていません")
        self.assertLess(page.index("## 注目銘柄"), notice)
        self.assertLess(notice, page.index("## 次回確認時に見る条件"))
        return notice

    def _assert_verified_card(self, index, labels):
        self.assertIn(f"{VERIFIED}: {labels}", index)
        self.assertNotIn(LABEL, index)
        self.assertNotIn(DATED_LABEL, index)

    def test_rei_blocker_sole_fresh_daihen_does_not_verify_ai_shinetsu(self):
        index, pages = self._build({DAY: (_report(SHINETSU), _diag([_fresh()]))})
        self._assert_verified_card(index, "6622 ダイヘン")
        self.assertNotIn("4063", index)
        self._memo_notice_precedes_ai_items(pages[DAY])

    def test_name_only_subject_with_verified_code_in_comparison_is_not_verified(self):
        ai = "- 信越化学工業（比較対象: 6622 ダイヘン）\n"
        index, pages = self._build({DAY: (_report(ai), _diag([_fresh()]))})
        self._assert_verified_card(index, "6622 ダイヘン")
        self.assertNotIn("信越化学工業", index)
        self._memo_notice_precedes_ai_items(pages[DAY])

    def test_verified_code_only_in_nested_rationale_does_not_clear_detail_notice(self):
        ai = "- 信越化学工業\n  - 根拠: 6622 ダイヘンとの比較\n"
        index, pages = self._build({DAY: (_report(ai), _diag([_fresh()]))})
        self.assertNotIn("信越化学工業", index)
        self._memo_notice_precedes_ai_items(pages[DAY])

    def test_mismatched_code_and_name_never_produces_a_verified_label(self):
        ai = "- 6622 信越化学工業\n"
        index, pages = self._build({DAY: (_report(ai), _diag([_fresh()]))})
        self.assertNotIn("6622 信越化学工業</", index)
        self.assertNotIn(f"{VERIFIED}: 6622 信越化学工業", index)
        self._assert_verified_card(index, "6622 ダイヘン")
        page = pages[DAY]
        notice = self._memo_notice_precedes_ai_items(page)
        self.assertLess(notice, page.index("- 6622 信越化学工業"))

    def test_truncated_mixed_codes_cannot_reach_the_card_as_verified(self):
        ai = "- 6622 ダイヘン " + "（解説）" * 40 + " / 4063 信越化学工業\n"
        index, _ = self._build({DAY: (_report(ai), _diag([_fresh()]))})
        self._assert_verified_card(index, "6622 ダイヘン")
        self.assertNotIn("解説", index)
        index_unverified, _ = self._build({DAY: (_report(ai), _diag(ALL_STALE))})
        self.assertIn(f"注目: {LABEL}{POINTER}", index_unverified)
        self.assertNotIn("6622", index_unverified)

    def test_positive_canonical_pair_is_displayed_and_ai_memo_stays_labelled(self):
        index, pages = self._build({DAY: (_report(DAIHEN), _diag([_fresh(), _fresh("278A", "テラドローン", rank=2)]))})
        self._assert_verified_card(index, "278A テラドローン / 6622 ダイヘン")
        page = pages[DAY]
        self.assertIn(f"**{VERIFIED}: 278A テラドローン / 6622 ダイヘン**", page)
        self._memo_notice_precedes_ai_items(page)
        self.assertNotIn(DATED_LABEL, page)

    def test_verification_for_a_different_report_date_is_not_reused(self):
        index, pages = self._build({DAY: (_report(DAIHEN), _diag([_fresh()], as_of="2026-11-27"))})
        self.assertIn(f"注目: {LABEL}{POINTER}", index)
        self.assertNotIn(VERIFIED, index)
        self.assertIn(DATED_LABEL, pages[DAY])

    def test_legacy_and_unscored_history_never_present_shinetsu_as_focus(self):
        index, pages = self._build({
            "2026-11-19": (_report(SHINETSU), _diag(ALL_STALE, as_of="2026-11-19")),
            "2026-11-18": (_report(SHINETSU), None),
            "2026-11-17": (_report(SHINETSU), {"dataset_status": "OK"}),
        })
        self.assertNotIn("注目: 4063", index)
        self.assertNotIn(VERIFIED, index)
        # Latest card speaks for today; past cards speak for their own date.
        self.assertEqual(index.count(f"注目: {LABEL}{POINTER}"), 1)
        self.assertEqual(index.count(f"注目: {DATED_LABEL}{POINTER}"), 2)
        # Unverified AI security names never appear on list cards.
        self.assertNotIn("4063", index)
        self.assertNotIn("信越化学工業", index)
        self.assertIn("優先度を算出できた候補がありません", pages["2026-11-19"])
        self.assertIn("検証済みかどうかの記録がありません", pages["2026-11-18"])
        for page in pages.values():
            self._memo_notice_precedes_ai_items(page)
            # Original AI text is kept verbatim (history is not rewritten).
            self.assertIn("  - 根拠: PORTFOLIO/RESEARCH_INDEXに存在（STALE）", page)
            self.assertIn(DATED_LABEL, page)
            self.assertIn("当日の推奨・新しい材料・現在の保有を示すものではありません", page)

    def test_tampered_or_malformed_focus_record_fails_closed(self):
        good = {"security_code": "6622", "company_name": "ダイヘン"}

        def record(entries, **extra):
            focus = {"as_of": DAY, "verified_focus_available": True, "verified_candidates": entries}
            focus.update(extra)
            return {"candidate_focus": focus}

        tampered = [
            record([good], verified_focus_available="true"),
            record([good], as_of=None),
            record("6622"),
            record([]),
            record([good, {"security_code": "66 22", "company_name": "x"}]),
            record([good, {"security_code": "4063"}]),
            record([{"security_code": "6622", "company_name": "ダイヘン\n- 4063 信越化学工業"}]),
            record([{"security_code": "6622", "company_name": "x" * 61}]),
            record([good, "4063"]),
            {"candidate_focus": ["6622"]},
            None,
        ]
        for diagnostics in tampered:
            self.assertEqual(PAGES.verified_candidates(diagnostics, DAY), (), diagnostics)
        self.assertEqual(PAGES.verified_candidates(record([good]), DAY), (("6622", "ダイヘン"),))

    def test_verified_name_is_escaped_in_card_and_detail(self):
        diagnostics = _diag([_fresh(name="<b>A&B</b>")])
        index, pages = self._build({DAY: (_report(DAIHEN), diagnostics)})
        self.assertNotIn("<b>A&B</b>", index)
        self.assertNotIn("<b>A&B</b>", pages[DAY])
        self.assertIn("&lt;b&gt;A&amp;B&lt;/b&gt;", pages[DAY])

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
