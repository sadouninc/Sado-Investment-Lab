from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / ".github/pages/build_risk_preflight.py"


class RiskPreflightRuntimeCtaContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = BUILDER.read_text(encoding="utf-8")

    def test_pages_links_to_authenticated_canonical_workflow(self):
        self.assertIn("actions/workflows/risk-preflight-what-if.yml", self.text)
        self.assertIn("What-if入力を開く", self.text)
        self.assertIn("Run workflow", self.text)

    def test_pages_does_not_claim_direct_order_or_canonical_save(self):
        self.assertIn("これは注文ではありません", self.text)
        self.assertIn("Decision / Execution Intentへ自動保存されません", self.text)

    def test_incomplete_runtime_state_is_fail_closed(self):
        self.assertIn("QUEUED / RUNNING", self.text)
        self.assertIn("artifact未生成は計算完了として扱いません", self.text)
        self.assertIn("7日で期限切れ", self.text)


if __name__ == "__main__":
    unittest.main()
