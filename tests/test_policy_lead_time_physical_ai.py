from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.policy_lead_time_physical_ai import (
    DEFAULT_THEME_ID,
    POLICY_CHECKPOINTS,
    build_physical_ai_policy_lead_time_v2,
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


class PhysicalAIPolicyLeadTimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.theme_config = json.loads(THEME_CONFIG.read_text(encoding="utf-8"))

    def test_uses_pr1_canonical_membership(self):
        payload = build_physical_ai_policy_lead_time_v2(history=[], theme_config=self.theme_config)
        self.assertEqual(
            {member["security_code"] for member in payload["members"]},
            {"6954", "6506", "6324", "6268", "6481"},
        )
        self.assertIn("Issue #394", payload["membership_authority"])

    def test_policy_checkpoints_are_deterministic_and_sourced(self):
        payload = build_physical_ai_policy_lead_time_v2(history=[], theme_config=self.theme_config)
        self.assertEqual(
            [checkpoint[0] for checkpoint in POLICY_CHECKPOINTS],
            [checkpoint["date"] for checkpoint in payload["policy_checkpoints"]],
        )
        for checkpoint in payload["policy_checkpoints"]:
            self.assertTrue(checkpoint["source_ref"].startswith("https://"))

    def test_reacceleration_after_policy_is_detected_with_proxy_limitations(self):
        history = [
            row("2026-03-02", "WARMING"),
            row("2026-04-01", "COLD"),
            row("2026-06-02", "WARMING"),
            row("2026-06-10", "INFLOW"),
        ]
        payload = build_physical_ai_policy_lead_time_v2(history=history, theme_config=self.theme_config)
        checkpoint = next(item for item in payload["policy_checkpoints"] if item["date"] == "2026-05-27")
        evaluation = checkpoint["evaluation"]
        self.assertEqual(evaluation["classification"], "REACCELERATION_AFTER_POLICY")
        self.assertEqual(evaluation["data_quality"], "OK")
        self.assertIn("RETROSPECTIVE_MEMBERSHIP", evaluation["limitations"])
        self.assertIn("THEME_SCOPE_PROXY", evaluation["limitations"])
        self.assertIn("BENCHMARK_PROXY", evaluation["limitations"])

    def test_no_reliable_signal_fails_closed(self):
        payload = build_physical_ai_policy_lead_time_v2(
            history=[row("2026-06-02", "WARMING", reliable=False)],
            theme_config=self.theme_config,
        )
        evaluation = payload["policy_checkpoints"][0]["evaluation"]
        self.assertEqual(evaluation["classification"], "DATA_LIMITED")
        self.assertIn("RELIABLE_MARKET_SIGNAL_NOT_OBSERVED", evaluation["limitations"])

    def test_policy_evidence_never_enters_market_score(self):
        payload = build_physical_ai_policy_lead_time_v2(history=[], theme_config=self.theme_config)
        self.assertFalse(payload["policy_evidence_in_market_score"])
        for checkpoint in payload["policy_checkpoints"]:
            self.assertFalse(checkpoint["evaluation"]["policy_evidence_in_market_score"])


if __name__ == "__main__":
    unittest.main()
