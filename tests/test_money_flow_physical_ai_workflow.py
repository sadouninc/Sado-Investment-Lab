from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/money-flow-canonical.yml"
GITIGNORE = ROOT / ".gitignore"
THEME_ID = "theme:physical-ai-robotics-core"
BASE_OUTPUT = "data/generated/public/money-flow/policy-lead-time-physical-ai.json"
V2_OUTPUT = "data/generated/public/money-flow/policy-lead-time-physical-ai-v2.json"


class PhysicalAIWorkflowRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.gitignore = GITIGNORE.read_text(encoding="utf-8")

    def test_manual_selector_exposes_physical_ai_without_changing_default(self) -> None:
        self.assertIn("default: 'theme:ai-data-center-power-infrastructure'", self.workflow)
        self.assertIn(f"- '{THEME_ID}'", self.workflow)

    def test_physical_ai_routes_to_dedicated_artifacts(self) -> None:
        self.assertIn(f"{THEME_ID})", self.workflow)
        self.assertIn(f"LEAD_TIME_OUTPUT='{BASE_OUTPUT}'", self.workflow)
        self.assertIn(f"V2_OUTPUT='{V2_OUTPUT}'", self.workflow)
        self.assertIn("python -m scripts.policy_lead_time_physical_ai", self.workflow)

    def test_physical_ai_artifacts_are_trackable(self) -> None:
        self.assertIn(f"!{BASE_OUTPUT}", self.gitignore)
        self.assertIn(f"!{V2_OUTPUT}", self.gitignore)

    def test_sector_backfill_remains_ai_dc_only(self) -> None:
        sector_condition = "steps.mode.outputs.theme_id == 'theme:ai-data-center-power-infrastructure'"
        self.assertGreaterEqual(self.workflow.count(sector_condition), 2)
        self.assertNotIn(
            "steps.mode.outputs.theme_id == 'theme:physical-ai-robotics-core' && steps.mode.outputs.mode == 'SECTOR_BOOTSTRAP'",
            self.workflow,
        )

    def test_future_leak_guard_is_preserved_by_reusing_bounded_backfill(self) -> None:
        self.assertIn("python -m scripts.money_flow_canonical_run", self.workflow)
        self.assertIn("--backfill-range 2y", self.workflow)
        self.assertIn("--theme-id '${{ steps.mode.outputs.theme_id }}'", self.workflow)


if __name__ == "__main__":
    unittest.main()
