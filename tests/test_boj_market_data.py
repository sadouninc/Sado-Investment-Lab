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
    FRESHNESS_VERIFIED_T_PLUS_1,
    PROVIDER_CREDENTIAL_MISSING,
    MarketDataRecord,
    ProviderResult,
    build_equity_reaction_metrics,
    build_equity_reaction_transaction,
    validate_aligned_market_data,
)


FIXTURE = Path(__file__).parent / "fixtures" / "boj_market_data_2026-08-14.json"


class BojMarketDataTest(unittest.TestCase):
    def load_replay(self):
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        market_date = date.fromisoformat(payload["market_date"])
        rows = []
        for row in payload["records"]:
            normalized = dict(row)
            normalized["market_date"] = market_date
            normalized["previous_market_date"] = date.fromisoformat(row["previous_market_date"])
            rows.append(MarketDataRecord(**normalized))
        return payload, market_date, rows

    def test_2026_08_14_replay_generates_primary_benchmark_excess_returns(self):
        payload, market_date, rows = self.load_replay()
        self.assertTrue(payload["not_market_truth"])
        self.assertEqual("DETERMINISTIC_CONTRACT_ONLY", payload["fixture_kind"])

        result = validate_aligned_market_data(rows, market_date=market_date)
        self.assertEqual(FRESHNESS_VERIFIED_SAME_DAY, result.freshness_status)
        self.assertEqual(7, len(result.records))

        metrics = build_equity_reaction_metrics(result)
        mapping = {row["security_code"]: row["benchmark_code"] for row in metrics}
        self.assertEqual("TOPIX", mapping["3778"])
        self.assertEqual("TSE_GROWTH_250", mapping["247A"])
        self.assertEqual("TSE_GROWTH_250", mapping["9166"])
        self.assertEqual("TOPIX", mapping["3110"])
        self.assertEqual("TOPIX", mapping["4063"])
        self.assertTrue(all(row["return_basis"] == "close_to_close" for row in metrics))
        self.assertTrue(all("excess_return_pt" in row for row in metrics))

        transaction = build_equity_reaction_transaction(
            policy_transaction_id=payload["policy_transaction_id"],
            market_date=market_date,
            validation=result,
        )
        self.assertEqual("equity-reaction", transaction["transaction_type"])
        self.assertEqual("2026-08-14-policy-step-002", transaction["policy_transaction_id"])
        ai_row = next(row for row in transaction["metrics"] if row["security_code"] == "247A")
        self.assertIn("EARNINGS_CONFOUND", ai_row["confounds"])
        self.assertIsNone(transaction["decision"])
        self.assertTrue(transaction["guardrails"]["policy_record_immutable"])
        self.assertTrue(transaction["guardrails"]["partial_success_rejected"])
        self.assertFalse(transaction["guardrails"]["buy_sell_generation"])

    def test_t_plus_1_morning_is_explicitly_usable(self):
        _, market_date, rows = self.load_replay()
        rows = [replace(row, source_timestamp="2026-08-15T08:00:00+09:00") for row in rows]
        result = validate_aligned_market_data(rows, market_date=market_date)
        self.assertEqual(FRESHNESS_VERIFIED_T_PLUS_1, result.freshness_status)
        self.assertTrue(result.usable)

    def test_utc_timestamp_normalizes_to_t_plus_1_in_tokyo(self):
        _, market_date, rows = self.load_replay()
        rows = [replace(row, source_timestamp="2026-08-14T23:00:00+00:00") for row in rows]
        result = validate_aligned_market_data(rows, market_date=market_date)
        self.assertEqual(FRESHNESS_VERIFIED_T_PLUS_1, result.freshness_status)
        self.assertTrue(result.usable)

    def test_after_t_plus_1_morning_is_stale(self):
        _, market_date, rows = self.load_replay()
        rows = [replace(row, source_timestamp="2026-08-15T13:00:00+09:00") for row in rows]
        result = validate_aligned_market_data(rows, market_date=market_date)
        self.assertEqual(FRESHNESS_STALE_SOURCE, result.freshness_status)
        self.assertEqual((), result.records)

    def test_naive_source_timestamp_fails_closed(self):
        _, market_date, rows = self.load_replay()
        rows = [replace(row, source_timestamp="2026-08-15T08:00:00") for row in rows]
        result = validate_aligned_market_data(rows, market_date=market_date)
        self.assertEqual(FRESHNESS_UNKNOWN, result.freshness_status)
        self.assertIn("source_timestamp_unknown", result.reasons)
        self.assertEqual((), result.records)

    def test_missing_required_instrument_fails_closed(self):
        _, market_date, rows = self.load_replay()
        rows = [row for row in rows if row.instrument_code != "TOPIX"]
        result = validate_aligned_market_data(rows, market_date=market_date)
        self.assertEqual(FRESHNESS_UNKNOWN, result.freshness_status)
        self.assertIn("missing:TOPIX", result.reasons)
        self.assertEqual((), result.records)

    def test_missing_previous_close_fails_closed(self):
        _, market_date, rows = self.load_replay()
        rows = [replace(row, previous_close=None) if row.instrument_code == "3778" else row for row in rows]
        result = validate_aligned_market_data(rows, market_date=market_date)
        self.assertEqual(FRESHNESS_UNKNOWN, result.freshness_status)
        self.assertIn("previous_close_missing:3778", result.reasons)
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

    def test_provider_credential_missing_is_explicit(self):
        result = ProviderResult(PROVIDER_CREDENTIAL_MISSING, reasons=("JQUANTS_API_KEY",))
        self.assertEqual(PROVIDER_CREDENTIAL_MISSING, result.status)
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
