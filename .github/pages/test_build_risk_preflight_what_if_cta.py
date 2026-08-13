from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_risk_preflight.py")
SPEC = importlib.util.spec_from_file_location("build_risk_preflight", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class RiskPreflightWhatIfCtaTests(unittest.TestCase):
    def test_page_links_to_authenticated_canonical_runner(self):
        rendered = MODULE.page_content()
        self.assertIn("売買前のPF影響を確認する", rendered)
        self.assertIn("PF影響の確認を準備", rendered)
        self.assertIn("GitHub Actionsで計算を実行", rendered)
        self.assertIn("このRequestを追跡", rendered)
        self.assertIn(MODULE.WHAT_IF_WORKFLOW_URL, rendered)
        self.assertIn("GitHub Actions", rendered)

    def test_mobile_flow_keeps_explicit_input_and_result_handoff(self):
        rendered = MODULE.page_content()
        self.assertIn("対象 / BUY・SELL / 数量 / 価格 / 口座文脈", rendered)
        self.assertIn("入力した仮定", rendered)
        self.assertIn("Step Summary", rendered)
        self.assertIn("Before → After / Rule / Data status", rendered)
        self.assertIn("条件を修正", rendered)

    def test_owner_first_view_prioritizes_trade_assumption_over_diagnostics(self):
        panel = MODULE.interactive_panel()
        input_index = panel.index("対象銘柄コード")
        diagnostics_index = panel.index("実行・診断情報")
        self.assertLess(input_index, diagnostics_index)
        self.assertIn("BUY / SELLは入力する仮定であり推奨ではありません", panel)
        self.assertIn("これは注文ではありません", panel)
        self.assertIn("Request ID", panel[diagnostics_index:])

    def test_polling_budget_and_client_failures_are_separated(self):
        panel = MODULE.interactive_panel()
        self.assertIn("const POLL_MS = 60000", panel)
        self.assertIn("RATE_LIMITED", panel)
        self.assertIn("CLIENT_ERROR", panel)
        self.assertIn("X-RateLimit-Remaining", panel)
        self.assertIn("X-RateLimit-Reset", panel)
        self.assertIn("response.status === 403", panel)
        self.assertIn("response.status === 429", panel)
        self.assertIn("setState('CLIENT_ERROR')", panel)
        self.assertIn("setState('RATE_LIMITED')", panel)
        self.assertIn("FAILED: '対応run自体が失敗", panel)

    def test_page_preserves_non_mutating_fail_closed_boundary(self):
        rendered = MODULE.page_content()
        self.assertIn("これは注文ではありません", rendered)
        self.assertIn("Portfolio、Decision Journal、Execution Intentを変更せず", rendered)
        self.assertIn("Pages内に別のrisk計算式を持ちません", rendered)
        self.assertIn("NOT_JUDGABLE", rendered)
        self.assertIn("UNKNOWN", rendered)
        self.assertIn("CALCULATED", rendered)
        self.assertIn("投資判断", rendered)
        self.assertNotIn("github_pat_", rendered)
        self.assertNotIn("ghp_", rendered)
        self.assertNotIn("Authorization", rendered)


if __name__ == "__main__":
    unittest.main()
