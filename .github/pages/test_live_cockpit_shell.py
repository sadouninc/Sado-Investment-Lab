from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("live_cockpit_shell.py")
SPEC = importlib.util.spec_from_file_location("live_cockpit_shell", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class LiveCockpitShellTests(unittest.TestCase):
    def _view(self, **overrides):
        data = {
            "company_name": "テスト電機",
            "security_code": "9999",
            "freshness_html": "情報が古いため再確認が必要 <code>STALE</code>",
            "price_as_of": "2026-08-11",
            "decision_delta_html": '<div class="content-card scenario-delta-summary">前回から何が変わった？ UNKNOWN</div>',
            "expectation_html": '<div class="content-card cockpit-expectation-summary">市場期待データは現在取得できません UNAVAILABLE</div>',
            "thesis_health": "UNKNOWN",
            "hypothesis_status_html": "鮮度を確認できません <code>UNKNOWN</code>",
            "warning_count": 2,
        }
        data.update(overrides)
        return MODULE.LiveCockpitFirstView(**data)

    def test_shell_is_company_agnostic_and_preserves_approved_order(self):
        rendered = MODULE.render_first_view(self._view())
        identity = rendered.index("テスト電機 / 9999")
        delta = rendered.index("前回から何が変わった？")
        expectation = rendered.index("市場期待データは現在取得できません")
        thesis = rendered.index("Warning / Thesis Health")
        self.assertLess(identity, delta)
        self.assertLess(delta, expectation)
        self.assertLess(expectation, thesis)
        self.assertNotIn("ダイヘン", rendered)
        self.assertNotIn("6622", rendered)

    def test_shell_preserves_fail_closed_semantics_without_trade_inference(self):
        rendered = MODULE.render_first_view(self._view())
        self.assertIn("STALE", rendered)
        self.assertIn("UNAVAILABLE", rendered)
        self.assertIn("UNKNOWN", rendered)
        self.assertNotIn("BUY", rendered)
        self.assertNotIn("SELL", rendered)
        self.assertNotIn("HOLD", rendered)

    def test_missing_identity_fields_are_explicit_not_fabricated(self):
        rendered = MODULE.render_first_view(
            self._view(company_name="", security_code="", price_as_of="", thesis_health="")
        )
        self.assertIn("対象企業を取得できません / UNKNOWN", rendered)
        self.assertIn("株価基準日: 取得できません", rendered)
        self.assertIn("Health: <code>取得できません</code>", rendered)


if __name__ == "__main__":
    unittest.main()
