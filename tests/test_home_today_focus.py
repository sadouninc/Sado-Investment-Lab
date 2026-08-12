from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / ".github" / "pages" / "enrich_home_focus.py"
CSS_PATH = ROOT / "assets" / "images" / "home-os-map.css"
SPEC = importlib.util.spec_from_file_location("home_focus", MODULE_PATH)
assert SPEC and SPEC.loader
home_focus = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = home_focus
SPEC.loader.exec_module(home_focus)


class HomeTodayFocusTest(unittest.TestCase):
    def dataset(self, status="OK"):
        return {
            "source_status": [{"name": "watchlist", "status": status, "as_of": "2026-08-12"}],
            "watchlist": {
                "items": [
                    {"text": "ダイヘンの次決算を確認", "reason": "受注から利益への転換を見る", "priority": None},
                    {"text": "富士電機の受注を確認", "reason": "DC電源需要を見る", "priority": None},
                    {"text": "SWCCの増産効果を確認", "reason": "海外通信ケーブルを見る", "priority": None},
                    {"text": "4件目", "reason": "表示上限外", "priority": None},
                ]
            },
        }

    def test_projection_preserves_source_order_and_caps_at_three(self):
        projection = home_focus.project_today_focus(self.dataset())
        self.assertEqual([row["text"] for row in projection["items"]], [
            "ダイヘンの次決算を確認", "富士電機の受注を確認", "SWCCの増産効果を確認"
        ])
        self.assertEqual(projection["status"], "OK")

    def test_stale_is_visible_and_not_promoted_to_current(self):
        rendered = home_focus.render_today_focus(self.dataset("STALE"))
        self.assertIn("情報が古い / STALE", rendered)
        self.assertIn("STALEを現在の優先順位へ昇格せず", rendered)
        self.assertIn("ダイヘンの次決算を確認", rendered)
        self.assertNotIn("4件目", rendered)

    def test_missing_fails_closed(self):
        rendered = home_focus.render_today_focus(None)
        self.assertIn("取得できません / MISSING", rendered)
        self.assertIn("Morning Datasetを取得できません", rendered)

    def test_focus_actions_have_contextual_accessible_names(self):
        rendered = home_focus.render_today_focus(self.dataset())
        self.assertIn('aria-label="ダイヘンの次決算を確認の根拠をMorning Datasetで確認する"', rendered)
        self.assertIn('aria-label="富士電機の受注を確認の根拠をMorning Datasetで確認する"', rendered)
        self.assertIn('aria-label="SWCCの増産効果を確認の根拠をMorning Datasetで確認する"', rendered)

    def test_mobile_focus_is_single_column_tap_safe_and_no_horizontal_scroll(self):
        css = CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".home-today-focus-grid", css)
        mobile = css.split("@media (max-width: 640px)", 1)[1]
        self.assertIn(".home-today-focus-grid", mobile)
        self.assertIn("grid-template-columns: 1fr", mobile)
        self.assertIn("min-height: 2.75rem", mobile)
        self.assertNotIn("overflow-x: auto", mobile)

    def test_focus_cards_allow_long_labels_without_overflow(self):
        css = CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".home-today-focus-grid .codex-summary-card", css)
        self.assertIn("overflow-wrap: anywhere", css)
        self.assertIn("min-width: 0", css)

    def test_enrichment_places_focus_before_map_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "index.md"
            path.write_text("before\n" + home_focus.MAP_MARKER + "\nafter\n", encoding="utf-8")
            home_focus.enrich_home_focus(self.dataset(), home_path=path)
            once = path.read_text(encoding="utf-8")
            home_focus.enrich_home_focus(self.dataset(), home_path=path)
            twice = path.read_text(encoding="utf-8")
            self.assertEqual(once, twice)
            self.assertLess(once.index("today-focus-title"), once.index("map-title"))
            self.assertIn("最大3件", once)
            self.assertIn("Home独自のscore・ranking", once)


if __name__ == "__main__":
    unittest.main()
