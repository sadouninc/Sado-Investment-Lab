import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "money-flow-canonical.yml"


class MoneyFlowPushBootstrapContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_main_engine_changes_trigger_existing_canonical_workflow(self):
        self.assertIn("  push:\n    branches:\n      - main\n", self.text)
        for expected_path in (
            "'.github/workflows/money-flow-canonical.yml'",
            "'scripts/money_flow_*.py'",
            "'data/config/money-flow-*.json'",
            "'tests/test_money_flow*.py'",
        ):
            self.assertIn(expected_path, self.text)

    def test_generated_evidence_does_not_retrigger_and_loop(self):
        push_block = self.text.split("  push:\n", 1)[1].split("  schedule:\n", 1)[0]
        self.assertNotIn("data/generated/", push_block)
        self.assertNotIn("sector-history.jsonl", push_block)
        self.assertNotIn("history.jsonl", push_block)

    def test_sector_snapshot_and_persistence_remain_in_same_workflow(self):
        self.assertIn("Run Sector canonical snapshot", self.text)
        self.assertIn("money_flow_sector_canonical_run", self.text)
        self.assertIn("git add data/generated/public/money-flow/sector-history.jsonl", self.text)

    def test_scheduled_refresh_explicitly_dispatches_pages(self):
        self.assertIn("  actions: write\n", self.text)
        self.assertIn("Refresh Pages after canonical scheduled run", self.text)
        self.assertIn("GH_TOKEN: ${{ github.token }}", self.text)
        self.assertIn("gh workflow run publish-site.yml --ref main", self.text)


if __name__ == "__main__":
    unittest.main()
