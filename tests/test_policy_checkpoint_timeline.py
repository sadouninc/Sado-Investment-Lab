from __future__ import annotations

import copy
import unittest

from scripts.policy_checkpoint_timeline import (
    PolicyCheckpointTimelineError,
    build_policy_checkpoint_timeline,
)


THEME = "theme:ai-data-center-power-infrastructure"


def _row(as_of: str, state: str, *, completeness: str = "OK") -> dict:
    return {
        "kind": "THEME",
        "id": THEME,
        "as_of": as_of,
        "state": state,
        "data_completeness": completeness,
        "scores": {
            "relative_strength": 1,
            "activity": 1,
            "breadth": 1,
            "heat": 1,
            "acceleration": 1,
        },
    }


class PolicyCheckpointTimelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.history = [
            _row("2024-09-26", "INFLOW", completeness="PARTIAL"),
            _row("2024-10-03", "COLD"),
            _row("2024-11-06", "WARMING"),
            _row("2024-11-08", "INFLOW"),
            _row("2025-03-17", "COLD"),
            _row("2025-03-20", "WARMING"),
            _row("2025-03-24", "INFLOW"),
        ]
        self.checkpoints = [
            {
                "checkpoint_id": "watt-bit-forum",
                "policy_t0": "2025-03-18",
                "stage": "POLICY_CONFIRMATION",
            },
            {
                "checkpoint_id": "early-policy-signal",
                "policy_t0": "2024-10-04",
                "stage": "EARLY_SIGNAL",
                "limitations": ["retrospective_membership"],
            },
        ]

    def test_multiple_checkpoints_are_sorted_and_projected(self):
        result = build_policy_checkpoint_timeline(
            history=self.history,
            checkpoints=self.checkpoints,
            theme_id=THEME,
        )
        rows = result["checkpoints"]
        self.assertEqual([row["checkpoint_id"] for row in rows], ["early-policy-signal", "watt-bit-forum"])
        self.assertEqual(rows[0]["next_reliable_warming"], "2024-11-06")
        self.assertEqual(rows[0]["next_reliable_warming_days"], 33)
        self.assertEqual(rows[0]["next_reliable_inflow"], "2024-11-08")
        self.assertEqual(rows[0]["next_reliable_inflow_days"], 35)
        self.assertEqual(rows[0]["limitations"], ["RETROSPECTIVE_MEMBERSHIP"])
        self.assertEqual(rows[1]["next_reliable_warming"], "2025-03-20")
        self.assertEqual(rows[1]["next_reliable_warming_days"], 2)
        self.assertEqual(rows[1]["next_reliable_inflow"], "2025-03-24")
        self.assertEqual(rows[1]["next_reliable_inflow_days"], 6)

    def test_state_at_checkpoint_is_observed_state_not_policy_score(self):
        result = build_policy_checkpoint_timeline(
            history=self.history,
            checkpoints=self.checkpoints,
            theme_id=THEME,
        )
        first = result["checkpoints"][0]
        self.assertEqual(first["market_state_at_checkpoint"]["state"], "COLD")
        self.assertFalse(result["policy_evidence_in_market_score"])

    def test_partial_signal_is_not_promoted_to_reliable(self):
        result = build_policy_checkpoint_timeline(
            history=self.history,
            checkpoints=[{"checkpoint_id": "pre", "policy_t0": "2024-09-25"}],
            theme_id=THEME,
        )
        row = result["checkpoints"][0]
        self.assertEqual(row["next_reliable_warming"], "2024-11-06")
        self.assertEqual(row["next_reliable_inflow"], "2024-11-08")

    def test_missing_future_signal_stays_none(self):
        result = build_policy_checkpoint_timeline(
            history=self.history,
            checkpoints=[{"checkpoint_id": "future", "policy_t0": "2026-01-01"}],
            theme_id=THEME,
        )
        row = result["checkpoints"][0]
        self.assertIsNone(row["next_reliable_warming"])
        self.assertIsNone(row["next_reliable_warming_days"])
        self.assertIsNone(row["next_reliable_inflow"])
        self.assertIsNone(row["next_reliable_inflow_days"])

    def test_duplicate_checkpoint_identity_fails_closed(self):
        with self.assertRaises(PolicyCheckpointTimelineError):
            build_policy_checkpoint_timeline(
                history=self.history,
                checkpoints=[
                    {"checkpoint_id": "same", "policy_t0": "2024-10-04"},
                    {"checkpoint_id": "same", "policy_t0": "2025-03-18"},
                ],
                theme_id=THEME,
            )

    def test_deterministic_and_non_mutating(self):
        history = copy.deepcopy(self.history)
        checkpoints = copy.deepcopy(self.checkpoints)
        first = build_policy_checkpoint_timeline(history=history, checkpoints=checkpoints, theme_id=THEME)
        second = build_policy_checkpoint_timeline(history=history, checkpoints=checkpoints, theme_id=THEME)
        self.assertEqual(first, second)
        self.assertEqual(history, self.history)
        self.assertEqual(checkpoints, self.checkpoints)


if __name__ == "__main__":
    unittest.main()
