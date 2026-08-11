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

    def test_underpopulated_sector_history_bootstraps_on_main_push(self):
        self.assertIn("EVENT_NAME: ${{ github.event_name }}", self.text)
        self.assertIn("DISTINCT_DATES", self.text)
        self.assertIn("[ \"$DISTINCT_DATES\" -le 1 ]", self.text)
        self.assertIn("echo 'bootstrap_sector_history=true'", self.text)
        self.assertIn("end = datetime.date.today() - datetime.timedelta(days=1)", self.text)
        self.assertIn("start = end - datetime.timedelta(days=8)", self.text)

    def test_bootstrap_uses_resolved_backfill_outputs_for_push_and_manual_runs(self):
        self.assertIn('echo "backfill_start=${BACKFILL_START}" >> "$GITHUB_OUTPUT"', self.text)
        self.assertIn('echo "backfill_end=${BACKFILL_END}" >> "$GITHUB_OUTPUT"', self.text)
        self.assertIn('echo "backfill_start=${BOOTSTRAP_START}" >> "$GITHUB_OUTPUT"', self.text)
        self.assertIn('echo "backfill_end=${BOOTSTRAP_END}" >> "$GITHUB_OUTPUT"', self.text)
        self.assertEqual(
            self.text.count("BACKFILL_START: ${{ steps.mode.outputs.backfill_start }}"),
            2,
        )
        self.assertEqual(
            self.text.count("BACKFILL_END: ${{ steps.mode.outputs.backfill_end }}"),
            2,
        )

    def test_bootstrap_window_is_dynamic_and_trading_dates_remain_runner_owned(self):
        resolve_block = self.text.split("- name: Resolve run mode", 1)[1].split(
            "- name: Run guarded current-session snapshot", 1
        )[0]
        self.assertNotIn("2026-08-03", resolve_block)
        self.assertNotIn("2026-08-10", resolve_block)
        self.assertIn("completed calendar days", resolve_block)
        self.assertIn("benchmark trading dates", resolve_block)

    def test_canonical_refresh_explicitly_dispatches_pages_for_scheduled_and_backfill(self):
        self.assertIn("  actions: write\n", self.text)
        self.assertIn("Refresh Pages after canonical run", self.text)
        self.assertIn(
            "if: steps.mode.outputs.mode == 'BACKFILL' || steps.scheduled.outputs.status == 'COMPLETED'",
            self.text,
        )
        self.assertIn("GH_TOKEN: ${{ github.token }}", self.text)
        self.assertIn("gh workflow run publish-site.yml --ref main", self.text)


if __name__ == "__main__":
    unittest.main()
