import json
import tempfile
import unittest
from pathlib import Path

from scripts.pages_review_preflight import inspect, render_markdown


class PagesReviewPreflightTests(unittest.TestCase):
    def fixture(self, root, *, status="STALE", candidates=None, with_teaser=True):
        file = root / "data/generated/public/morning-dataset.json"
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps({"as_of": "2026-11-20", "generated_at": "2026-11-19T23:47:21Z",
            "source_status": [{"name": name, "status": status, "as_of": "2026-08-08", "reason": "old"}
                              for name in ("portfolio", "capital", "events", "watchlist", "candidates")],
            "candidates": candidates if candidates is not None else [
                {"security_code": "4063", "status": "STALE", "total_priority": None}]}))
        builder = root / ".github/pages/build_daihen_cockpit.py"
        builder.parent.mkdir(parents=True, exist_ok=True)
        teaser = ('<div class="cockpit-expectation-summary">市場期待との差は？</div>'
                  if with_teaser else '<a href="#market-expectations">市場期待の詳細</a>')
        builder.write_text('def _expectation_first_view():\n    return ' + repr(teaser) + '\n\ndef page_content():\n    pass\n')
        return root

    def test_stale_and_dead_teaser_are_explicit(self):
        with tempfile.TemporaryDirectory() as td:
            report = inspect(self.fixture(Path(td)))
            rules = {f["rule"] for f in report["findings"]}
            self.assertIn("SOURCE_NOT_CURRENT", rules)
            self.assertIn("NO_VERIFIED_FOCUS", rules)
            self.assertIn("DEAD_EXPECTATION_TEASER", rules)
            self.assertEqual("NOT_RUN", report["run_scope"]["ai_review"])
            self.assertIn("AIによる意味理解レビュー", render_markdown(report))

    def test_no_false_focus_when_all_stale(self):
        with tempfile.TemporaryDirectory() as td:
            report = inspect(self.fixture(Path(td), candidates=[
                {"security_code":"4063", "status":"STALE", "total_priority":None},
                {"security_code":"6232", "status":"STALE", "total_priority":None}]))
            self.assertTrue(any(f["rule"] == "NO_VERIFIED_FOCUS" for f in report["findings"]))

    def test_fresh_candidate_and_link_avoid_specific_findings(self):
        with tempfile.TemporaryDirectory() as td:
            report = inspect(self.fixture(Path(td), status="OK", with_teaser=False, candidates=[
                {"security_code":"6622", "company_name":"ダイヘン", "status":"CURRENT", "total_priority":3.0, "rank":1, "last_researched_at":"2026-11-19"}]))
            rules = {f["rule"] for f in report["findings"]}
            self.assertNotIn("NO_VERIFIED_FOCUS", rules)
            self.assertNotIn("DEAD_EXPECTATION_TEASER", rules)

    def test_current_candidate_contract_rejects_unverified_rows_and_source(self):
        valid = {"security_code": "6622", "company_name": "ダイヘン",
                 "status": "CURRENT", "total_priority": 3.0, "rank": 1,
                 "last_researched_at": "2026-11-19"}
        cases = (
            ("provider_ok", "OK", valid, False),
            ("provider_partial", "PARTIAL", valid, True),
            ("row_ok_not_current", "OK", dict(valid, status="OK"), True),
            ("stale", "OK", dict(valid, status="STALE"), True),
            ("missing_date", "OK", dict(valid, last_researched_at=None), True),
            ("future_date", "OK", dict(valid, last_researched_at="2026-11-21"), True),
            ("invalid_date", "OK", dict(valid, last_researched_at="2026-02-30"), True),
            ("missing_rank", "OK", dict(valid, rank=None), True),
            ("zero_rank", "OK", dict(valid, rank=0), True),
            ("fractional_rank", "OK", dict(valid, rank=1.5), True),
            ("missing_name", "OK", dict(valid, company_name=""), True),
            ("invalid_code", "OK", dict(valid, security_code="theme"), True),
        )
        for name, status, row, should_flag in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as td:
                report = inspect(self.fixture(Path(td), status=status,
                    candidates=[row], with_teaser=False))
                self.assertEqual(should_flag, "NO_VERIFIED_FOCUS" in
                                 {f["rule"] for f in report["findings"]})

    def test_missing_candidate_source_or_dataset_date_is_not_verified(self):
        valid = {"security_code": "285A", "company_name": "キオクシア",
                 "status": "CURRENT", "total_priority": 3.0, "rank": 1,
                 "last_researched_at": "2026-11-19"}
        for key in ("as_of", "source_status"):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as td:
                root = self.fixture(Path(td), status="OK", candidates=[valid])
                dataset = root / "data/generated/public/morning-dataset.json"
                data = json.loads(dataset.read_text())
                del data[key]
                dataset.write_text(json.dumps(data))
                self.assertIn("NO_VERIFIED_FOCUS", {f["rule"] for f in inspect(root)["findings"]})

    def test_empty_missing_invalid_candidates_fail_closed(self):
        for candidates in ([], "invalid"):
            with self.subTest(candidates=candidates), tempfile.TemporaryDirectory() as td:
                root = self.fixture(Path(td), status="OK", with_teaser=False, candidates=candidates)
                report = inspect(root)
                self.assertIn("NO_VERIFIED_FOCUS", {f["rule"] for f in report["findings"]})
        with tempfile.TemporaryDirectory() as td:
            root = self.fixture(Path(td), status="OK", with_teaser=False)
            dataset = root / "data/generated/public/morning-dataset.json"
            data = json.loads(dataset.read_text())
            del data["candidates"]
            dataset.write_text(json.dumps(data))
            report = inspect(root)
            self.assertTrue(any(f["rule"] == "NO_VERIFIED_FOCUS" and "missing" in f["evidence"]
                                for f in report["findings"]))

    def test_invalid_priorities_are_not_verified(self):
        for priority in ("", True, "3", float("inf"), None):
            with self.subTest(priority=priority), tempfile.TemporaryDirectory() as td:
                report = inspect(self.fixture(Path(td), status="OK", with_teaser=False,
                    candidates=[{"security_code": "4063", "company_name": "信越化学", "status": "CURRENT", "total_priority": priority, "rank": 1, "last_researched_at": "2026-11-19"}]))
                self.assertIn("NO_VERIFIED_FOCUS", {f["rule"] for f in report["findings"]})

    def test_unrelated_link_does_not_clear_dead_teaser(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.fixture(Path(td), status="OK")
            builder = root / ".github/pages/build_daihen_cockpit.py"
            builder.write_text(builder.read_text().replace("</div>\x27",
                "</div><a href=\x27#unrelated\x27>別項目</a>\x27"))
            report = inspect(root)
            self.assertIn("DEAD_EXPECTATION_TEASER", {f["rule"] for f in report["findings"]})

    def test_teaser_link_without_target_stays_a_finding(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.fixture(Path(td), status="OK")
            builder = root / ".github/pages/build_daihen_cockpit.py"
            source = builder.read_text()
            source = source.replace(
                '<div class="cockpit-expectation-summary">市場期待との差は？</div>',
                '<div class="cockpit-expectation-summary"><a href="#market-expectations">比較を見る</a></div>',
            )
            builder.write_text(source)
            report = inspect(root)
            self.assertIn("DEAD_EXPECTATION_TEASER", {f["rule"] for f in report["findings"]})

    def test_teaser_link_with_source_target_is_only_static_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.fixture(Path(td), status="OK")
            builder = root / ".github/pages/build_daihen_cockpit.py"
            source = builder.read_text()
            source = source.replace(
                '<div class="cockpit-expectation-summary">市場期待との差は？</div>',
                '<div class="cockpit-expectation-summary"><a href="#market-expectations">比較を見る</a></div>',
            )
            builder.write_text(source + '\\nMARKET_HTML = \'<h2 id="market-expectations">市場期待</h2>\'\\n')
            report = inspect(root)
            self.assertNotIn("DEAD_EXPECTATION_TEASER", {f["rule"] for f in report["findings"]})
            self.assertEqual("NOT_RUN", report["run_scope"]["browser_review"])

    def test_teaser_anchor_positions_and_unrelated_links(self):
        card = '<div class="cockpit-expectation-summary">市場期待との差は？</div>'
        cases = (
            ("outer", '<a href="#market-expectations">' + card + '</a>', False),
            ("inner", '<div class="cockpit-expectation-summary"><a href="#market-expectations">比較</a></div>', False),
            ("self_href_first", '<a href="#market-expectations" class="cockpit-expectation-summary">比較</a>', False),
            ("self_class_first", '<a class="cockpit-expectation-summary" href="#market-expectations">比較</a>', False),
            ("unrelated_same_target", card + '<a href="#market-expectations">別項目</a>', True),
            ("unrelated_other_target", card + '<a href="#unrelated">別項目</a>', True),
        )
        for name, html, should_flag in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as td:
                root = self.fixture(Path(td), status="OK")
                builder = root / ".github/pages/build_daihen_cockpit.py"
                builder.write_text(
                    "def _expectation_first_view():\n    return " + repr(html)
                    + "\n\ndef page_content():\n    pass\n"
                    + 'TARGET_HTML = \'<h2 id="market-expectations">市場期待</h2>\'\n'
                )
                report = inspect(root)
                rules = {f["rule"] for f in report["findings"]}
                self.assertEqual(should_flag, "DEAD_EXPECTATION_TEASER" in rules)
                self.assertEqual("NOT_RUN", report["run_scope"]["browser_review"])

    def test_missing_files_cannot_be_pass(self):
        with tempfile.TemporaryDirectory() as td:
            report = inspect(Path(td))
            rules = {f["rule"] for f in report["findings"]}
            self.assertIn("MORNING_DATA_MISSING", rules)
            self.assertIn("DAIHEN_SOURCE_MISSING", rules)


if __name__ == "__main__":
    unittest.main()
