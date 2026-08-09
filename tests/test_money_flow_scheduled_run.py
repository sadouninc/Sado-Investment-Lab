from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone

from scripts.money_flow_scheduled_run import market_session_guard


THEME_CONFIG = {
    "benchmark": {"name": "TOPIX", "symbol": "^TOPX"},
    "history_range": "6mo",
    "interval": "1d",
    "themes": [
        {
            "id": "theme:ai-data-center-power-infrastructure",
            "name": "AI Data Center / Power Infrastructure",
            "membership_as_of": "2026-08-09",
            "members": [
                {"security_code": "6622", "company_name": "ダイヘン", "symbol": "6622.T"},
                {"security_code": "6504", "company_name": "富士電機", "symbol": "6504.T"},
                {"security_code": "6508", "company_name": "明電舎", "symbol": "6508.T"},
            ],
        }
    ],
}


def chart(last_day: date) -> dict:
    start = datetime.combine(last_day - timedelta(days=79), datetime.min.time(), tzinfo=timezone.utc)
    timestamps = [int((start + timedelta(days=i)).timestamp()) for i in range(80)]
    return {
        "chart": {
            "result": [
                {
                    "timestamp": timestamps,
                    "indicators": {"quote": [{"close": [100 + i for i in range(80)], "volume": [100] * 80}]},
                }
            ],
            "error": None,
        }
    }


class MoneyFlowScheduledRunTests(unittest.TestCase):
    def test_current_session_is_ready(self):
        as_of = date(2026, 8, 10)

        def fetcher(symbol: str, range_: str, interval: str) -> dict:
            return chart(as_of)

        result = market_session_guard(
            as_of=as_of,
            theme_id="theme:ai-data-center-power-infrastructure",
            theme_config=THEME_CONFIG,
            fetcher=fetcher,
        )
        self.assertTrue(result["ready"])
        self.assertEqual(result["reason"], "CURRENT_MARKET_SESSION")

    def test_exchange_holiday_does_not_persist_previous_session_as_today(self):
        as_of = date(2026, 8, 11)
        previous_session = date(2026, 8, 10)

        def fetcher(symbol: str, range_: str, interval: str) -> dict:
            return chart(previous_session)

        result = market_session_guard(
            as_of=as_of,
            theme_id="theme:ai-data-center-power-infrastructure",
            theme_config=THEME_CONFIG,
            fetcher=fetcher,
        )
        self.assertFalse(result["ready"])
        self.assertEqual(result["reason"], "MARKET_SESSION_NOT_CURRENT")
        self.assertEqual(result["benchmark_as_of"], previous_session.isoformat())

    def test_stale_member_fails_closed_instead_of_mixing_dates(self):
        as_of = date(2026, 8, 10)

        def fetcher(symbol: str, range_: str, interval: str) -> dict:
            if symbol == "6508.T":
                return chart(date(2026, 8, 9))
            return chart(as_of)

        result = market_session_guard(
            as_of=as_of,
            theme_id="theme:ai-data-center-power-infrastructure",
            theme_config=THEME_CONFIG,
            fetcher=fetcher,
        )
        self.assertFalse(result["ready"])
        self.assertEqual(result["reason"], "MEMBER_MARKET_DATA_STALE")
        self.assertEqual(result["stale_members"], ["6508"])

    def test_unavailable_one_member_can_remain_explicit_partial_input(self):
        as_of = date(2026, 8, 10)

        def fetcher(symbol: str, range_: str, interval: str) -> dict:
            if symbol == "6508.T":
                raise RuntimeError("unavailable")
            return chart(as_of)

        result = market_session_guard(
            as_of=as_of,
            theme_id="theme:ai-data-center-power-infrastructure",
            theme_config=THEME_CONFIG,
            fetcher=fetcher,
        )
        self.assertTrue(result["ready"])
        self.assertEqual(result["unavailable_members"], ["6508"])


if __name__ == "__main__":
    unittest.main()
