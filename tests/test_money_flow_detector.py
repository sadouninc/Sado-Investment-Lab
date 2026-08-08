from __future__ import annotations

import unittest
from datetime import date

from scripts.money_flow_detector import evaluate_snapshot


CONFIG = {
    "schema_version": 1,
    "required_axes": ["relative_strength", "activity", "breadth", "heat", "acceleration"],
    "weights": {
        "relative_strength": 0.30,
        "activity": 0.20,
        "breadth": 0.25,
        "acceleration": 0.25,
    },
    "thresholds": {
        "warming_score": 55,
        "inflow_score": 70,
        "hot_score": 82,
        "overheated_heat": 85,
        "max_heat_for_warming": 70,
        "max_heat_for_inflow": 80,
    },
    "hysteresis": {"promote_days": 2, "demote_days": 2},
    "minimum_non_null_axes": 4,
}


def raw(scores, **extra):
    payload = {
        "id": "theme:gaming",
        "name": "Gaming",
        "kind": "THEME",
        "scores": scores,
        "previous_state": "COLD",
        "prior_target_state": None,
        "target_streak": 0,
        "member_count": 8,
        "membership_as_of": "2026-08-08",
    }
    payload.update(extra)
    return payload


class MoneyFlowDetectorTests(unittest.TestCase):
    def test_cold_to_warming_requires_two_days(self):
        scores = {"relative_strength": 60, "activity": 58, "breadth": 62, "heat": 45, "acceleration": 70}
        first = evaluate_snapshot(raw(scores), config=CONFIG, as_of=date(2026, 8, 8))
        self.assertEqual(first["target_state"], "WARMING")
        self.assertEqual(first["state"], "COLD")
        second = evaluate_snapshot(
            raw(scores, previous_state="COLD", prior_target_state="WARMING", target_streak=1),
            config=CONFIG,
            as_of=date(2026, 8, 9),
        )
        self.assertEqual(second["state"], "WARMING")
        self.assertTrue(second["selection_signal"])

    def test_warming_to_inflow_requires_persistence(self):
        scores = {"relative_strength": 75, "activity": 72, "breadth": 76, "heat": 60, "acceleration": 78}
        first = evaluate_snapshot(
            raw(scores, previous_state="WARMING"), config=CONFIG, as_of=date(2026, 8, 8)
        )
        self.assertEqual(first["state"], "WARMING")
        second = evaluate_snapshot(
            raw(scores, previous_state="WARMING", prior_target_state="INFLOW", target_streak=1),
            config=CONFIG,
            as_of=date(2026, 8, 9),
        )
        self.assertEqual(second["state"], "INFLOW")
        self.assertTrue(second["selection_signal"])

    def test_one_day_spike_is_not_warming(self):
        scores = {"relative_strength": 90, "activity": 95, "breadth": 82, "heat": 68, "acceleration": 98}
        result = evaluate_snapshot(raw(scores), config=CONFIG, as_of=date(2026, 8, 9))
        self.assertNotEqual(result["state"], "WARMING")
        self.assertFalse(result["selection_signal"])

    def test_hot_and_overheated_are_distinct_from_early_signal(self):
        hot = {"relative_strength": 90, "activity": 85, "breadth": 88, "heat": 80, "acceleration": 82}
        r1 = evaluate_snapshot(
            raw(hot, previous_state="INFLOW", prior_target_state="HOT", target_streak=1),
            config=CONFIG,
            as_of=date(2026, 8, 9),
        )
        self.assertEqual(r1["state"], "HOT")
        self.assertFalse(r1["selection_signal"])

        over = {"relative_strength": 80, "activity": 88, "breadth": 85, "heat": 92, "acceleration": 75}
        r2 = evaluate_snapshot(
            raw(over, previous_state="HOT", prior_target_state="OVERHEATED", target_streak=1),
            config=CONFIG,
            as_of=date(2026, 8, 9),
        )
        self.assertEqual(r2["state"], "OVERHEATED")
        self.assertFalse(r2["selection_signal"])

    def test_missing_data_is_not_zero_scored(self):
        scores = {"relative_strength": 65, "activity": None, "breadth": None, "heat": 40, "acceleration": 70}
        result = evaluate_snapshot(raw(scores), config=CONFIG, as_of=date(2026, 8, 9))
        self.assertEqual(result["data_completeness"], "INSUFFICIENT")
        self.assertIsNone(result["scores"]["activity"])
        self.assertFalse(result["selection_signal"])

    def test_hysteresis_prevents_one_day_downgrade(self):
        cold = {"relative_strength": 30, "activity": 35, "breadth": 32, "heat": 30, "acceleration": 28}
        first = evaluate_snapshot(
            raw(cold, previous_state="WARMING"), config=CONFIG, as_of=date(2026, 8, 8)
        )
        self.assertEqual(first["state"], "WARMING")
        second = evaluate_snapshot(
            raw(cold, previous_state="WARMING", prior_target_state="COLD", target_streak=1),
            config=CONFIG,
            as_of=date(2026, 8, 9),
        )
        self.assertEqual(second["state"], "COLD")

    def test_sector_and_theme_share_interface(self):
        scores = {"relative_strength": 60, "activity": 58, "breadth": 62, "heat": 45, "acceleration": 70}
        theme = evaluate_snapshot(raw(scores), config=CONFIG, as_of=date(2026, 8, 9))
        sector_input = raw(scores, id="sector:electrical", name="Electric Appliances", kind="SECTOR")
        sector = evaluate_snapshot(sector_input, config=CONFIG, as_of=date(2026, 8, 9))
        self.assertEqual(set(theme), set(sector))
        self.assertEqual(sector["kind"], "SECTOR")


if __name__ == "__main__":
    unittest.main()
