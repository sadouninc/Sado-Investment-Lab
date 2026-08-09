from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.money_flow_history import (
    MoneyFlowHistoryError,
    compute_stability_metrics,
    evaluate_forward_performance,
    load_history,
    upsert_snapshot,
)


def snapshot(day: str, state: str, *, signal: bool, entity_id: str = "theme:gaming"):
    return {
        "schema_version": 1,
        "id": entity_id,
        "name": "Gaming",
        "kind": "THEME",
        "as_of": day,
        "state": state,
        "selection_signal": signal,
        "flow_score": 67.5 if signal else 35.0,
    }


class MoneyFlowHistoryTests(unittest.TestCase):
    def test_upsert_is_idempotent_and_conflicts_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.jsonl"
            row = snapshot("2026-08-03", "WARMING", signal=True)
            self.assertEqual(upsert_snapshot(path, row), "INSERTED")
            self.assertEqual(upsert_snapshot(path, row), "UNCHANGED")
            self.assertEqual(len(load_history(path)), 1)

            conflicting = dict(row)
            conflicting["flow_score"] = 80.0
            with self.assertRaises(MoneyFlowHistoryError):
                upsert_snapshot(path, conflicting)

    def test_history_is_sorted_by_identity_and_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.jsonl"
            upsert_snapshot(path, snapshot("2026-08-05", "INFLOW", signal=True))
            upsert_snapshot(path, snapshot("2026-08-03", "WARMING", signal=True))
            rows = load_history(path)
            self.assertEqual([row["as_of"] for row in rows], ["2026-08-03", "2026-08-05"])

    def test_forward_performance_uses_trading_sessions_and_keeps_missing_null(self):
        history = [snapshot("2026-08-03", "WARMING", signal=True)]
        prices = {
            "theme:gaming": [
                {"date": "2026-08-03", "close": 100},
                {"date": "2026-08-04", "close": 101},
                {"date": "2026-08-05", "close": 102},
                {"date": "2026-08-06", "close": 103},
                {"date": "2026-08-07", "close": 104},
                {"date": "2026-08-10", "close": 110},
            ]
        }
        result = evaluate_forward_performance(history, prices, horizons=(5, 20))[0]
        self.assertEqual(result["base_market_date"], "2026-08-03")
        self.assertEqual(result["forward_returns_pct"]["return_5d"], 10.0)
        self.assertIsNone(result["forward_returns_pct"]["return_20d"])

    def test_selection_only_excludes_hot_and_cold_rows(self):
        history = [
            snapshot("2026-08-03", "COLD", signal=False),
            snapshot("2026-08-04", "WARMING", signal=True),
            snapshot("2026-08-05", "HOT", signal=False),
        ]
        rows = evaluate_forward_performance(history, {}, horizons=(5,))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["state"], "WARMING")

    def test_stability_metrics_capture_churn_and_short_reversals(self):
        history = [
            snapshot("2026-08-03", "COLD", signal=False),
            snapshot("2026-08-04", "WARMING", signal=True),
            snapshot("2026-08-05", "COLD", signal=False),
            snapshot("2026-08-06", "WARMING", signal=True),
            snapshot("2026-08-07", "WARMING", signal=True),
            snapshot("2026-08-10", "INFLOW", signal=True),
        ]
        metrics = compute_stability_metrics(history)
        self.assertEqual(metrics["snapshot_count"], 6)
        self.assertEqual(metrics["entity_count"], 1)
        self.assertEqual(metrics["warming_run_count"], 2)
        self.assertEqual(metrics["warming_average_duration_sessions"], 1.5)
        self.assertEqual(metrics["warming_short_reversal_rate"], 0.5)
        self.assertGreater(metrics["state_change_rate"], 0)

    def test_invalid_snapshot_and_duplicate_price_dates_fail_closed(self):
        invalid = snapshot("2026-08-03", "UNKNOWN", signal=False)
        with self.assertRaises(MoneyFlowHistoryError):
            compute_stability_metrics([invalid])

        history = [snapshot("2026-08-03", "WARMING", signal=True)]
        prices = {
            "theme:gaming": [
                {"date": "2026-08-03", "close": 100},
                {"date": "2026-08-03", "close": 101},
            ]
        }
        with self.assertRaises(MoneyFlowHistoryError):
            evaluate_forward_performance(history, prices)


if __name__ == "__main__":
    unittest.main()
