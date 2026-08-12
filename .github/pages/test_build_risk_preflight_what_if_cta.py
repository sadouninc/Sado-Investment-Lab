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
        self.assertIn("実際にWhat-ifを確認する", rendered)
        self.assertIn("Request IDを発行", rendered)
        self.assertIn("GitHub ActionsでWhat-ifを実行", rendered)
        self.assertIn("このRequestを追跡", rendered)
        self.assertIn(MODULE.WHAT_IF_WORKFLOW_URL, rendered)
        self.assertIn("GitHub Actions", rendered)
        self.assertIn("Run workflow", rendered)

    def test_mobile_steps_keep_explicit_input_and_result_handoff(self):
        rendered = MODULE.page_content()
        self.assertIn("request_id", rendered)
        self.assertIn("銘柄コード / BUY・SELL / 株数 / 価格", rendered)
        self.assertIn("iPhoneでの確認手順", rendered)
        self.assertIn("Step Summary", rendered)
        self.assertIn("対応するGitHub run", rendered)

    def test_owner_first_view_prioritizes_request_flow_over_internal_metadata(self):
        panel = MODULE.interactive_panel()
        self.assertIn("一意なRequest ID", panel)
        self.assertIn("そのrequestだけを追跡", panel)
        self.assertNotIn("既存 #307 / #233", panel.split("**実装境界:**", 1)[0])

    def test_page_preserves_non_mutating_fail_closed_boundary(self):
        rendered = MODULE.page_content()
        self.assertIn("これは注文ではありません", rendered)
        self.assertIn("Portfolio、Decision Journal、Execution Intentを変更せず", rendered)
        self.assertIn("Pages内に別の計算式を持ちません", rendered)
        self.assertIn("NOT_JUDGABLE", rendered)
        self.assertIn("UNKNOWN", rendered)
        self.assertIn("CALCULATED", rendered)
        self.assertIn("投資判断", rendered)
        self.assertNotIn("github_pat_", rendered)
        self.assertNotIn("ghp_", rendered)
        self.assertNotIn("Authorization", rendered)


if __name__ == "__main__":
    unittest.main()
