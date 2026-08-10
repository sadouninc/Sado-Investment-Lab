from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from scripts.money_flow_history import load_history
from scripts.money_flow_sector_canonical_run import canonical_sector_set, persist_sector_set

DETECTOR = {
    "required_axes": ["relative_strength", "activity", "breadth", "heat", "acceleration"],
    "weights": {"relative_strength": .30, "activity": .20, "breadth": .25, "acceleration": .25},
    "thresholds": {"warming_score": 55, "inflow_score": 70, "hot_score": 82, "overheated_heat": 85, "max_heat_for_warming": 70, "max_heat_for_inflow": 80},
    "hysteresis": {"promote_days": 2, "demote_days": 2},
    "minimum_non_null_axes": 4,
}
CONFIG = {
    "taxonomy": "TOPIX-17",
    "benchmark": {"name": "TOPIX", "symbol": "^TOPX"},
    "history_range": "6mo", "interval": "1d",
    "windows": {"short": 5, "medium": 20, "long": 60, "activity_short": 5, "activity_baseline": 20},
    "scoring": {"relative_strength_points_per_pct": 4, "acceleration_points_per_pct": 4, "activity_points_per_ratio": 40, "heat_points_per_pct": 3},
    "sectors": [{"id": "sector:a", "name": "A", "symbol": "A.T"}, {"id": "sector:b", "name": "B", "symbol": "B.T"}],
}


def chart(end: date, step: float = .1) -> dict:
    start = datetime.combine(end - timedelta(days=99), datetime.min.time(), tzinfo=timezone.utc)
    ts = [int((start + timedelta(days=i)).timestamp()) for i in range(100)]
    return {"chart": {"result": [{"timestamp": ts, "indicators": {"quote": [{"close": [100 + step*i for i in range(100)], "volume": [100]*100}]}}], "error": None}}


class SectorCanonicalRunTests(unittest.TestCase):
    def test_same_as_of_set_is_persisted_idempotently_and_breadth_stays_null(self):
        as_of = date(2026, 8, 10)
        def fetch(symbol: str, range_: str, interval: str) -> dict:
            return chart(as_of, .05 if symbol == "^TOPX" else .2)
        payload = canonical_sector_set(as_of=as_of, sector_config=CONFIG, detector_config=DETECTOR, history=[], fetcher=fetch)
        self.assertTrue(payload["persistable"])
        self.assertEqual(len(payload["sectors"]), 2)
        self.assertTrue(all(row["scores"]["breadth"] is None for row in payload["sectors"]))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.jsonl"
            self.assertEqual(persist_sector_set(path, payload), {"INSERTED": 2})
            self.assertEqual(persist_sector_set(path, payload), {"UNCHANGED": 2})
            self.assertEqual(len(load_history(path)), 2)

    def test_mixed_source_dates_fail_closed_without_synthetic_cold_history(self):
        as_of = date(2026, 8, 10)
        def fetch(symbol: str, range_: str, interval: str) -> dict:
            end = as_of - timedelta(days=1) if symbol == "B.T" else as_of
            return chart(end, .05 if symbol == "^TOPX" else .2)
        payload = canonical_sector_set(as_of=as_of, sector_config=CONFIG, detector_config=DETECTOR, history=[], fetcher=fetch)
        self.assertFalse(payload["persistable"])
        self.assertEqual(payload["data_completeness"], "PARTIAL")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.jsonl"
            persist_sector_set(path, payload)
            self.assertFalse(path.exists())

    def test_previous_state_comes_only_from_prior_sector_history(self):
        as_of = date(2026, 8, 10)
        history = [{"kind": "THEME", "id": "sector:a", "as_of": "2026-08-09", "state": "HOT"}, {"kind": "SECTOR", "id": "sector:a", "as_of": "2026-08-09", "state": "WARMING", "selection_signal": True}]
        def fetch(symbol: str, range_: str, interval: str) -> dict:
            return chart(as_of, .05 if symbol == "^TOPX" else .2)
        payload = canonical_sector_set(as_of=as_of, sector_config=CONFIG, detector_config=DETECTOR, history=history, fetcher=fetch)
        row = next(r for r in payload["sectors"] if r["id"] == "sector:a")
        self.assertEqual(row["previous_state"], "WARMING")


if __name__ == "__main__":
    unittest.main()
