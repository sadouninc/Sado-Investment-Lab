from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BUILDER = _load("build_daihen_cockpit_for_link_test", "build_daihen_cockpit.py")
ENHANCER = _load("enhance_daihen_cockpit_links", "enhance_daihen_cockpit_links.py")


class DaihenCockpitLinkTests(unittest.TestCase):
    def test_adds_only_known_stable_research_route(self):
        model = BUILDER.load_model()
        page = ENHANCER.enhance_page(BUILDER.page_content(model), model)
        self.assertIn("## 🔎 根拠へ降りる", page)
        self.assertIn("/companies/infrastructure/6622-daihen/", page)
        self.assertIn("Forward PER専用ページはまだありません", page)
        self.assertIn("仮説専用ページはまだありません", page)
        self.assertIn("Decision History専用ページはまだありません", page)

    def test_does_not_guess_unpublished_routes(self):
        model = BUILDER.load_model()
        page = ENHANCER.enhance_page(BUILDER.page_content(model), model)
        self.assertNotIn("/forward-per/6622", page)
        self.assertNotIn("/hypothesis/6622", page)
        self.assertNotIn("/decision-history/6622", page)

    def test_enhancement_is_idempotent(self):
        model = BUILDER.load_model()
        original = BUILDER.page_content(model)
        once = ENHANCER.enhance_page(original, model)
        twice = ENHANCER.enhance_page(once, model)
        self.assertEqual(once, twice)
        self.assertEqual(once.count(ENHANCER.START), 1)
        self.assertEqual(once.count(ENHANCER.END), 1)

    def test_historical_snapshot_remains_visible(self):
        model = BUILDER.load_model()
        page = ENHANCER.enhance_page(BUILDER.page_content(model), model)
        self.assertIn(model["decision_history"]["historical_snapshot_ref"], page)


if __name__ == "__main__":
    unittest.main()
