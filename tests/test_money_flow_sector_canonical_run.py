from __future__ import annotations

import copy
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from scripts.money_flow_history import load_history
from scripts.money_flow_sector_canonical_run import SectorCanonicalRunError, canonical_sector_set, persist_sector_set, run_backfill

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


def weekday_chart(end: date, step: float = .1) -> dict:
    days = []
    cursor = end - timedelta(days=180)
    while cursor <= end:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)
    days = days[-100:]
    ts = [int(datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc).timestamp()) for day in days]
    return {"chart": {"result": [{"timestamp": ts, "indicators": {"quote": [{"close": [100 + step*i for i in range(len(days))], "volume": [100]*len(days)}]}}], "error": None}}


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

    def test_backfill_uses_benchmark_trading_dates_oldest_first_and_builds_hysteresis(self):
        end = date(2026, 8, 10)
        detector = copy.deepcopy(DETECTOR)
        detector["thresholds"].update({
            "warming_score": 0,
            "inflow_score": 101,
            "hot_score": 102,
            "overheated_heat": 101,
            "max_heat_for_warming": 100,
            "max_heat_for_inflow": 100,
        })
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            history = root / "sector-history.jsonl"
            sector_config = root / "sector.json"
            detector_config = root / "detector.json"
            import json
            sector_config.write_text(json.dumps(CONFIG), encoding="utf-8")
            detector_config.write_text(json.dumps(detector), encoding="utf-8")

            def fetch(symbol: str, range_: str, interval: str) -> dict:
                return weekday_chart(end, .05 if symbol == "^TOPX" else .2)

            result = run_backfill(
                start=date(2026, 8, 5),
                end=end,
                history_path=history,
                sector_config_path=sector_config,
                detector_config_path=detector_config,
                fetcher=fetch,
            )

            self.assertEqual(result["trading_dates"], ["2026-08-05", "2026-08-06", "2026-08-07", "2026-08-10"])
            self.assertEqual(result["unavailable_dates"], [])
            rows = load_history(history)
            self.assertEqual(len(rows), 8)
            latest = [row for row in rows if row["as_of"] == "2026-08-10"]
            self.assertEqual({row["state"] for row in latest}, {"WARMING"})
            self.assertEqual({row["previous_state"] for row in latest}, {"WARMING"})

    def test_backfill_rebuilds_existing_window_snapshot_instead_of_conflicting(self):
        end = date(2026, 8, 10)
        detector = copy.deepcopy(DETECTOR)
        detector["thresholds"].update({
            "warming_score": 0,
            "inflow_score": 101,
            "hot_score": 102,
            "overheated_heat": 101,
            "max_heat_for_warming": 100,
            "max_heat_for_inflow": 100,
        })
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            history = root / "sector-history.jsonl"
            sector_config = root / "sector.json"
            detector_config = root / "detector.json"
            import json
            sector_config.write_text(json.dumps(CONFIG), encoding="utf-8")
            detector_config.write_text(json.dumps(detector), encoding="utf-8")

            def fetch(symbol: str, range_: str, interval: str) -> dict:
                return weekday_chart(end, .05 if symbol == "^TOPX" else .2)

            initial = canonical_sector_set(
                as_of=end,
                sector_config=CONFIG,
                detector_config=detector,
                history=[],
                fetcher=fetch,
            )
            persist_sector_set(history, initial)
            self.assertEqual({row["state"] for row in load_history(history)}, {"COLD"})

            result = run_backfill(
                start=date(2026, 8, 5),
                end=end,
                history_path=history,
                sector_config_path=sector_config,
                detector_config_path=detector_config,
                fetcher=fetch,
            )

            self.assertEqual(result["replaced_existing_sector_rows"], 2)
            rows = load_history(history)
            self.assertEqual(len(rows), 8)
            latest = [row for row in rows if row["as_of"] == "2026-08-10"]
            self.assertEqual({row["state"] for row in latest}, {"WARMING"})

    def test_backfill_rejects_window_that_stops_before_latest_existing_sector_snapshot(self):
        end = date(2026, 8, 10)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            history = root / "sector-history.jsonl"
            sector_config = root / "sector.json"
            detector_config = root / "detector.json"
            import json
            sector_config.write_text(json.dumps(CONFIG), encoding="utf-8")
            detector_config.write_text(json.dumps(DETECTOR), encoding="utf-8")

            def fetch(symbol: str, range_: str, interval: str) -> dict:
                return weekday_chart(end, .05 if symbol == "^TOPX" else .2)

            initial = canonical_sector_set(
                as_of=end,
                sector_config=CONFIG,
                detector_config=DETECTOR,
                history=[],
                fetcher=fetch,
            )
            persist_sector_set(history, initial)

            with self.assertRaisesRegex(SectorCanonicalRunError, "latest existing Sector snapshot date"):
                run_backfill(
                    start=date(2026, 8, 5),
                    end=date(2026, 8, 7),
                    history_path=history,
                    sector_config_path=sector_config,
                    detector_config_path=detector_config,
                    fetcher=fetch,
                )


if __name__ == "__main__":
    unittest.main()
