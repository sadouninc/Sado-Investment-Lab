from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.policy_lead_time_defense_drone import (
    DEFAULT_THEME_ID,
    build_defense_drone_policy_lead_time_v2,
)


ROOT = Path(__file__).resolve().parents[1]
THEME_CONFIG = ROOT / "data/config/money-flow-themes-v1.json"


def row(as_of: str, state: str, *, reliable: bool = True) -> dict:
    scores = {
        "relative_strength": 1,
        "activity": 1,
        "breadth": 1,
        "heat": 1,
        "acceleration": 1,
    }
    return {
        "kind": "THEME",
        "id": DEFAULT_THEME_ID,
        "as_of": as_of,
        "state": state,
        "data_completeness": "OK" if reliable else "PARTIAL",
        "scores": scores if reliable else {"relative_strength": 1},
    }


class DefenseDronePolicyLeadTimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.theme_config = json.loads(THEME_CONFIG.read_text(encoding="utf-8"))

    def test_canonical_membership_is_terra_drone_plus_acsl(self):
        payload = build_defense_drone_policy_lead_time_v2(history=[], theme_config=self.theme_config)
        self.assertEqual(
            {member["security_code"] for member in payload["members"]},
            {"278A", "6232"},
        )
        self.assertEqual(payload["membership_authority"], "Issue #259 completed canonical membership")

    def test_pre_listing_checkpoints_fail_closed_as_company_proxy(self):
        history = [row("2026-03-02", "WARMING"), row("2026-05-20", "INFLOW")]
        payload = build_defense_drone_policy_lead_time_v2(history=history, theme_config=self.theme_config)
        first = payload["policy_checkpoints"][0]
        second = payload["policy_checkpoints"][1]
        for checkpoint in (first, second):
            self.assertEqual(checkpoint["phase"], "COMPANY_PROXY_ACSL_ONLY")
            self.assertEqual(checkpoint["evaluation"]["classification"], "DATA_LIMITED")
            self.assertIn("THEME_BREADTH_NOT_AVAILABLE", checkpoint["evaluation"]["limitations"])
            self.assertIn("COMPANY_PROXY_ONLY", checkpoint["evaluation"]["limitations"])

    def test_post_listing_checkpoint_can_identify_reacceleration_with_limitations(self):
        history = [
            row("2026-03-02", "WARMING"),
            row("2026-04-01", "COLD"),
            row("2026-05-20", "WARMING"),
            row("2026-06-10", "INFLOW"),
        ]
        payload = build_defense_drone_policy_lead_time_v2(history=history, theme_config=self.theme_config)
        checkpoint = next(item for item in payload["policy_checkpoints"] if item["date"] == "2026-05-12")
        evaluation = checkpoint["evaluation"]
        self.assertEqual(checkpoint["phase"], "TWO_STOCK_THEME")
        self.assertEqual(evaluation["classification"], "REACCELERATION_AFTER_POLICY")
        self.assertEqual(evaluation["data_quality"], "OK")
        self.assertIn("RETROSPECTIVE_MEMBERSHIP", evaluation["limitations"])
        self.assertIn("NARROW_MEMBERSHIP", evaluation["limitations"])
        self.assertIn("BENCHMARK_PROXY", evaluation["limitations"])

    def test_policy_evidence_never_enters_market_score(self):
        payload = build_defense_drone_policy_lead_time_v2(history=[], theme_config=self.theme_config)
        self.assertFalse(payload["policy_evidence_in_market_score"])
        for checkpoint in payload["policy_checkpoints"]:
            self.assertFalse(checkpoint["evaluation"]["policy_evidence_in_market_score"])


if __name__ == "__main__":
    unittest.main()
