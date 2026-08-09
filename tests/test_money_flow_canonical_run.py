from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from scripts.money_flow_canonical_run import (
    DEFAULT_THEME_ID,
    canonical_snapshot,
    evaluate_policy_lead_time,
    persist_canonical_snapshot,
)
from scripts.money_flow_history import load_history


DETECTOR_CONFIG = {
    "schema_version": 1,
    "required_axes": ["relative_strength", "activity", "breadth", "heat", "acceleration"],
    "weights": {"relative_strength": 0.30, "activity": 0.20, "breadth": 0.25, "acceleration": 0.25},
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

SECTOR_CONFIG = {
    "windows": {"short": 5, "medium": 20, "long": 60, "activity_short": 5, "activity_baseline": 20},
    "scoring": {
        "relative_strength_points_per_pct": 4.0,
        "acceleration_points_per_pct": 4.0,
        "activity_points_per_ratio": 40.0,
        "heat_points_per_pct": 3.0,
    },
}

THEME_CONFIG = {
    "benchmark": {"name": "TOPIX", "symbol": "^TOPX"},
    "history_range": "6mo",
    "interval": "1d",
    "themes": [
        {
            "id": DEFAULT_THEME_ID,
            "name": "AI Data Center / Power Infrastructure",
            "membership_as_of": "2026-08-09",
            "membership_version": "2026-08-09-v1",
            "backfill_policy": "RETROSPECTIVE_MEMBERSHIP_IF_HISTORICAL_MEMBERSHIP_UNAVAILABLE",
            "members": [
                {"security_code": "6622", "company_name": "ダイヘン", "symbol": "6622.T"},
                {"security_code": "6504", "company_name": "富士電機", "symbol": "6504.T"},
                {"security_code": "6508", "company_name": "明電舎", "symbol": "6508.T"},
            ],
        }
    ],
}


def chart(closes: list[float], volumes: list[float]) -> dict:
    start = datetime(2026, 5, 1, tzinfo=timezone.utc)
    timestamps = [int((start + timedelta(days=i)).timestamp()) for i in range(len(closes))]
    return {
        "chart": {
            "result": [
                {"timestamp": timestamps, "indicators": {"quote": [{"close": closes, "volume": volumes}]}}
            ],
            "error": None,
        }
    }


def rising(start: float, step: float, count: int = 100) -> list[float]:
    return [start + step * i for i in range(count)]


class MoneyFlowCanonicalRunTests(unittest.TestCase):
    def _fetcher(self, symbol: str, range_: str, interval: str) -> dict:
        payloads = {
            "^TOPX": chart(rising(100, 0.08), [100] * 100),
            "6622.T": chart(rising(100, 0.35), [100] * 80 + [180] * 20),
            "6504.T": chart(rising(100, 0.30), [100] * 80 + [170] * 20),
            "6508.T": chart(rising(100, 0.28), [100] * 80 + [165] * 20),
        }
        return payloads[symbol]

    def test_canonical_snapshot_keeps_explicit_membership_and_is_persistable(self):
        snapshot = canonical_snapshot(
            theme_id=DEFAULT_THEME_ID,
            as_of=date(2026, 8, 9),
            theme_config=THEME_CONFIG,
            sector_config=SECTOR_CONFIG,
            detector_config=DETECTOR_CONFIG,
            history=[],
            fetcher=self._fetcher,
        )
        self.assertTrue(snapshot["persistable"])
        self.assertEqual(snapshot["membership_version"], "2026-08-09-v1")
        self.assertEqual([row["security_code"] for row in snapshot["members"]], ["6622", "6504", "6508"])
        self.assertEqual(snapshot["coverage"]["available"], 3)
        self.assertIn(snapshot["data_completeness"], {"OK", "PARTIAL"})

    def test_persistence_is_idempotent_and_conflict_safe_via_history_contract(self):
        snapshot = canonical_snapshot(
            theme_id=DEFAULT_THEME_ID,
            as_of=date(2026, 8, 9),
            theme_config=THEME_CONFIG,
            sector_config=SECTOR_CONFIG,
            detector_config=DETECTOR_CONFIG,
            history=[],
            fetcher=self._fetcher,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.jsonl"
            self.assertEqual(persist_canonical_snapshot(path, snapshot), "INSERTED")
            self.assertEqual(persist_canonical_snapshot(path, snapshot), "UNCHANGED")
            self.assertEqual(len(load_history(path)), 1)

    def test_all_market_data_unavailable_is_not_persisted_as_cold(self):
        def unavailable(symbol: str, range_: str, interval: str) -> dict:
            if symbol == "^TOPX":
                return chart(rising(100, 0.08), [100] * 100)
            raise RuntimeError("market unavailable")

        snapshot = canonical_snapshot(
            theme_id=DEFAULT_THEME_ID,
            as_of=date(2026, 8, 9),
            theme_config=THEME_CONFIG,
            sector_config=SECTOR_CONFIG,
            detector_config=DETECTOR_CONFIG,
            history=[],
            fetcher=unavailable,
        )
        self.assertFalse(snapshot["persistable"])
        self.assertEqual(snapshot["data_completeness"], "UNAVAILABLE")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.jsonl"
            self.assertEqual(persist_canonical_snapshot(path, snapshot), "NOT_PERSISTED_UNAVAILABLE")
            self.assertFalse(path.exists())

    def test_policy_lead_time_uses_first_observed_states_and_exposes_limitations(self):
        history = [
            {"kind": "THEME", "id": DEFAULT_THEME_ID, "as_of": "2024-10-10", "state": "WARMING"},
            {"kind": "THEME", "id": DEFAULT_THEME_ID, "as_of": "2024-10-18", "state": "INFLOW"},
            {"kind": "THEME", "id": DEFAULT_THEME_ID, "as_of": "2024-10-20", "state": "WARMING"},
        ]
        result = evaluate_policy_lead_time(
            history,
            theme_id=DEFAULT_THEME_ID,
            policy_t0=date(2024, 10, 4),
            retrospective_membership=True,
        )
        self.assertEqual(result["first_warming_date"], "2024-10-10")
        self.assertEqual(result["first_inflow_date"], "2024-10-18")
        self.assertEqual(result["policy_to_warming_days"], 6)
        self.assertEqual(result["policy_to_inflow_days"], 14)
        self.assertIn("RETROSPECTIVE_MEMBERSHIP", result["limitations"])

    def test_missing_inflow_remains_unknown_not_zero_days(self):
        history = [{"kind": "THEME", "id": DEFAULT_THEME_ID, "as_of": "2024-10-10", "state": "WARMING"}]
        result = evaluate_policy_lead_time(history, theme_id=DEFAULT_THEME_ID)
        self.assertIsNone(result["first_inflow_date"])
        self.assertIsNone(result["policy_to_inflow_days"])
        self.assertIn("FIRST_INFLOW_NOT_OBSERVED", result["limitations"])


if __name__ == "__main__":
    unittest.main()
