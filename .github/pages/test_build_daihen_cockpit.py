from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_daihen_cockpit.py")
SPEC = importlib.util.spec_from_file_location("build_daihen_cockpit", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class DaihenCockpitPageTests(unittest.TestCase):
    def test_model_preserves_partial_stale_and_unavailable_states(self):
        model = MODULE.load_model()
        self.assertEqual(model["security_code"], "6622")
        self.assertEqual(model["overall_status"], "PARTIAL")
        self.assertEqual(model["valuation"]["freshness"], "STALE")
        self.assertEqual(model["expectations"]["status"], "UNAVAILABLE")
        self.assertEqual(model["portfolio_preflight"]["status"], "NOT_RUN")

    def test_page_is_japanese_first_and_surfaces_first_viewport_questions(self):
        page = MODULE.page_content(MODULE.load_model())
        self.assertIn("なぜ今日見る？", page)
        self.assertIn("前回から何が変わった？", page)
        self.assertIn("今の投資仮説は？", page)
        self.assertIn("株価情報が古い場合", page)
        self.assertIn("Consensusを取得できない場合", page)
        self.assertIn("これは売買指示を生成しません", page)

    def test_page_preserves_historical_snapshot_and_no_auto_trade_language(self):
        model = MODULE.load_model()
        snapshot = model["decision_history"]["historical_snapshot_ref"]
        page = MODULE.page_content(model)
        self.assertIn(snapshot, page)
        self.assertIn("過去snapshotを現在のResearch / Valuationで書き換えません", page)
        self.assertNotIn("買い推奨", page)
        self.assertNotIn("売り推奨", page)

    def test_page_uses_canonical_values_without_recalculation(self):
        model = MODULE.load_model()
        page = MODULE.page_content(model)
        self.assertIn("720.10円", page)
        self.assertIn("16.53倍", page)
        self.assertIn("20.81倍", page)
        self.assertIn("14.05倍", page)


if __name__ == "__main__":
    unittest.main()
