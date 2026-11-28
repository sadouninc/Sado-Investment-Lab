"""#998: mobile browser audit verdict contract over synthetic observations.

担当: ♦️ソラ
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import pages_browser_audit_contract as bac  # noqa: E402

SHA = "a" * 40


def obs(route="/", vp=320, **overrides):
    base = {
        "route": route, "viewport": vp, "status": "OK", "screenshot": f"shots/{route.strip('/').replace('/', '_') or 'root'}-{vp}.png",
        "document_scroll_width": vp, "document_client_width": vp,
        "body_scroll_width": vp, "body_client_width": vp,
        "overflow_elements": [],
        "anchors": [{"href": "#market-expectation", "link_visible": True, "target_exists": True,
                     "target_visible": True, "reached": True}],
        "details": [{"selector": "details.codex-disclosure", "content_visible_closed": False,
                     "content_visible_open": True}],
    }
    base.update(overrides)
    return base


def audit(observations=None, **overrides):
    base = {
        "source_sha": SHA, "artifact_sha": "b" * 40, "run_id": 46147386877, "captured_by": "browser",
        "required_routes": ["/", "/reports/morning/"], "viewports": [320, 390],
        "observations": observations if observations is not None else [
            obs("/", 320), obs("/", 390), obs("/reports/morning/", 320), obs("/reports/morning/", 390)],
    }
    base.update(overrides)
    return base


def rule_status(report, rule):
    return [f["status"] for f in report["findings"] if f["rule"] == rule]


class VerdictTests(unittest.TestCase):
    def test_all_rules_satisfied_is_pass_with_scope_limits(self):
        report = bac.evaluate(audit())
        self.assertEqual(report["verdict"], "PASS", report["findings"])
        self.assertFalse(report["coverage"]["semantic_ux_review"])
        self.assertTrue(report["coverage"]["observations_from_real_browser"])

    def test_synthetic_observations_are_not_labelled_real_browser(self):
        report = bac.evaluate(audit(captured_by="fixture"))
        self.assertFalse(report["coverage"]["observations_from_real_browser"])

    def test_nothing_measured_is_never_pass(self):
        self.assertEqual(bac.evaluate(audit(observations=[]))["verdict"], "NOT_RUN")
        for broken in (None, [], {}, "x"):
            self.assertIn(bac.evaluate(broken)["verdict"], {"UNKNOWN", "NOT_RUN"})

    def test_missing_viewport_observation_is_not_run(self):
        observations = [obs("/", 320), obs("/reports/morning/", 320), obs("/reports/morning/", 390)]
        report = bac.evaluate(audit(observations))
        self.assertEqual(report["verdict"], "NOT_RUN")
        self.assertIn("NOT_RUN", rule_status(report, "route_presence"))

    def test_missing_provenance_is_unknown(self):
        for key, value in (("source_sha", "abc"), ("artifact_sha", None), ("run_id", True), ("run_id", 0)):
            self.assertEqual(bac.evaluate(audit(**{key: value}))["verdict"], "UNKNOWN", (key, value))


class RouteTests(unittest.TestCase):
    def test_not_found_required_route_is_p0_fail(self):
        observations = audit()["observations"]
        observations[2] = obs("/reports/morning/", 320, status="NOT_FOUND")
        report = bac.evaluate(audit(observations))
        self.assertEqual(report["verdict"], "FAIL")
        fail = next(f for f in report["findings"] if f["status"] == "FAIL")
        self.assertEqual((fail["rule"], fail["severity"]), ("route_presence", "P0"))

    def test_timeout_js_error_and_unknown_status_are_unknown(self):
        for status in ("TIMEOUT", "JS_ERROR", "weird", None):
            observations = audit()["observations"]
            observations[0] = obs("/", 320, status=status)
            self.assertEqual(bac.evaluate(audit(observations))["verdict"], "UNKNOWN", status)

    def test_duplicate_observation_for_same_route_viewport_is_unknown(self):
        observations = audit()["observations"] + [obs("/", 320)]
        self.assertEqual(bac.evaluate(audit(observations))["verdict"], "UNKNOWN")

    def test_malformed_manifest_is_unknown(self):
        for routes in ([], "/", ["reports"], [1]):
            self.assertEqual(bac.evaluate(audit(required_routes=routes))["verdict"], "UNKNOWN", routes)
        self.assertEqual(bac.evaluate(audit(viewports=[0]))["verdict"], "UNKNOWN")


class OverflowTests(unittest.TestCase):
    def _one(self, **overrides):
        observations = audit()["observations"]
        observations[0] = obs("/", 320, **overrides)
        return bac.evaluate(audit(observations))

    def test_page_overflow_fails_with_offending_selector(self):
        report = self._one(document_scroll_width=412, overflow_elements=[{"selector": "ul.long-list"}])
        self.assertEqual(report["verdict"], "FAIL")
        finding = next(f for f in report["findings"] if f["rule"] == "horizontal_overflow" and f["status"] == "FAIL")
        self.assertEqual(finding["observed"]["page_overflow_elements"], ["ul.long-list"])
        self.assertEqual(finding["screenshot"], "shots/root-320.png")

    def test_one_pixel_tolerance_and_body_overflow(self):
        self.assertEqual(self._one(document_scroll_width=321)["verdict"], "PASS")
        self.assertEqual(self._one(body_scroll_width=330)["verdict"], "FAIL")

    def test_locally_scrollable_table_is_not_page_overflow(self):
        report = self._one(overflow_elements=[{"selector": "table.data", "scrollable_container": True}])
        self.assertEqual(report["verdict"], "PASS")
        finding = next(f for f in report["findings"] if f["rule"] == "horizontal_overflow" and f["route"] == "/"
                       and f["viewport"] == 320)
        self.assertEqual(finding["observed"]["locally_scrollable"], ["table.data"])

    def test_missing_width_or_malformed_elements_are_unknown(self):
        self.assertEqual(self._one(document_scroll_width=None)["verdict"], "UNKNOWN")
        self.assertEqual(self._one(body_client_width=True)["verdict"], "UNKNOWN")
        self.assertEqual(self._one(overflow_elements=[{"x": 1}])["verdict"], "UNKNOWN")


class AnchorAndDetailsTests(unittest.TestCase):
    def _one(self, **overrides):
        observations = audit()["observations"]
        observations[0] = obs("/", 320, **overrides)
        return bac.evaluate(audit(observations))

    def test_dead_or_hidden_anchor_target_fails(self):
        for broken in ({"target_exists": False}, {"target_visible": False}, {"reached": False}, {"link_visible": False}):
            anchor = {"href": "#market-expectation", "link_visible": True, "target_exists": True,
                      "target_visible": True, "reached": True, **broken}
            self.assertEqual(self._one(anchors=[anchor])["verdict"], "FAIL", broken)

    def test_unmeasured_anchor_is_unknown_and_none_present_is_not_applicable(self):
        self.assertEqual(self._one(anchors=[{"href": "#x", "reached": True}])["verdict"], "UNKNOWN")
        self.assertEqual(self._one(anchors=None)["verdict"], "UNKNOWN")
        report = self._one(anchors=[])
        self.assertEqual(report["verdict"], "PASS")
        na = [f for f in report["findings"] if f["status"] == "NOT_APPLICABLE"]
        self.assertTrue(na and na[0]["reason"])

    def test_details_must_toggle_visibility(self):
        self.assertEqual(self._one(details=[{"selector": "d", "content_visible_closed": False,
                                              "content_visible_open": False}])["verdict"], "FAIL")
        self.assertEqual(self._one(details=[{"selector": "d", "content_visible_closed": True,
                                              "content_visible_open": True}])["verdict"], "FAIL")
        self.assertEqual(self._one(details=[{"selector": "d"}])["verdict"], "UNKNOWN")
        self.assertEqual(self._one(details=[])["verdict"], "PASS")


class ReiCounterexampleTests(unittest.TestCase):
    """❤️レイ review 6099042530."""

    def test_partial_viewport_manifest_cannot_pass(self):
        for viewports in ([320], [1], [390]):
            observations = [obs(r, v) for r in ("/", "/reports/morning/") for v in viewports]
            report = bac.evaluate(audit(observations, viewports=viewports))
            self.assertNotEqual(report["verdict"], "PASS", viewports)
            self.assertTrue(any("mandatory viewport" in (f["reason"] or "") for f in report["findings"]), viewports)

    def test_zero_or_inconsistent_widths_are_not_a_measurement(self):
        observations = audit()["observations"]
        observations[0] = obs("/", 320, document_scroll_width=0, document_client_width=0,
                              body_scroll_width=0, body_client_width=0)
        self.assertEqual(bac.evaluate(audit(observations))["verdict"], "UNKNOWN")
        observations[0] = obs("/", 320, document_scroll_width=1280, document_client_width=1280,
                              body_scroll_width=1280, body_client_width=1280)  # desktop width at "320"
        self.assertEqual(bac.evaluate(audit(observations))["verdict"], "UNKNOWN")
        observations[0] = obs("/", 320, document_client_width=305, document_scroll_width=305,
                              body_client_width=305, body_scroll_width=305)  # scrollbar tolerance
        self.assertEqual(bac.evaluate(audit(observations))["verdict"], "PASS")

    def test_malformed_rows_alongside_valid_set_fail_closed(self):
        for junk in (None, {"route": "/"}, {"viewport": 320}, "row", {"route": 1, "viewport": 320}):
            report = bac.evaluate(audit(audit()["observations"] + [junk]))
            self.assertEqual(report["verdict"], "UNKNOWN", junk)
        self.assertEqual(bac.evaluate(audit(observations={"x": 1}))["verdict"], "UNKNOWN")

    def test_browser_claim_alone_is_not_real_browser_coverage(self):
        empty = bac.evaluate(audit(observations=[]))
        self.assertTrue(empty["coverage"]["caller_claims_browser_capture"])
        self.assertFalse(empty["coverage"]["observations_from_real_browser"])
        bad_provenance = bac.evaluate(audit(source_sha="x"))
        self.assertFalse(bad_provenance["coverage"]["observations_from_real_browser"])
        self.assertTrue(bac.evaluate(audit())["coverage"]["observations_from_real_browser"])

    def test_known_false_anchor_flag_is_fail_even_with_missing_flags(self):
        observations = audit()["observations"]
        observations[0] = obs("/", 320, anchors=[{"href": "#x", "target_exists": False}])
        report = bac.evaluate(audit(observations))
        self.assertEqual(report["verdict"], "FAIL")

    def test_cli_handles_deep_json_and_diagnostics_are_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "deep.json").write_text("[" * 100000 + "]" * 100000, encoding="utf-8")
            rc = bac.main([str(root / "deep.json"), "--output", str(root / "r.json")])
            self.assertEqual(rc, 0)
            self.assertIn(json.loads((root / "r.json").read_text())["verdict"], {"UNKNOWN", "NOT_RUN"})
        report = bac.evaluate(audit(source_sha={"nested": ["x" * 1000]}))
        observed = next(f for f in report["findings"] if f["rule"] == "provenance")["observed"]
        self.assertEqual(observed["source_sha"], "<dict>")
        long = bac.evaluate(audit(artifact_sha="y" * 5000))
        self.assertLessEqual(len(next(f for f in long["findings"] if f["rule"] == "provenance")["observed"]["artifact_sha"]), 200)


class OutputTests(unittest.TestCase):
    def test_finding_fields_and_japanese_summary(self):
        observations = audit()["observations"]
        observations[1] = obs("/", 390, document_scroll_width=500)
        report = bac.evaluate(audit(observations))
        for f in report["findings"]:
            self.assertTrue({"route", "viewport", "rule", "severity", "status", "observed", "expected", "screenshot"} <= f.keys())
        summary = bac.render_summary_ja(report)
        self.assertIn("不合格", summary)
        self.assertIn("[P1] / @ 390px horizontal_overflow", summary)
        self.assertIn("意味的なUXレビュー", summary)
        json.dumps(report, ensure_ascii=False)

    def test_summary_formats_findings_without_viewport(self):
        report = bac.evaluate(audit(source_sha="bad"))
        summary = bac.render_summary_ja(report)
        self.assertIn("[P1] 全体 provenance: 判定不能（UNKNOWN）", summary)
        self.assertNotIn("Nonepx", summary)
        broken = bac.render_summary_ja(bac.evaluate(audit(required_routes=[])))
        self.assertNotIn("Nonepx", broken)

    def test_cli_writes_report_and_unreadable_input_is_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "obs.json").write_text(json.dumps(audit()), encoding="utf-8")
            bac.main([str(root / "obs.json"), "--output", str(root / "r.json"), "--summary", str(root / "s.md")])
            self.assertEqual(json.loads((root / "r.json").read_text())["verdict"], "PASS")
            self.assertIn("問題として報告する項目はありません", (root / "s.md").read_text(encoding="utf-8"))
            (root / "bad.json").write_text("{", encoding="utf-8")
            bac.main([str(root / "bad.json"), "--output", str(root / "b.json")])
            self.assertIn(json.loads((root / "b.json").read_text())["verdict"], {"UNKNOWN", "NOT_RUN"})

    def test_input_is_not_mutated(self):
        data = audit()
        snapshot = copy.deepcopy(data)
        bac.evaluate(data)
        self.assertEqual(data, snapshot)


if __name__ == "__main__":
    unittest.main()
