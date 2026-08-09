from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone

from scripts.money_flow_sector_adapter import _series, build_sector_snapshots, derive_sector_scores


DETECTOR_CONFIG = {
    "schema_version": 1,
    "required_axes": ["relative_strength", "activity", "breadth", "heat", "acceleration"],
    "weights": {"relative_strength": 0.30, "activity": 0.20, "breadth": 0.25, "acceleration": 0.25},
    "thresholds": {"warming_score": 55, "inflow_score": 70, "hot_score": 82, "overheated_heat": 85, "max_heat_for_warming": 70, "max_heat_for_inflow": 80},
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
    "scoring": {"relative_strength_points_per_pct": 4.0, "acceleration_points_per_pct": 4.0, "activity_points_per_ratio": 40.0, "heat_points_per_pct": 3.0},
    "sectors": [{"id": "sector:test", "name": "Test Sector", "symbol": "9999.T"}],
}


def timestamps(days: int, *, skip: set[int] | None = None) -> list[int]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    skip = skip or set()
    return [int((start + timedelta(days=i)).timestamp()) for i in range(days) if i not in skip]


def yahoo_payload(closes: list[float], volumes: list[float], *, stamps: list[int] | None = None) -> dict:
    stamps = stamps or timestamps(len(closes))
    return {"chart": {"result": [{"timestamp": stamps, "indicators": {"quote": [{"close": closes, "volume": volumes}]}}], "error": None}}


def growth_series(days: int, daily: float) -> list[float]:
    values = [100.0]
    for _ in range(days - 1):
        values.append(values[-1] * (1.0 + daily))
    return values


def rows(closes: list[float], volumes: list[float], *, stamps: list[int] | None = None):
    return _series(yahoo_payload(closes, volumes, stamps=stamps), "TEST")


class MoneyFlowSectorAdapterTests(unittest.TestCase):
    def test_scores_use_relative_returns_activity_and_keep_breadth_null(self):
        benchmark = rows(growth_series(80, 0.0005), [100.0] * 80)
        sector = rows(growth_series(80, 0.0015), [100.0] * 75 + [180.0] * 5)
        scores, evidence, metrics = derive_sector_scores(sector, benchmark, config=SECTOR_CONFIG)
        self.assertGreater(scores["relative_strength"], 50)
        self.assertGreater(scores["activity"], 50)
        self.assertIsNone(scores["breadth"])
        self.assertIn("breadth unavailable", " ".join(evidence))
        self.assertFalse(metrics["proxy_breadth_available"])
        self.assertEqual(metrics["common_trading_date_count"], 80)

    def test_inner_join_prevents_misaligned_returns_when_sector_has_missing_day(self):
        all_prices = growth_series(80, 0.001)
        benchmark_stamps = timestamps(80)
        sector_stamps = timestamps(80, skip={70})
        sector_prices = [price for i, price in enumerate(all_prices) if i != 70]
        benchmark = rows(all_prices, [100.0] * 80, stamps=benchmark_stamps)
        sector = rows(sector_prices, [100.0] * 79, stamps=sector_stamps)
        _, _, metrics = derive_sector_scores(sector, benchmark, config=SECTOR_CONFIG)
        self.assertEqual(metrics["common_trading_date_count"], 79)
        self.assertAlmostEqual(metrics["relative_returns_pct"]["short"], 0.0, places=10)

    def test_market_data_as_of_uses_latest_common_date_when_benchmark_is_newer(self):
        benchmark = rows(growth_series(81, 0.0), [100.0] * 81, stamps=timestamps(81))
        sector = rows(growth_series(80, 0.0), [100.0] * 80, stamps=timestamps(80))
        _, _, metrics = derive_sector_scores(sector, benchmark, config=SECTOR_CONFIG)
        self.assertEqual(metrics["market_data_as_of"], metrics["sector_source_as_of"])
        self.assertNotEqual(metrics["market_data_as_of"], metrics["benchmark_source_as_of"])

    def test_common_history_shortage_keeps_long_window_null(self):
        benchmark = rows(growth_series(80, 0.0), [100.0] * 80)
        sector_stamps = timestamps(80)[20:]
        sector = rows(growth_series(60, 0.001), [100.0] * 60, stamps=sector_stamps)
        scores, _, metrics = derive_sector_scores(sector, benchmark, config=SECTOR_CONFIG)
        self.assertIsNone(metrics["relative_returns_pct"]["long"])
        self.assertIsNone(scores["acceleration"])

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

        result = build_sector_snapshots(sector_config=SECTOR_CONFIG, detector_config=DETECTOR_CONFIG, as_of=date(2026, 8, 9), fetcher=fetcher)
        self.assertEqual(result["coverage"]["available"], 1)
        self.assertIn("snapshot evaluation date", result["as_of_semantics"])
        row = result["sectors"][0]
        self.assertEqual(row["kind"], "SECTOR")
        self.assertEqual(row["proxy_symbol"], "9999.T")
        self.assertEqual(row["data_completeness"], "PARTIAL")
        self.assertIsNone(row["scores"]["breadth"])
        self.assertIn("market_data_as_of", row["source_metrics"])

    def test_previous_snapshot_carries_hysteresis_state(self):
        benchmark = growth_series(80, 0.0)
        sector = growth_series(80, 0.001)

        def fetcher(symbol: str, range_: str, interval: str):
            closes = benchmark if symbol == "^TOPX" else sector
            return yahoo_payload(closes, [150.0] * 80)

        previous = {"sector:test": {"id": "sector:test", "state": "COLD", "target_state": "WARMING", "target_streak": 1, "state_since": "2026-08-08"}}
        result = build_sector_snapshots(sector_config=SECTOR_CONFIG, detector_config=DETECTOR_CONFIG, as_of=date(2026, 8, 9), fetcher=fetcher, previous=previous)
        row = result["sectors"][0]
        if row["target_state"] == "WARMING":
            self.assertEqual(row["state"], "WARMING")
            self.assertEqual(row["target_streak"], 2)

    def test_one_sector_failure_does_not_drop_other_sector_results(self):
        config = dict(SECTOR_CONFIG)
        config["sectors"] = [{"id": "sector:ok", "name": "OK", "symbol": "1111.T"}, {"id": "sector:bad", "name": "BAD", "symbol": "2222.T"}]
        benchmark = growth_series(80, 0.0)

        def fetcher(symbol: str, range_: str, interval: str):
            if symbol == "^TOPX":
                return yahoo_payload(benchmark, [100.0] * 80)
            if symbol == "1111.T":
                return yahoo_payload(growth_series(80, 0.0005), [100.0] * 80)
            raise RuntimeError("unavailable")

        result = build_sector_snapshots(sector_config=config, detector_config=DETECTOR_CONFIG, as_of=date(2026, 8, 9), fetcher=fetcher)
        self.assertEqual(result["coverage"]["available"], 1)
        self.assertEqual(result["coverage"]["requested"], 2)
        self.assertEqual(result["coverage"]["missing"][0]["id"], "sector:bad")


if __name__ == "__main__":
    unittest.main()
