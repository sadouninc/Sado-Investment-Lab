from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
import json
from pathlib import Path
import unittest

from scripts.boj_market_data import (
    FRESHNESS_SOURCE_CONFLICT,
    FRESHNESS_STALE_SOURCE,
    FRESHNESS_UNKNOWN,
    FRESHNESS_VERIFIED_SAME_DAY,
    MarketDataRecord,
    build_equity_reaction_transaction,
    validate_aligned_market_data,
)


FIXTURE = Path(__file__).parent / "fixtures" / "boj_market_data_2026-08-14.json"


class BojMarketDataTest(unittest.TestCase):
    def load_replay(self):
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        market_date = date.fromisoformat(payload["market_date"])
        rows = [
            MarketDataRecord(
                **row,
                market_date=market_date,
            )
            for row in payload["records"]
        ]
        return payload, market_date, rows

    def test_2026_08_14_replay_is_aligned_without_becoming_market_truth(self):
        payload, market_date, rows = self.load_replay()
        self.assertTrue(payload["not_market_truth"])
        self.assertEqual("DETERMINISTIC_CONTRACT_ONLY", payload["fixture_kind"])

        result = validate_aligned_market_data(rows, market_date=market_date)
        self.assertEqual(FRESHNESS_VERIFIED_SAME_DAY, result.freshness_status)
        self.assertEqual(7, len(result.records))

        transaction = build_equity_reaction_transaction(
            policy_transaction_id=payload["policy_transaction_id"],
            market_date=market_date,
            validation=result,
        )
        self.assertEqual("equity-reaction", transaction["transaction_type"])
        self.assertEqual("2026-08-14-policy-step-002", transaction["policy_transaction_id"])
        self.assertIsNone(transaction["decision"])
        self.assertTrue(transaction["guardrails"]["policy_record_immutable"])
        self.assertFalse(transaction["guardrails"]["buy_sell_generation"])

    def test_missing_required_instrument_fails_closed(self):
        _, market_date, rows = self.load_replay()
        rows = [row for row in rows if row.instrument_code != "TOPIX"]
        result = validate_aligned_market_data(rows, market_date=market_date)
        self.assertEqual(FRESHNESS_UNKNOWN, result.freshness_status)
        self.assertIn("missing:TOPIX", result.reasons)
        self.assertEqual((), result.records)

    def test_stale_record_fails_closed(self):
        _, market_date, rows = self.load_replay()
        rows = [
            replace(row, market_date=market_date - timedelta(days=1))
            if row.instrument_code == "3778"
            else row
            for row in rows
        ]
        result = validate_aligned_market_data(rows, market_date=market_date)
        self.assertEqual(FRESHNESS_STALE_SOURCE, result.freshness_status)
        self.assertIn("market_date_mismatch:3778", result.reasons)
        self.assertEqual((), result.records)

    def test_conflicting_same_day_sources_fail_closed(self):
        _, market_date, rows = self.load_replay()
        original = next(row for row in rows if row.instrument_code == "3110")
        rows.append(replace(original, source="fixture-secondary", close=original.close + 1.0))
        result = validate_aligned_market_data(rows, market_date=market_date)
        self.assertEqual(FRESHNESS_SOURCE_CONFLICT, result.freshness_status)
        self.assertIn("source_conflict:3110", result.reasons)
        self.assertEqual((), result.records)

    def test_adjustment_basis_mismatch_fails_closed(self):
        _, market_date, rows = self.load_replay()
        rows = [
            replace(row, adjustment_basis="split_adjusted")
            if row.instrument_code == "4063"
            else row
            for row in rows
        ]
        result = validate_aligned_market_data(rows, market_date=market_date)
        self.assertEqual(FRESHNESS_UNKNOWN, result.freshness_status)
        self.assertIn("adjustment_basis_mismatch:raw,split_adjusted", result.reasons)
        self.assertEqual((), result.records)

    def test_transaction_rejects_unusable_market_data(self):
        _, market_date, rows = self.load_replay()
        result = validate_aligned_market_data(rows[:-1], market_date=market_date)
        with self.assertRaisesRegex(ValueError, "market data is not usable"):
            build_equity_reaction_transaction(
                policy_transaction_id="2026-08-14-policy-step-002",
                market_date=market_date,
                validation=result,
            )


if __name__ == "__main__":
    unittest.main()
