"""#997: preview artifact exact-head conformance (offline, read-only).

担当: ♦️ソラ
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import unittest.mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import preview_artifact_contract as pac  # noqa: E402

HEAD = "a" * 40
OLD = "b" * 40
FILES = ["index.html", "concepts/investment-decision-cockpit/index.html", "preview-metadata.json", "assets/book.css"]


def meta(**overrides):
    base = {
        "schema_version": "1.0", "preview": True, "not_production": True, "pull_request": 986,
        "head_sha": HEAD, "built_at": "2026-11-28T15:00:00Z", "namespace": "pr-986", "html_files": 2,
    }
    base.update(overrides)
    return base


def check(metadata=None, files=None, **kwargs):
    kwargs.setdefault("expected_pr", 986)
    kwargs.setdefault("expected_head", HEAD)
    return pac.check_artifact(meta() if metadata is None else metadata,
                              list(FILES) if files is None else files, **kwargs)


def statuses(report, name):
    return [c["status"] for c in report["checks"] if c["check"] == name]


class VerdictTests(unittest.TestCase):
    def test_conforming_artifact_passes_without_claiming_browser_or_production(self):
        report = check()
        self.assertEqual(report["verdict"], "PASS", report["checks"])
        self.assertIn("not a browser, UX or production check", report["limits"])

    def test_stale_head_fails(self):
        report = check(meta(head_sha=OLD))
        self.assertEqual(report["verdict"], "FAIL")
        self.assertEqual(statuses(report, "metadata.head_sha"), ["FAIL"])

    def test_wrong_pr_and_namespace_fail(self):
        self.assertEqual(check(meta(pull_request=985))["verdict"], "FAIL")
        self.assertEqual(check(meta(namespace="pr-985"))["verdict"], "FAIL")

    def test_production_or_non_preview_flags_fail_and_missing_flags_are_unknown(self):
        self.assertEqual(check(meta(not_production=False))["verdict"], "FAIL")
        self.assertEqual(check(meta(preview=False))["verdict"], "FAIL")
        missing = meta()
        del missing["not_production"]
        self.assertEqual(check(missing)["verdict"], "UNKNOWN")

    def test_missing_or_malformed_metadata_is_unknown(self):
        for bad in (None, [], "x"):
            report = pac.check_artifact(bad, list(FILES), expected_pr=986, expected_head=HEAD)
            self.assertEqual(report["verdict"], "UNKNOWN", bad)
        for field, value in (("head_sha", "abc"), ("pull_request", True), ("pull_request", "986"),
                             ("built_at", "2026-02-30T00:00:00Z"), ("schema_version", "2.0"),
                             ("html_files", -1)):
            self.assertEqual(check(meta(**{field: value}))["verdict"], "UNKNOWN", (field, value))

    def test_malformed_expectation_is_unknown(self):
        self.assertEqual(check(expected_pr=0)["verdict"], "UNKNOWN")
        self.assertEqual(check(expected_head="HEAD")["verdict"], "UNKNOWN")

    def test_run_provenance_not_in_schema_is_unknown_not_assumed(self):
        report = check(expected_run_id=46147386877, expected_run_attempt=1)
        self.assertEqual(report["verdict"], "UNKNOWN")
        self.assertEqual(statuses(report, "metadata.run_id"), ["UNKNOWN"])
        with_run = check(meta(run_id=46147386877, run_attempt=2), expected_run_id=46147386877, expected_run_attempt=1)
        self.assertEqual(with_run["verdict"], "FAIL")
        self.assertEqual(statuses(with_run, "metadata.run_attempt"), ["FAIL"])
        matching = check(meta(run_id=46147386877, run_attempt=1), expected_run_id=46147386877, expected_run_attempt=1)
        self.assertEqual(matching["verdict"], "PASS")


class FileAndRouteTests(unittest.TestCase):
    def test_missing_required_route_fails(self):
        files = [f for f in FILES if "cockpit" not in f]
        report = check(meta(html_files=1), files)
        self.assertEqual(report["verdict"], "FAIL")
        self.assertTrue(any("missing route: concepts" in c["detail"] for c in report["checks"]))

    def test_path_traversal_and_absolute_paths_fail(self):
        for bad in ("../secret", "a/../../b", "/etc/passwd", "C:/x", "a\\b", "a\x00b", ""):
            report = check(files=list(FILES) + [bad])
            self.assertEqual(report["verdict"], "FAIL", repr(bad))

    def test_duplicates_after_normalization_fail(self):
        report = check(files=list(FILES) + ["./index.html"])
        self.assertEqual(report["verdict"], "FAIL")
        self.assertTrue(any(c["check"] == "files.duplicate" for c in report["checks"]))

    def test_html_count_mismatch_fails(self):
        self.assertEqual(check(meta(html_files=5))["verdict"], "FAIL")

    def test_empty_or_missing_file_list_is_unknown(self):
        self.assertEqual(check(files=[])["verdict"], "FAIL")  # required routes absent
        report = pac.check_artifact(meta(), None, expected_pr=986, expected_head=HEAD)
        self.assertEqual(report["verdict"], "UNKNOWN")

    def test_invalid_route_manifest_entry_fails(self):
        self.assertEqual(check(required_routes=["../index.html"])["verdict"], "FAIL")
        self.assertEqual(check(required_routes=["./index.html"])["verdict"], "PASS")

    def test_report_is_json_serialisable(self):
        json.dumps(check(meta(head_sha=OLD), list(FILES) + ["../x"]), ensure_ascii=False)


class ProducerCompatibilityTests(unittest.TestCase):
    """Run the real prepare_pr_preview.py producer and check its output."""

    def test_real_producer_output_conforms(self):
        spec = importlib.util.spec_from_file_location("prepare_pr_preview", ROOT / ".github/pages/prepare_pr_preview.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "concepts/investment-decision-cockpit").mkdir(parents=True)
            (root / "index.html").write_text("<html><body>home</body></html>")
            (root / "concepts/investment-decision-cockpit/index.html").write_text("<html><body>c</body></html>")
            module.prepare_preview(root, owner="sadouninc", repo="Sado-Investment-Lab", ref="pages-previews",
                                   namespace="pr-986", pr_number=986, head_sha=HEAD, built_at="2026-11-28T15:00:00Z")
            rc = pac.main(["--root", str(root), "--expected-pr", "986", "--expected-head", HEAD,
                           "--output", str(root / "report.json")])
            self.assertEqual(rc, 0)
            report = json.loads((root / "report.json").read_text())
            self.assertEqual(report["verdict"], "PASS", report["checks"])
            stale = pac.main(["--root", str(root), "--expected-pr", "986", "--expected-head", OLD,
                              "--output", str(root / "stale.json")])
            self.assertEqual(stale, 0)
            self.assertEqual(json.loads((root / "stale.json").read_text())["verdict"], "FAIL")

    def test_cli_unreadable_metadata_and_escaping_symlink(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            (root / "index.html").write_text("x")
            (root / "preview-metadata.json").write_text("{broken")
            rc = pac.main(["--root", str(root), "--expected-pr", "986", "--expected-head", HEAD,
                           "--output", str(Path(outside) / "r.json")])
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads((Path(outside) / "r.json").read_text())["verdict"], "FAIL")  # routes missing
            (root / "preview-metadata.json").write_text(json.dumps(meta(html_files=1)))
            (root / "concepts/investment-decision-cockpit").mkdir(parents=True)
            (root / "concepts/investment-decision-cockpit/index.html").write_text("c")
            os.symlink(outside, root / "leak")
            files = pac.list_artifact(root)
            self.assertTrue(any(f.startswith("../symlink-rejected/") for f in files))
            report = pac.check_artifact(meta(html_files=2), files, expected_pr=986, expected_head=HEAD)
            self.assertEqual(report["verdict"], "FAIL")
            self.assertIsNone(pac.list_artifact(root / "missing"))


class SymlinkAndRobustnessTests(unittest.TestCase):
    """❤️レイ review 6098961241 counterexamples."""

    def _artifact(self, root: Path) -> None:
        (root / "concepts/investment-decision-cockpit").mkdir(parents=True)
        (root / "index.html").write_text("x")
        (root / "concepts/investment-decision-cockpit/index.html").write_text("c")
        (root / "preview-metadata.json").write_text(json.dumps(meta()))

    def _cli(self, root: Path, out: Path) -> dict:
        rc = pac.main(["--root", str(root), "--expected-pr", "986", "--expected-head", HEAD, "--output", str(out)])
        self.assertEqual(rc, 0)
        return json.loads(out.read_text())

    def test_escaping_metadata_symlink_is_never_read(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            self._artifact(root)
            (root / "preview-metadata.json").unlink()
            (Path(outside) / "meta.json").write_text(json.dumps(meta()))
            os.symlink(Path(outside) / "meta.json", root / "preview-metadata.json")
            self.assertIsNone(pac.read_metadata(root))
            report = self._cli(root, Path(outside) / "r.json")
            self.assertNotEqual(report["verdict"], "PASS")
            self.assertEqual(statuses(report, "metadata"), ["UNKNOWN"])

    def test_dangling_and_internal_symlink_routes_are_not_present(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as out:
            root = Path(tmp)
            self._artifact(root)
            cockpit = root / "concepts/investment-decision-cockpit/index.html"
            cockpit.unlink()
            os.symlink(root / "concepts/missing.html", cockpit)  # dangling, inside root
            report = self._cli(root, Path(out) / "r.json")
            self.assertEqual(report["verdict"], "FAIL")
            self.assertTrue(any("missing route: concepts" in c["detail"] for c in report["checks"]))
            cockpit.unlink()
            os.symlink(root / "index.html", cockpit)  # internal, existing target
            self.assertEqual(self._cli(root, Path(out) / "r2.json")["verdict"], "FAIL")

    def test_symlink_loop_does_not_raise(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as out:
            root = Path(tmp)
            self._artifact(root)
            os.symlink(root / "loop-b", root / "loop-a")
            os.symlink(root / "loop-a", root / "loop-b")
            self.assertEqual(self._cli(root, Path(out) / "r.json")["verdict"], "FAIL")

    def test_walk_errors_make_listing_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._artifact(root)
            real_walk = os.walk

            def failing_walk(top, **kwargs):
                kwargs["onerror"](PermissionError("denied"))
                return real_walk(top, **{k: v for k, v in kwargs.items() if k != "onerror"})

            with unittest.mock.patch.object(pac.os, "walk", side_effect=failing_walk):
                self.assertIsNone(pac.list_artifact(root))
            self.assertIsNone(pac.list_artifact(root / "nope"))
            link = Path(tmp + "-link")
            os.symlink(root, link)
            try:
                self.assertIsNone(pac.list_artifact(link))  # root itself must not be a symlink
            finally:
                link.unlink()

    def test_malformed_or_empty_route_manifest_is_unknown_not_typeerror(self):
        for routes in (None, [], (), "index.html", 5):
            report = check(required_routes=routes)
            self.assertNotEqual(report["verdict"], "PASS", routes)
            self.assertIn("UNKNOWN", statuses(report, "route"), routes)

    def test_deeply_nested_metadata_json_is_unknown(self):
        # Depending on the Python version the decoder either raises
        # RecursionError (-> None) or returns a nested list; both must be
        # handled without an exception and never yield a PASS.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "preview-metadata.json").write_text("[" * 100000 + "]" * 100000)
            metadata = pac.read_metadata(root)
            self.assertNotIsInstance(metadata, dict)
            report = pac.check_artifact(metadata, list(FILES), expected_pr=986, expected_head=HEAD)
            self.assertEqual(report["verdict"], "UNKNOWN")
            self.assertEqual(statuses(report, "metadata"), ["UNKNOWN"])
        with unittest.mock.patch.object(pac.json, "loads", side_effect=RecursionError):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "preview-metadata.json").write_text("{}")
                self.assertIsNone(pac.read_metadata(root))

    def test_namespace_is_explicitly_unknown_when_expectation_malformed(self):
        report = check(expected_pr=0)
        self.assertEqual(statuses(report, "metadata.namespace"), ["UNKNOWN"])


if __name__ == "__main__":
    unittest.main()
