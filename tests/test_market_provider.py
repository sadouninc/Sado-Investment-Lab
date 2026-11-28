from __future__ import annotations

from datetime import datetime, timezone
import unittest

from scripts.morning_dataset.providers.market import MARKET_SYMBOLS, MarketProvider


def chart(close_values: list[float]) -> dict:
    base = int(datetime(2026, 8, 6, tzinfo=timezone.utc).timestamp())
    return {
        "chart": {
            "result": [{
                "timestamp": [base + 86400 * i for i in range(len(close_values))],
                "indicators": {"quote": [{"close": close_values}]},
            }],
            "error": None,
        }
    }


class MarketProviderTest(unittest.TestCase):
    def test_complete_snapshot_is_ok(self) -> None:
        def fetcher(symbol: str) -> dict:
            return chart([100.0, 102.0])

        result = MarketProvider(fetcher=fetcher).collect()
        self.assertEqual("OK", result.status)
        self.assertEqual(len(MARKET_SYMBOLS), result.data["coverage"]["available"])
        self.assertIn("nikkei_225", result.data["indices"])
        self.assertEqual("1306.T", result.data["indices"]["topix"]["symbol"])
        self.assertEqual("TOPIX", result.data["indices"]["topix"]["proxy_for"])
        self.assertEqual("etf_proxy", result.data["indices"]["topix"]["kind"])
        self.assertIn("usdjpy", result.data["macro"])
        self.assertAlmostEqual(2.0, result.data["indices"]["nikkei_225"]["change_pct"])
        # Yahoo ^TNX is ten times the percentage yield; provider normalizes it.
        self.assertAlmostEqual(10.2, result.data["macro"]["us_10y"]["value"])
        self.assertTrue(result.as_of)
        self.assertTrue(result.source_reference)

    def test_individual_failure_returns_partial_with_preserved_data(self) -> None:
        failed_symbol = MARKET_SYMBOLS["vix"]["symbol"]

        def fetcher(symbol: str) -> dict:
            if symbol == failed_symbol:
                raise TimeoutError("simulated")
            return chart([100.0, 101.0])

        result = MarketProvider(fetcher=fetcher).collect()
        self.assertEqual("PARTIAL", result.status)
        self.assertEqual(len(MARKET_SYMBOLS) - 1, result.data["coverage"]["available"])
        self.assertEqual(1, len(result.data["coverage"]["missing"]))
        self.assertIn("1 of", result.reason)

    def test_all_failures_are_missing(self) -> None:
        def fetcher(symbol: str) -> dict:
            raise TimeoutError("simulated")

        result = MarketProvider(fetcher=fetcher).collect()
        self.assertEqual("MISSING", result.status)
        self.assertIsNone(result.data)
        self.assertIn("all public market quote requests failed", result.reason)

    # --- #973: series integrity, finite values, ordering ---

    def collect_with_bad(self, bad_symbol_key: str, bad_payload: dict):
        bad_symbol = MARKET_SYMBOLS[bad_symbol_key]["symbol"]

        def fetcher(symbol: str) -> dict:
            if symbol == bad_symbol:
                return bad_payload
            return chart([100.0, 101.0])

        return MarketProvider(fetcher=fetcher).collect()

    def assert_symbol_failed(self, result, key: str) -> None:
        self.assertEqual("PARTIAL", result.status)
        self.assertNotIn(key, result.data["indices"])
        self.assertNotIn(key, result.data["macro"])
        self.assertEqual(len(MARKET_SYMBOLS) - 1, result.data["coverage"]["available"])
        self.assertEqual(1, len(result.data["coverage"]["missing"]))
        self.assertTrue(result.data["coverage"]["missing"][0].startswith(f"{key}("))
        # Other valid symbols are retained.
        self.assertAlmostEqual(1.0, result.data["indices"]["sp500"]["change_pct"])

    def test_length_mismatch_is_symbol_failure(self) -> None:
        payload = chart([100.0, 101.0])
        payload["chart"]["result"][0]["timestamp"].append(
            payload["chart"]["result"][0]["timestamp"][-1] + 86400
        )
        self.assert_symbol_failed(self.collect_with_bad("nikkei_225", payload), "nikkei_225")

        payload = chart([100.0, 101.0, 102.0])
        payload["chart"]["result"][0]["timestamp"].pop()
        self.assert_symbol_failed(self.collect_with_bad("nikkei_225", payload), "nikkei_225")

    def test_non_finite_or_bool_close_is_symbol_failure(self) -> None:
        for bad in (float("nan"), float("inf"), float("-inf"), True, "101.0"):
            with self.subTest(close=bad):
                result = self.collect_with_bad("vix", chart([100.0, bad]))
                self.assert_symbol_failed(result, "vix")

    def test_invalid_timestamp_is_symbol_failure(self) -> None:
        for bad in (None, "1786060800", float("nan"), True):
            with self.subTest(timestamp=bad):
                payload = chart([100.0, 101.0])
                payload["chart"]["result"][0]["timestamp"][1] = bad
                self.assert_symbol_failed(self.collect_with_bad("dow", payload), "dow")

    def test_unordered_or_duplicate_timestamps_are_symbol_failure(self) -> None:
        payload = chart([100.0, 101.0, 102.0])
        ts = payload["chart"]["result"][0]["timestamp"]
        ts[1], ts[2] = ts[2], ts[1]
        self.assert_symbol_failed(self.collect_with_bad("sox", payload), "sox")

        payload = chart([100.0, 101.0])
        ts = payload["chart"]["result"][0]["timestamp"]
        ts[1] = ts[0]
        self.assert_symbol_failed(self.collect_with_bad("sox", payload), "sox")

    def test_wrongly_typed_series_are_symbol_failure(self) -> None:
        payload = chart([100.0, 101.0])
        payload["chart"]["result"][0]["timestamp"] = "not a list"
        self.assert_symbol_failed(self.collect_with_bad("wti", payload), "wti")

        payload = chart([100.0, 101.0])
        payload["chart"]["result"][0]["indicators"]["quote"][0]["close"] = {"0": 100.0}
        self.assert_symbol_failed(self.collect_with_bad("wti", payload), "wti")

        payload = {"chart": {"result": ["not an object"], "error": None}}
        self.assert_symbol_failed(self.collect_with_bad("wti", payload), "wti")

    def test_overflowing_change_is_symbol_failure(self) -> None:
        result = self.collect_with_bad("nasdaq", chart([-1.7e308, 1.7e308]))
        self.assert_symbol_failed(result, "nasdaq")

    def test_overflowing_change_pct_is_symbol_failure(self) -> None:
        result = self.collect_with_bad("nasdaq", chart([1e-320, 1e308]))
        self.assert_symbol_failed(result, "nasdaq")

    def test_missing_close_handling_is_preserved(self) -> None:
        # A trailing null close is skipped; the latest real close and its
        # timestamp are used, as before.
        payload = chart([100.0, 102.0, None])

        def fetcher(symbol: str) -> dict:
            return payload

        result = MarketProvider(fetcher=fetcher).collect()
        self.assertEqual("OK", result.status)
        nikkei = result.data["indices"]["nikkei_225"]
        self.assertEqual(102.0, nikkei["value"])
        self.assertEqual(100.0, nikkei["previous_close"])
        self.assertEqual("2026-08-07T00:00:00+00:00", nikkei["as_of"])

    def test_all_null_closes_is_symbol_failure(self) -> None:
        result = self.collect_with_bad("usdjpy", chart([None, None]))
        self.assert_symbol_failed(result, "usdjpy")

    def test_true_zero_previous_close_does_not_fabricate_change(self) -> None:
        def fetcher(symbol: str) -> dict:
            return chart([0.0, 5.0])

        result = MarketProvider(fetcher=fetcher).collect()
        self.assertEqual("OK", result.status)
        quote = result.data["indices"]["nikkei_225"]
        self.assertEqual(5.0, quote["value"])
        self.assertEqual(0.0, quote["previous_close"])
        self.assertIsNone(quote["change"])
        self.assertIsNone(quote["change_pct"])

    def test_true_zero_change_is_reported_as_zero(self) -> None:
        def fetcher(symbol: str) -> dict:
            return chart([100.0, 100.0])

        result = MarketProvider(fetcher=fetcher).collect()
        quote = result.data["indices"]["nikkei_225"]
        self.assertEqual(0.0, quote["change"])
        self.assertEqual(0.0, quote["change_pct"])

    def test_yield_scaling_and_proxy_labels_are_preserved_with_validation(self) -> None:
        def fetcher(symbol: str) -> dict:
            return chart([40.0, 41.0])

        result = MarketProvider(fetcher=fetcher).collect()
        us_10y = result.data["macro"]["us_10y"]
        self.assertAlmostEqual(4.1, us_10y["value"])
        self.assertAlmostEqual(4.0, us_10y["previous_close"])
        self.assertAlmostEqual(0.1, us_10y["change"])
        self.assertNotIn("scale", us_10y)
        self.assertEqual("TSE Growth Market 250", result.data["indices"]["growth_250_proxy"]["proxy_for"])

    def test_every_symbol_malformed_is_missing(self) -> None:
        def fetcher(symbol: str) -> dict:
            return chart([100.0, float("nan")])

        result = MarketProvider(fetcher=fetcher).collect()
        self.assertEqual("MISSING", result.status)
        self.assertIsNone(result.data)


if __name__ == "__main__":
    unittest.main()
