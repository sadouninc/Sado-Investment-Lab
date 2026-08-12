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
        self.assertIn("What-if入力を開始する", rendered)
        self.assertIn("実行履歴を開く", rendered)
        self.assertNotIn("直近の実行結果を見る", rendered)
        self.assertIn(MODULE.WHAT_IF_WORKFLOW_URL, rendered)
        self.assertIn("GitHubへログインした状態", rendered)
        self.assertIn("Run workflow", rendered)

    def test_daihen_example_and_mobile_steps_are_explicit(self):
        rendered = MODULE.page_content()
        self.assertIn("ダイヘンは <code>6622</code>", rendered)
        self.assertIn("action=<code>BUY</code> / quantity=<code>100</code>", rendered)
        self.assertIn("iPhoneでの確認手順", rendered)
        self.assertIn("Step Summary", rendered)

    def test_owner_first_view_avoids_internal_issue_numbers(self):
        rendered = MODULE.page_content()
        card_start = rendered.index('<div class="content-card">')
        card_end = rendered.index("</div>", card_start)
        first_card = rendered[card_start:card_end]
        self.assertIn("共通計算ロジック", first_card)
        self.assertNotIn("#307", first_card)
        self.assertNotIn("#233", first_card)

    def test_page_preserves_non_mutating_fail_closed_boundary(self):
        rendered = MODULE.page_content()
        self.assertIn("これは注文ではありません", rendered)
        self.assertIn("Portfolio、Decision Journal、Execution Intentを変更せず", rendered)
        self.assertIn("Pages内に別の計算式を持ちません", rendered)
        self.assertIn("NOT_JUDGABLE", rendered)
        self.assertIn("UNKNOWN", rendered)
        self.assertNotIn("github_pat_", rendered)
        self.assertNotIn("ghp_", rendered)


if __name__ == "__main__":
    unittest.main()
