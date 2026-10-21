from __future__ import annotations

import unittest
from datetime import datetime

from scripts.monitoring.ai_key_person_watch_status import (
    classify_health,
    update_status,
    validate_status,
)


BASE = {
    "schema_version": "1.0",
    "watch": "AI_Key_Person_Watch",
    "expected_interval_minutes": 60,
    "stale_after_minutes": 150,
    "last_run_at": "2026-08-09T07:30:00+09:00",
    "last_success_at": "2026-08-09T07:30:00+09:00",
    "last_status": "OK",
    "news_delta": 0,
    "last_news_delta_at": None,
    "news_persisted": False,
    "persistence_status": "NOT_REQUIRED",
    "updated_by": "❤️レイ",
}


class AIKeyPersonWatchStatusTest(unittest.TestCase):
    def test_recent_success_is_healthy(self) -> None:
        health = classify_health(BASE, datetime.fromisoformat("2026-08-09T08:30:00+09:00"))
        self.assertEqual("HEALTHY", health.state)
        self.assertEqual(60.0, health.age_minutes)

    def test_old_success_is_stale(self) -> None:
        health = classify_health(BASE, datetime.fromisoformat("2026-08-09T10:01:00+09:00"))
        self.assertEqual("STALE", health.state)

    def test_missing_success_is_stale(self) -> None:
        payload = dict(BASE, last_success_at=None, last_status="UNKNOWN")
        health = classify_health(payload, datetime.fromisoformat("2026-08-09T08:30:00+09:00"))
        self.assertEqual("STALE", health.state)
        self.assertIsNone(health.age_minutes)

    def test_latest_error_is_degraded_when_recent_success_exists(self) -> None:
        payload = dict(BASE, last_status="ERROR", last_run_at="2026-08-09T08:20:00+09:00")
        health = classify_health(payload, datetime.fromisoformat("2026-08-09T08:30:00+09:00"))
        self.assertEqual("DEGRADED", health.state)

    def test_pending_persistence_is_degraded(self) -> None:
        payload = dict(BASE, news_delta=1, news_persisted=False, persistence_status="PENDING_PERSIST")
        health = classify_health(payload, datetime.fromisoformat("2026-08-09T08:30:00+09:00"))
        self.assertEqual("DEGRADED", health.state)

    def test_invalid_status_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_status(dict(BASE, last_status="BROKEN"))

    def test_naive_timestamp_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_status(dict(BASE, last_success_at="2026-08-09T07:30:00"))

    def test_future_success_beyond_clock_skew_is_degraded(self) -> None:
        payload = dict(
            BASE,
            last_run_at="2026-08-09T09:00:00+09:00",
            last_success_at="2026-08-09T09:00:00+09:00",
        )
        health = classify_health(payload, datetime.fromisoformat("2026-08-09T08:30:00+09:00"))
        self.assertEqual("DEGRADED", health.state)
        self.assertIn("future", health.reason)

    def test_small_future_clock_skew_is_tolerated(self) -> None:
        payload = dict(
            BASE,
            last_run_at="2026-08-09T08:34:00+09:00",
            last_success_at="2026-08-09T08:34:00+09:00",
        )
        health = classify_health(payload, datetime.fromisoformat("2026-08-09T08:30:00+09:00"))
        self.assertEqual("HEALTHY", health.state)

    def test_success_after_last_run_is_degraded(self) -> None:
        payload = dict(
            BASE,
            last_run_at="2026-08-09T08:00:00+09:00",
            last_success_at="2026-08-09T08:01:00+09:00",
        )
        health = classify_health(payload, datetime.fromisoformat("2026-08-09T08:30:00+09:00"))
        self.assertEqual("DEGRADED", health.state)
        self.assertIn("last_success_at is later than last_run_at", health.reason)

    def test_news_delta_after_last_run_is_degraded(self) -> None:
        payload = dict(
            BASE,
            last_run_at="2026-08-09T08:00:00+09:00",
            last_success_at="2026-08-09T08:00:00+09:00",
            last_news_delta_at="2026-08-09T08:01:00+09:00",
        )
        health = classify_health(payload, datetime.fromisoformat("2026-08-09T08:30:00+09:00"))
        self.assertEqual("DEGRADED", health.state)
        self.assertIn("last_news_delta_at is later than last_run_at", health.reason)

    def test_update_status_success_delta_zero(self) -> None:
        initial = {
            "schema_version": "1.0",
            "watch": "AI_Key_Person_Watch",
            "expected_interval_minutes": 60,
            "stale_after_minutes": 150,
            "last_run_at": "2026-08-09T07:30:00+09:00",
            "last_success_at": "2026-08-09T07:30:00+09:00",
            "last_status": "OK",
            "news_delta": 2,
            "last_news_delta_at": "2026-08-09T07:30:00+09:00",
            "news_persisted": True,
            "persistence_status": "COMPLETED",
            "updated_by": "❤️レイ",
        }
        evidence = {
            "run_at": "2026-08-09T08:30:00+09:00",
            "status": "OK",
            "news_delta": 0,
            "news_persisted": False,
            "persistence_status": "NOT_REQUIRED",
        }
        updated = update_status(initial, evidence)
        self.assertEqual("2026-08-09T08:30:00+09:00", updated["last_run_at"])
        self.assertEqual("2026-08-09T08:30:00+09:00", updated["last_success_at"])
        self.assertEqual("2026-08-09T07:30:00+09:00", updated["last_news_delta_at"])
        self.assertEqual(0, updated["news_delta"])
        self.assertFalse(updated["news_persisted"])
        self.assertEqual("NOT_REQUIRED", updated["persistence_status"])

        health = classify_health(updated, datetime.fromisoformat("2026-08-09T08:35:00+09:00"))
        self.assertEqual("HEALTHY", health.state)

    def test_update_status_success_delta_positive(self) -> None:
        initial = dict(BASE, last_run_at="2026-08-09T07:30:00+09:00", last_success_at="2026-08-09T07:30:00+09:00")
        evidence = {
            "run_at": "2026-08-09T08:30:00+09:00",
            "status": "OK",
            "news_delta": 3,
            "news_persisted": True,
            "persistence_status": "COMPLETED",
        }
        updated = update_status(initial, evidence)
        self.assertEqual("2026-08-09T08:30:00+09:00", updated["last_run_at"])
        self.assertEqual("2026-08-09T08:30:00+09:00", updated["last_success_at"])
        self.assertEqual("2026-08-09T08:30:00+09:00", updated["last_news_delta_at"])
        self.assertEqual(3, updated["news_delta"])
        self.assertTrue(updated["news_persisted"])
        self.assertEqual("COMPLETED", updated["persistence_status"])

    def test_update_status_error_run(self) -> None:
        initial = dict(
            BASE,
            last_run_at="2026-08-09T07:30:00+09:00",
            last_success_at="2026-08-09T07:30:00+09:00",
            last_news_delta_at="2026-08-09T07:30:00+09:00",
        )
        evidence = {
            "run_at": "2026-08-09T08:30:00+09:00",
            "status": "ERROR",
            "news_delta": 0,
            "news_persisted": False,
            "persistence_status": "NOT_REQUIRED",
        }
        updated = update_status(initial, evidence)
        self.assertEqual("2026-08-09T08:30:00+09:00", updated["last_run_at"])
        self.assertEqual("2026-08-09T07:30:00+09:00", updated["last_success_at"])
        self.assertEqual("2026-08-09T07:30:00+09:00", updated["last_news_delta_at"])
        self.assertEqual("ERROR", updated["last_status"])

        health = classify_health(updated, datetime.fromisoformat("2026-08-09T08:35:00+09:00"))
        self.assertEqual("DEGRADED", health.state)

    def test_update_status_pending_persistence_is_degraded(self) -> None:
        initial = dict(BASE, last_run_at="2026-08-09T07:30:00+09:00", last_success_at="2026-08-09T07:30:00+09:00")
        evidence = {
            "run_at": "2026-08-09T08:30:00+09:00",
            "status": "OK",
            "news_delta": 1,
            "news_persisted": False,
            "persistence_status": "PENDING_PERSIST",
        }
        updated = update_status(initial, evidence)
        self.assertEqual("PENDING_PERSIST", updated["persistence_status"])

        health = classify_health(updated, datetime.fromisoformat("2026-08-09T08:35:00+09:00"))
        self.assertEqual("DEGRADED", health.state)

    def test_update_status_invalid_evidence_rejected(self) -> None:
        valid_evidence = {
            "run_at": "2026-08-09T08:30:00+09:00",
            "status": "OK",
            "news_delta": 0,
            "news_persisted": False,
            "persistence_status": "NOT_REQUIRED",
        }
        with self.assertRaises(ValueError):
            update_status(BASE, dict(valid_evidence, run_at="2026-08-09T08:30:00"))  # Naive timestamp

        with self.assertRaises(ValueError):
            update_status(BASE, dict(valid_evidence, status="INVALID"))

        with self.assertRaises(ValueError):
            update_status(BASE, dict(valid_evidence, news_delta=-1))

        with self.assertRaises(ValueError):
            update_status(BASE, dict(valid_evidence, news_persisted="yes"))

    def test_update_status_missing_required_fields_raises_value_error(self) -> None:
        valid_evidence = {
            "run_at": "2026-08-09T08:30:00+09:00",
            "status": "OK",
            "news_delta": 0,
            "news_persisted": False,
            "persistence_status": "NOT_REQUIRED",
        }
        required_fields = ("run_at", "status", "news_delta", "news_persisted", "persistence_status")
        for field in required_fields:
            incomplete = dict(valid_evidence)
            del incomplete[field]
            with self.assertRaises(ValueError) as ctx:
                update_status(BASE, incomplete)
            self.assertIn("missing required evidence field", str(ctx.exception))
            self.assertIn(field, str(ctx.exception))

    def test_update_status_older_evidence_rejected(self) -> None:
        initial = dict(BASE, last_run_at="2026-08-09T08:30:00+09:00", last_success_at="2026-08-09T08:30:00+09:00")
        older_evidence = {
            "run_at": "2026-08-09T08:29:59+09:00",
            "status": "OK",
            "news_delta": 0,
            "news_persisted": False,
            "persistence_status": "NOT_REQUIRED",
        }
        with self.assertRaises(ValueError) as ctx:
            update_status(initial, older_evidence)
        self.assertIn("older than current last_run_at", str(ctx.exception))

    def test_update_status_exact_replay_idempotent(self) -> None:
        initial = dict(
            BASE,
            last_run_at="2026-08-09T08:30:00+09:00",
            last_success_at="2026-08-09T08:30:00+09:00",
            last_status="OK",
            news_delta=0,
            news_persisted=False,
            persistence_status="NOT_REQUIRED",
        )
        exact_evidence = {
            "run_at": "2026-08-09T08:30:00+09:00",
            "status": "OK",
            "news_delta": 0,
            "news_persisted": False,
            "persistence_status": "NOT_REQUIRED",
        }
        updated = update_status(initial, exact_evidence)
        self.assertEqual(initial, updated)

    def test_update_status_conflicting_same_timestamp_rejected(self) -> None:
        initial = dict(
            BASE,
            last_run_at="2026-08-09T08:30:00+09:00",
            last_success_at="2026-08-09T08:30:00+09:00",
            last_status="OK",
            news_delta=0,
            news_persisted=False,
            persistence_status="NOT_REQUIRED",
        )
        conflicting_evidence = {
            "run_at": "2026-08-09T08:30:00+09:00",
            "status": "ERROR",
            "news_delta": 0,
            "news_persisted": False,
            "persistence_status": "NOT_REQUIRED",
        }
        with self.assertRaises(ValueError) as ctx:
            update_status(initial, conflicting_evidence)
        self.assertIn("conflicting evidence for same run_at", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
