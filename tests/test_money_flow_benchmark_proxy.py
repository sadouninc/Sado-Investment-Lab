from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.money_flow_canonical_run import latest_market_date
from scripts.money_flow_theme_adapter import load_theme_config


CONFIG_PATH = Path("data/config/money-flow-themes-v1.json")


def chart() -> dict:
    timestamp = int(datetime(2026, 8, 7, tzinfo=timezone.utc).timestamp())
    return {
        "chart": {
            "result": [
                {
                    "timestamp": [timestamp],
                    "indicators": {
                        "quote": [{"close": [100.0], "volume": [1000.0]}]
                    },
                }
            ],
            "error": None,
        }
    }


class MoneyFlowBenchmarkProxyTests(unittest.TestCase):
    def test_production_config_uses_explicit_topix_etf_proxy(self):
        config = load_theme_config(CONFIG_PATH)
        benchmark = config["benchmark"]

        self.assertEqual(benchmark["symbol"], "1306.T")
        self.assertTrue(benchmark["proxy"])
        self.assertIn("TOPIX", benchmark["tracks"])
        self.assertTrue(benchmark["authority"])
        self.assertTrue(benchmark["limitation"])

    def test_latest_market_date_uses_configured_proxy_without_hidden_fallback(self):
        config = load_theme_config(CONFIG_PATH)
        requested_symbols: list[str] = []

        def fetcher(symbol: str, range_: str, interval: str) -> dict:
            requested_symbols.append(symbol)
            if symbol != "1306.T":
                raise AssertionError(f"unexpected benchmark symbol: {symbol}")
            return chart()

        market_date = latest_market_date(theme_config=config, fetcher=fetcher)

        self.assertEqual(market_date.isoformat(), "2026-08-07")
        self.assertEqual(requested_symbols, ["1306.T"])

    def test_proxy_metadata_prevents_index_identity_ambiguity(self):
        config = load_theme_config(CONFIG_PATH)
        benchmark = config["benchmark"]

        self.assertNotEqual(benchmark["name"], "TOPIX")
        self.assertIn("proxy", benchmark["name"].lower())
        self.assertIn("not the TOPIX index level", benchmark["limitation"])


if __name__ == "__main__":
    unittest.main()
