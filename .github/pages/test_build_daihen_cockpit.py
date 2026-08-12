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
        self.assertIn("市場期待との差は？", page)
        self.assertIn("Warning / Thesis Health", page)
        self.assertIn("株価情報が古い場合", page)
        self.assertIn("Consensusを取得できない場合", page)
        self.assertIn("この画面は売買指示を生成しません", page)

    def test_approved_first_view_hierarchy_is_preserved(self):
        page = MODULE.page_content(MODULE.load_model())
        identity = page.index("ダイヘン / 6622")
        delta = page.index("前回から何が変わった？")
        expectations = page.index("市場期待との差は？")
        thesis = page.index("Warning / Thesis Health")
        self.assertLess(identity, delta)
        self.assertLess(delta, expectations)
        self.assertLess(expectations, thesis)
        self.assertIn("情報鮮度:", page)
        self.assertIn("株価基準日:", page)

    def test_unavailable_expectation_is_visible_and_not_coerced_to_zero_gap(self):
        page = MODULE.page_content(MODULE.load_model())
        self.assertIn("市場期待データは現在取得できません。差なし・0として扱いません。", page)
        self.assertIn("現在取得できません <code>UNAVAILABLE</code>", page)
        self.assertNotIn("gap=0", page.split("## 3. 市場期待との差", 1)[0])

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

    def test_scenario_delta_is_in_first_view_and_reuses_read_model(self):
        model = MODULE.load_model()
        delta = MODULE._scenario_delta(model)
        page = MODULE.page_content(model)
        self.assertEqual(delta.current.eps, 720.1)
        self.assertEqual(delta.current.forward_per, 16.53)
        self.assertIn("Scenario: UNKNOWN", page)
        self.assertIn("業績見通し", page)
        self.assertIn("Valuation余地", page)
        self.assertIn("Previous / Current の詳細値", page)
        self.assertIn("progressive-disclosure", page)
        self.assertIn("delta-indicator", page)

    def test_missing_previous_snapshot_fails_closed_instead_of_reconstructing_history(self):
        model = MODULE.load_model()
        delta = MODULE._scenario_delta(model)
        self.assertEqual(delta.previous.scenario, "UNKNOWN")
        self.assertIsNone(delta.previous.eps)
        self.assertIsNone(delta.previous.price)
        self.assertIsNone(delta.previous.forward_per)
        self.assertEqual(delta.earnings_direction, "UNKNOWN")
        self.assertEqual(delta.valuation_direction, "UNKNOWN")
        page = MODULE.page_content(model)
        self.assertIn("前回との差分を確定するための情報が不足しています。", page)
        self.assertIn("現在値から過去値を逆算しません", page)
        self.assertIn(model["decision_history"]["comparison_ref"], page)


if __name__ == "__main__":
    unittest.main()
