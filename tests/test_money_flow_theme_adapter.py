from __future__ import annotations

import unittest
from datetime import date

from scripts.candidate_selector import build_selector
from scripts.money_flow_theme_adapter import build_theme_snapshots, theme_snapshots_to_candidate_rows


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
            "id": "theme:gaming",
            "name": "Gaming",
            "membership_as_of": "2026-08-09",
            "members": [
                {"security_code": "7974", "company_name": "任天堂", "symbol": "7974.T"},
                {"security_code": "9697", "company_name": "カプコン", "symbol": "9697.T"},
            ],
        }
    ],
}

SELECTOR_CONFIG = {
    "schema_version": 1,
    "freshness_days": 90,
    "major_change_threshold": 80,
    "weights": {
        "investment_relevance": 0.30,
        "change_signal": 0.25,
        "research_gap": 0.20,
        "theme_relevance": 0.15,
        "valuation_interest": 0.10,
    },
}


def chart(closes: list[float], volumes: list[float]) -> dict:
    return {
        "chart": {
            "result": [
                {
                    "indicators": {"quote": [{"close": closes, "volume": volumes}]}
                }
            ],
            "error": None,
        }
    }


def rising(start: float, step: float, count: int = 80) -> list[float]:
    return [start + step * i for i in range(count)]


class MoneyFlowThemeAdapterTests(unittest.TestCase):
    def test_theme_breadth_and_membership_are_explicit(self):
        payloads = {
            "^TOPX": chart(rising(100, 0.10), [100] * 80),
            "7974.T": chart(rising(100, 0.35), [100] * 60 + [180] * 20),
            "9697.T": chart(rising(100, 0.30), [100] * 60 + [170] * 20),
        }

        def fetcher(symbol: str, range_: str, interval: str) -> dict:
            return payloads[symbol]

        result = build_theme_snapshots(
            theme_config=THEME_CONFIG,
            sector_config=SECTOR_CONFIG,
            detector_config=DETECTOR_CONFIG,
            as_of=date(2026, 8, 9),
            fetcher=fetcher,
            previous={
                "theme:gaming": {
                    "state": "COLD",
                    "target_state": "WARMING",
                    "target_streak": 1,
                    "state_since": "2026-08-08",
                }
            },
        )
        theme = result["themes"][0]
        self.assertEqual(theme["membership_as_of"], "2026-08-09")
        self.assertEqual(theme["member_count"], 2)
        self.assertEqual(theme["coverage"]["available"], 2)
        self.assertEqual(theme["scores"]["breadth"], 100.0)
        self.assertEqual([m["security_code"] for m in theme["members"]], ["7974", "9697"])

    def test_warming_theme_emits_money_flow_candidate_rows(self):
        payload = {
            "schema_version": 1,
            "as_of": "2026-08-09",
            "themes": [
                {
                    "id": "theme:gaming",
                    "name": "Gaming",
                    "state": "WARMING",
                    "selection_signal": True,
                    "flow_score": 72.0,
                    "scores": {"acceleration": 68.0, "breadth": 75.0},
                    "members": [
                        {"security_code": "7974", "company_name": "任天堂", "symbol": "7974.T"},
                        {"security_code": "9697", "company_name": "カプコン", "symbol": "9697.T"},
                    ],
                }
            ],
        }
        rows = theme_snapshots_to_candidate_rows(payload)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["candidate_sources"], ["MONEY_FLOW"])
        self.assertEqual(rows[0]["signals"]["theme_relevance"], 72.0)
        self.assertEqual(rows[0]["updated_at"], "2026-08-09")

        selector = build_selector(rows, config=SELECTOR_CONFIG, as_of=date(2026, 8, 9))
        self.assertEqual(len(selector["candidates"]), 2)
        self.assertIn("MONEY_FLOW", selector["candidates"][0]["candidate_sources"])

    def test_cold_or_hot_theme_does_not_emit_candidates(self):
        for state in ("COLD", "HOT", "OVERHEATED"):
            payload = {
                "as_of": "2026-08-09",
                "themes": [
                    {
                        "name": "Gaming",
                        "state": state,
                        "selection_signal": False,
                        "flow_score": 80,
                        "scores": {"acceleration": 80, "breadth": 80},
                        "members": [{"security_code": "7974", "company_name": "任天堂"}],
                    }
                ],
            }
            self.assertEqual(theme_snapshots_to_candidate_rows(payload), [])

    def test_missing_member_is_reported_not_imputed(self):
        payloads = {
            "^TOPX": chart(rising(100, 0.10), [100] * 80),
            "7974.T": chart(rising(100, 0.35), [100] * 80),
        }

        def fetcher(symbol: str, range_: str, interval: str) -> dict:
            if symbol not in payloads:
                raise RuntimeError("unavailable")
            return payloads[symbol]

        result = build_theme_snapshots(
            theme_config=THEME_CONFIG,
            sector_config=SECTOR_CONFIG,
            detector_config=DETECTOR_CONFIG,
            as_of=date(2026, 8, 9),
            fetcher=fetcher,
        )
        theme = result["themes"][0]
        self.assertEqual(theme["coverage"]["available"], 1)
        self.assertEqual(theme["coverage"]["requested"], 2)
        self.assertEqual(theme["coverage"]["missing"][0]["security_code"], "9697")


if __name__ == "__main__":
    unittest.main()
