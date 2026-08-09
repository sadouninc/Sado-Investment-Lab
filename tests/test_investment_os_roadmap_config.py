from __future__ import annotations

import copy
import unittest
from pathlib import Path

from scripts.roadmap.config import load_roadmap_config, validate_roadmap_config


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "data" / "config" / "investment-os-roadmap-v1.json"


class InvestmentOSRoadmapConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_roadmap_config(CONFIG_PATH)

    def test_stage_zero_through_seven_are_present_in_order(self) -> None:
        self.assertEqual([f"stage_{i}" for i in range(8)], [stage["id"] for stage in self.config["stages"]])

    def test_related_issue_mapping_contains_core_investment_os_issues(self) -> None:
        all_issues = {issue for stage in self.config["stages"] for issue in stage["related_issues"]}
        for issue in (108, 112, 113, 117, 130, 131, 133, 135, 141, 144, 151, 152):
            self.assertIn(issue, all_issues)

    def test_done_condition_ids_are_globally_unique(self) -> None:
        ids = [condition["id"] for stage in self.config["stages"] for condition in stage["done_conditions"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_unknown_stage_key_is_rejected(self) -> None:
        payload = copy.deepcopy(self.config)
        payload["stages"][0]["manual_progress"] = 100
        with self.assertRaises(ValueError):
            validate_roadmap_config(payload)

    def test_future_stage_dependency_is_rejected(self) -> None:
        payload = copy.deepcopy(self.config)
        payload["stages"][2]["entry_conditions"] = ["stage_3"]
        with self.assertRaises(ValueError):
            validate_roadmap_config(payload)

    def test_duplicate_done_condition_is_rejected(self) -> None:
        payload = copy.deepcopy(self.config)
        payload["stages"][1]["done_conditions"][0]["id"] = payload["stages"][0]["done_conditions"][0]["id"]
        with self.assertRaises(ValueError):
            validate_roadmap_config(payload)

    def test_manual_current_stage_is_not_part_of_config_contract(self) -> None:
        self.assertNotIn("current_stage", self.config)
        self.assertNotIn("primary_current_stage", self.config)


if __name__ == "__main__":
    unittest.main()
