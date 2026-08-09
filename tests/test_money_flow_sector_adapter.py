from __future__ import annotations

import unittest
from datetime import date

from scripts.money_flow_sector_adapter import build_sector_snapshots, derive_sector_scores


DETECTOR_CONFIG = {
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

SECTOR_CONFIG = {
    "schema_version": 1,
    "taxonomy": "TOPIX-17 ETF proxy",
    "benchmark": {"name": "TOPIX", "symbol": "^TOPX"},
    "history_range": "6mo",
    "interval": "1d",
    "windows": {"short": 5, "medium": 20, "long": 60, "activity_short": 5, "activity_baseline": 20},
    "scoring": {
        "relative_strength_points_per_pct": 4.0,
        "acceleration_points_per_pct": 4.0,
        "activity_points_per_ratio": 40.0,
        "heat_points_per_pct": 3.0,
    },
    "sectors": [{"id": "sector:test", "name": "Test Sector", "symbol": "9999.T"}],
}


def yahoo_payload(closes: list[float], volumes: list[float]) -> dict:
    return {
        "chart": {
            "result": [
                {
                    "timestamp": list(range(len(closes))),
                    "indicators": {"quote": [{"close": closes, "volume": volumes}]},
                }
            ],
            "error": None,
        }
    }


def growth_series(days: int, daily: float) -> list[float]:
    values = [100.0]
    for _ in range(days - 1):
        values.append(values[-1] * (1.0 + daily))
    return values


class MoneyFlowSectorAdapterTests(unittest.TestCase):
    def test_scores_use_relative_returns_activity_and_keep_breadth_null(self):
        benchmark = {"close": growth_series(80, 0.0005), "volume": [100.0] * 80}
        sector = {"close": growth_series(80, 0.0015), "volume": [100.0] * 60 + [100.0] * 15 + [180.0] * 5}
        scores, evidence, metrics = derive_sector_scores(sector, benchmark, config=SECTOR_CONFIG)
        self.assertGreater(scores["relative_strength"], 50)
        self.assertGreater(scores["activity"], 50)
        self.assertIsNone(scores["breadth"])
        self.assertIn("breadth unavailable", " ".join(evidence))
        self.assertFalse(metrics["proxy_breadth_available"])

    def test_build_sector_snapshot_connects_market_series_to_detector_core(self):
        benchmark = growth_series(80, 0.0002)
        sector = growth_series(80, 0.0012)
        volumes = [100.0] * 75 + [190.0] * 5

        def fetcher(symbol: str, range_: str, interval: str):
            self.assertEqual(range_, "6mo")
            self.assertEqual(interval, "1d")
            if symbol == "^TOPX":
                return yahoo_payload(benchmark, [100.0] * 80)
            if symbol == "9999.T":
                return yahoo_payload(sector, volumes)
            raise AssertionError(symbol)

        result = build_sector_snapshots(
            sector_config=SECTOR_CONFIG,
            detector_config=DETECTOR_CONFIG,
            as_of=date(2026, 8, 9),
            fetcher=fetcher,
        )
        self.assertEqual(result["coverage"]["available"], 1)
        row = result["sectors"][0]
        self.assertEqual(row["kind"], "SECTOR")
        self.assertEqual(row["proxy_symbol"], "9999.T")
        self.assertEqual(row["benchmark"]["symbol"], "^TOPX")
        self.assertEqual(row["data_completeness"], "PARTIAL")
        self.assertIsNone(row["scores"]["breadth"])
        self.assertIn(row["state"], {"COLD", "WARMING", "INFLOW", "HOT", "OVERHEATED"})

    def test_previous_snapshot_carries_hysteresis_state(self):
        benchmark = growth_series(80, 0.0)
        sector = growth_series(80, 0.001)

        def fetcher(symbol: str, range_: str, interval: str):
            closes = benchmark if symbol == "^TOPX" else sector
            return yahoo_payload(closes, [150.0] * 80)

        previous = {
            "sector:test": {
                "id": "sector:test",
                "state": "COLD",
                "target_state": "WARMING",
                "target_streak": 1,
                "state_since": "2026-08-08",
            }
        }
        result = build_sector_snapshots(
            sector_config=SECTOR_CONFIG,
            detector_config=DETECTOR_CONFIG,
            as_of=date(2026, 8, 9),
            fetcher=fetcher,
            previous=previous,
        )
        row = result["sectors"][0]
        if row["target_state"] == "WARMING":
            self.assertEqual(row["state"], "WARMING")
            self.assertEqual(row["target_streak"], 2)

    def test_one_sector_failure_does_not_drop_other_sector_results(self):
        config = dict(SECTOR_CONFIG)
        config["sectors"] = [
            {"id": "sector:ok", "name": "OK", "symbol": "1111.T"},
            {"id": "sector:bad", "name": "BAD", "symbol": "2222.T"},
        ]
        benchmark = growth_series(80, 0.0)

        def fetcher(symbol: str, range_: str, interval: str):
            if symbol == "^TOPX":
                return yahoo_payload(benchmark, [100.0] * 80)
            if symbol == "1111.T":
                return yahoo_payload(growth_series(80, 0.0005), [100.0] * 80)
            raise RuntimeError("unavailable")

        result = build_sector_snapshots(
            sector_config=config,
            detector_config=DETECTOR_CONFIG,
            as_of=date(2026, 8, 9),
            fetcher=fetcher,
        )
        self.assertEqual(result["coverage"]["available"], 1)
        self.assertEqual(result["coverage"]["requested"], 2)
        self.assertEqual(result["coverage"]["missing"][0]["id"], "sector:bad")


if __name__ == "__main__":
    unittest.main()
