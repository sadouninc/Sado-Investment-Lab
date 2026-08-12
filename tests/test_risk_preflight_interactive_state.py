from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / ".github" / "pages" / "build_risk_preflight.py"
WORKFLOW = ROOT / ".github" / "workflows" / "risk-preflight-what-if.yml"


def load_builder():
    spec = importlib.util.spec_from_file_location("build_risk_preflight", BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError("risk-preflight builder could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RiskPreflightInteractiveStateTests(unittest.TestCase):
    def test_panel_exposes_request_scoped_state_bridge_without_secret_storage(self):
        panel = load_builder().interactive_panel()

        for state in ("QUEUED", "RUNNING", "CALCULATED", "FAILED", "EXPIRED"):
            self.assertIn(state, panel)

        self.assertIn("whatif-ui-", panel)
        self.assertIn("display_title.startsWith(prefix)", panel)
        self.assertIn("event=workflow_dispatch", panel)
        self.assertIn("対応するGitHub runを開く", panel)
        self.assertNotIn("localStorage", panel)
        self.assertNotIn("sessionStorage", panel)
        self.assertNotIn("Authorization", panel)
        self.assertNotIn("Bearer ", panel)

    def test_calculated_is_not_presented_as_investment_pass(self):
        panel = load_builder().interactive_panel()
        self.assertIn("投資判断PASSの意味ではありません", panel)
        self.assertIn("result JSONをPages内へ直接取得する機能はこのsliceでは実装せず", panel)

    def test_workflow_run_name_carries_request_identity(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("run-name:", workflow)
        self.assertIn("${{ inputs.request_id }}", workflow)
        self.assertIn("${{ inputs.security_code }}", workflow)
        self.assertIn("${{ inputs.action }}", workflow)

    def test_page_generation_keeps_non_mutation_and_canonical_calculator_boundary(self):
        page = load_builder().page_content()
        self.assertIn("Portfolio、Decision Journal、Execution Intentを変更せず", page)
        self.assertIn("#307 / #233 Python calculatorだけ", page)
        self.assertIn("Pagesにはtoken / secretを保存しません", page)


if __name__ == "__main__":
    unittest.main()
