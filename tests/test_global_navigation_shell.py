from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / ".github" / "pages"

# build_architecture.py is normally executed as a script, where its own directory is
# automatically on sys.path. These tests load it via importlib instead, so mirror the
# real execution environment to make sibling imports such as company_cards available.
if str(PAGES) not in sys.path:
    sys.path.insert(0, str(PAGES))


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


navigation = load_module(PAGES / "navigation.py", "navigation_contract")
build_architecture = load_module(PAGES / "build_architecture.py", "build_architecture")


class GlobalNavigationShellTest(unittest.TestCase):
    def test_fixed_six_purpose_destinations_are_valid(self):
        payload = navigation.load_navigation(PAGES / "navigation-v1.json")
        groups = payload["navigation_groups"]
        self.assertEqual(
            ["Home", "銘柄を探す", "企業を理解する", "判断する", "記録する", "振り返る"],
            [group["label_ja"] for group in groups],
        )
        self.assertEqual(6, len(groups))
        self.assertNotIn("保有・売買", [group["label_ja"] for group in groups])
        self.assertNotIn("売買前確認", [group["label_ja"] for group in groups])
        self.assertTrue(all(group["primary_destination"].startswith("/") for group in groups))
        self.assertTrue(all(group["icon_ja"] for group in groups))

    def test_shell_uses_shared_navigation_data_and_non_color_current_semantics(self):
        shell = build_architecture.GLOBAL_NAVIGATION_SHELL
        self.assertIn("SADO INVESTMENT CODEX", shell)
        self.assertIn("site.data.navigation.navigation_groups", shell)
        self.assertIn("aria-current", shell)
        self.assertIn("data-current", shell)
        self.assertIn("現在地:", shell)
        self.assertNotIn("Investment OS", shell)

    def test_deep_link_resolution_prefers_longest_known_parent(self):
        payload = json.loads((PAGES / "navigation-v1.json").read_text(encoding="utf-8"))

        def group_for(path: str) -> str | None:
            candidates = [
                row for row in payload["routes"]
                if row["availability"] == "AVAILABLE"
                and row.get("route")
                and (path == row["route"] or (row["route"] != "/" and path.startswith(row["route"])))
            ]
            candidates.sort(key=lambda row: len(row["route"]), reverse=True)
            return candidates[0]["primary_journey_stage"] if candidates else None

        self.assertEqual("understand", group_for("/companies/semiconductor/4063-shinetsu/"))
        self.assertEqual("record", group_for("/trade-journal/2026/08/2026-08-04/"))
        self.assertEqual("decide", group_for("/decision-cockpit/daihen/"))

    def test_breadcrumb_shell_uses_route_truth_and_fail_safe_semantics(self):
        shell = build_architecture.GLOBAL_NAVIGATION_SHELL
        self.assertIn('id="codex-global-breadcrumb"', shell)
        self.assertIn('aria-label="現在地"', shell)
        self.assertIn("matchedRoute.breadcrumb_segments_ja", shell)
        self.assertIn("matchedRoute.user_facing_label_ja", shell)
        self.assertIn("pageTitle", shell)
        self.assertIn("label: '未分類'", shell)
        self.assertIn("currentPath !== matchedRoute.route", shell)
        self.assertIn("span.setAttribute('aria-current', 'page')", shell)

    def test_cockpit_has_explicit_japanese_breadcrumb_segments(self):
        payload = navigation.load_navigation(PAGES / "navigation-v1.json")
        cockpit = next(row for row in payload["routes"] if row.get("route") == "/decision-cockpit/daihen/")
        self.assertEqual(["投資判断コックピット", "ダイヘン"], cockpit["breadcrumb_segments_ja"])
        self.assertEqual("decide", cockpit["primary_journey_stage"])

    def test_publish_navigation_shell_is_idempotent(self):
        legacy = """<head>\n  <link rel=\"stylesheet\" href=\"{{ '/assets/book.css' | relative_url }}\">\n</head>\n<body>\n  <header class=\"site-header\">\n    <a>old</a>\n  </header>\n</body>\n"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site_root = root / "site-src"
            layout = site_root / "_layouts" / "site.html"
            layout.parent.mkdir(parents=True)
            layout.write_text(legacy, encoding="utf-8")
            navigation_source = root / "navigation-v1.json"
            navigation_source.write_text((PAGES / "navigation-v1.json").read_text(encoding="utf-8"), encoding="utf-8")

            old_root = build_architecture.SITE_ROOT
            old_layout = build_architecture.SITE_LAYOUT
            old_nav = build_architecture.NAVIGATION_SOURCE
            try:
                build_architecture.SITE_ROOT = site_root
                build_architecture.SITE_LAYOUT = layout
                build_architecture.NAVIGATION_SOURCE = navigation_source
                build_architecture.publish_navigation_shell()
                first = layout.read_text(encoding="utf-8")
                build_architecture.publish_navigation_shell()
                second = layout.read_text(encoding="utf-8")
            finally:
                build_architecture.SITE_ROOT = old_root
                build_architecture.SITE_LAYOUT = old_layout
                build_architecture.NAVIGATION_SOURCE = old_nav

            self.assertEqual(first, second)
            self.assertEqual(1, first.count('class="codex-global-header"'))
            self.assertEqual(1, first.count('id="codex-global-breadcrumb"'))
            self.assertEqual(1, first.count("/assets/design-system.css"))
            self.assertTrue((site_root / "_data" / "navigation.json").is_file())


if __name__ == "__main__":
    unittest.main()
