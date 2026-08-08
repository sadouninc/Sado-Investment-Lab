from __future__ import annotations

import unittest
from datetime import datetime

from scripts.monitoring.ai_key_person_watch_status import classify_health, validate_status


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


if __name__ == "__main__":
    unittest.main()
