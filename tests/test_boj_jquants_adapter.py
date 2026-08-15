from __future__ import annotations

from datetime import date, datetime, timezone
import unittest

from scripts.boj_jquants_adapter import JQuantsV2MarketDataProvider
from scripts.boj_market_data import (
    FRESHNESS_VERIFIED_SAME_DAY,
    PROVIDER_CREDENTIAL_MISSING,
    PROVIDER_OK,
    REQUIRED_BENCHMARK_CODES,
    REQUIRED_SECURITY_CODES,
    validate_aligned_market_data,
)


class FakeFrame:
    def __init__(self, rows):
        self.rows = rows

    def to_dict(self, orient):
        if orient != "records":
            raise AssertionError(orient)
        return list(self.rows)


class FakeJQuantsClient:
    def __init__(self):
        self.calls = []

    def get_eq_bars_daily(self, **kwargs):
        self.calls.append(("eq", kwargs))
        rows = []
        for code_index, code in enumerate(REQUIRED_SECURITY_CODES, start=1):
            returned_code = code + "0" if code.isdigit() and len(code) == 4 else code
            for day, close in (("2026-08-13", 100.0 + code_index), ("2026-08-14", 102.0 + code_index)):
                rows.append(
                    {
                        "Date": day,
                        "Code": returned_code,
                        "AdjO": close - 1.0,
                        "AdjH": close + 1.0,
                        "AdjL": close - 2.0,
                        "AdjC": close,
                        "AdjVo": 1000.0 * code_index,
                    }
                )
        return FakeFrame(rows)

    def get_idx_bars_daily_topix(self, **kwargs):
        self.calls.append(("topix", kwargs))
        return FakeFrame(
            [
                {"Date": "2026-08-13", "O": 2990.0, "H": 3010.0, "L": 2980.0, "C": 3000.0},
                {"Date": "2026-08-14", "O": 3000.0, "H": 3020.0, "L": 2990.0, "C": 3010.0},
            ]
        )

    def get_idx_bars_daily(self, **kwargs):
        self.calls.append(("growth", kwargs))
        return FakeFrame(
            [
                {"Date": "2026-08-13", "Code": "154", "O": 790.0, "H": 805.0, "L": 785.0, "C": 800.0},
                {"Date": "2026-08-14", "Code": "154", "O": 800.0, "H": 810.0, "L": 795.0, "C": 805.0},
            ]
        )


class JQuantsV2MarketDataProviderTest(unittest.TestCase):
    def test_missing_credential_fails_closed_without_client_creation(self):
        called = False

        def factory(_):
            nonlocal called
            called = True
            return FakeJQuantsClient()

        provider = JQuantsV2MarketDataProvider(api_key="", client_factory=factory)
        provider.api_key = None
        result = provider.fetch(date(2026, 8, 14), (*REQUIRED_SECURITY_CODES, *REQUIRED_BENCHMARK_CODES))
        self.assertEqual(PROVIDER_CREDENTIAL_MISSING, result.status)
        self.assertFalse(called)
        self.assertEqual((), result.records)

    def test_live_adapter_emits_seven_aligned_records_with_common_previous_close(self):
        client = FakeJQuantsClient()
        provider = JQuantsV2MarketDataProvider(
            api_key="test-key",
            client_factory=lambda key: client,
            growth250_index_code="154",
            clock=lambda: datetime(2026, 8, 14, 6, 31, tzinfo=timezone.utc),
        )
        result = provider.fetch(date(2026, 8, 14), (*REQUIRED_SECURITY_CODES, *REQUIRED_BENCHMARK_CODES))

        self.assertEqual(PROVIDER_OK, result.status)
        self.assertEqual(7, len(result.records))
        self.assertTrue(all(row.previous_market_date == date(2026, 8, 13) for row in result.records))
        self.assertTrue(all(row.previous_close is not None for row in result.records))
        self.assertEqual(
            {"JQUANTS_V2_EQ_BARS_DAILY", "JQUANTS_V2_IDX_TOPIX", "JQUANTS_V2_IDX_BARS_DAILY"},
            {row.source for row in result.records},
        )

        validation = validate_aligned_market_data(result.records, market_date=date(2026, 8, 14))
        self.assertEqual(FRESHNESS_VERIFIED_SAME_DAY, validation.freshness_status)
        self.assertTrue(validation.usable)

        call_names = [name for name, _ in client.calls]
        self.assertEqual(["eq", "topix", "growth"], call_names)
        growth_kwargs = next(kwargs for name, kwargs in client.calls if name == "growth")
        self.assertEqual("154", growth_kwargs["code"])


if __name__ == "__main__":
    unittest.main()
