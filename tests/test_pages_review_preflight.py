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
                {"security_code":"6622", "status":"OK", "total_priority":3.0}]))
            rules = {f["rule"] for f in report["findings"]}
            self.assertNotIn("NO_VERIFIED_FOCUS", rules)
            self.assertNotIn("DEAD_EXPECTATION_TEASER", rules)

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
                    candidates=[{"security_code": "4063", "status": "OK", "total_priority": priority}]))
                self.assertIn("NO_VERIFIED_FOCUS", {f["rule"] for f in report["findings"]})

    def test_unrelated_link_does_not_clear_dead_teaser(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.fixture(Path(td), status="OK")
            builder = root / ".github/pages/build_daihen_cockpit.py"
            builder.write_text(builder.read_text().replace("</div>\x27",
                "</div><a href=\x27#unrelated\x27>別項目</a>\x27"))
            report = inspect(root)
            self.assertIn("DEAD_EXPECTATION_TEASER", {f["rule"] for f in report["findings"]})

    def test_missing_files_cannot_be_pass(self):
        with tempfile.TemporaryDirectory() as td:
            report = inspect(Path(td))
            rules = {f["rule"] for f in report["findings"]}
            self.assertIn("MORNING_DATA_MISSING", rules)
            self.assertIn("DAIHEN_SOURCE_MISSING", rules)


if __name__ == "__main__":
    unittest.main()
