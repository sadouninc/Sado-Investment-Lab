from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from scripts.morning_dataset.providers.events import EventsProvider


class EventsProviderTest(unittest.TestCase):
    def write(self, root: Path, payload: dict) -> Path:
        path = root / "calendar.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def complete_payload(self, as_of: str = "2026-08-08") -> dict:
        return {
            "as_of": as_of,
            "source": "official/manual-reviewed aggregation",
            "coverage": {
                "earnings": True,
                "economic": True,
                "policy": True,
                "market_calendar": True,
                "company": True,
            },
            "events": {
                "earnings": [
                    {"title": "Example earnings", "date": "2026-08-08", "security_code": "9999", "source": "https://example.invalid/ir"}
                ],
                "economic": [
                    {"title": "Example economic indicator", "scheduled_at": "2026-08-08T21:30:00+09:00", "source": "official"}
                ],
                "policy": [],
                "market_calendar": [],
                "company": [],
            },
        }

    def test_ok_for_fresh_complete_calendar(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), self.complete_payload())
            result = EventsProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("OK", result.status)
            self.assertEqual("2026-08-08", result.as_of)
            self.assertEqual(1, len(result.data["earnings"]))
            self.assertEqual(1, len(result.data["economic"]))

    def test_stale_calendar_preserves_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), self.complete_payload("2026-08-05"))
            result = EventsProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("STALE", result.status)
            self.assertTrue(result.data["earnings"])

    def test_future_dated_complete_calendar_is_partial_not_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), self.complete_payload("2026-08-09"))
            result = EventsProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertEqual("2026-08-09", result.as_of)
            self.assertIn("future", result.reason)
            self.assertIsNotNone(result.data)
            self.assertEqual(1, len(result.data["earnings"]))
            self.assertEqual(1, len(result.data["economic"]))

    def test_future_dated_explicit_empty_calendar_is_not_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = self.complete_payload("2026-08-09")
            for key in payload["events"]:
                payload["events"][key] = []
            payload["empty_confirmed"] = True
            path = self.write(Path(tmp), payload)
            result = EventsProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertEqual("2026-08-09", result.as_of)
            self.assertIn("future", result.reason)
            self.assertIsNotNone(result.data)
            self.assertEqual([], result.data["earnings"])

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = EventsProvider(Path(tmp) / "missing.json", today=date(2026, 8, 8)).collect()
            self.assertEqual("MISSING", result.status)

    def test_partial_when_coverage_not_explicitly_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = self.complete_payload()
            payload["coverage"]["policy"] = False
            path = self.write(Path(tmp), payload)
            result = EventsProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertIn("coverage", result.reason)

    def test_partial_when_event_item_is_malformed(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = self.complete_payload()
            payload["events"]["company"] = [{"title": "missing date"}]
            path = self.write(Path(tmp), payload)
            result = EventsProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertEqual([], result.data["company"])

    def test_empty_calendar_requires_explicit_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = self.complete_payload()
            for key in payload["events"]:
                payload["events"][key] = []
            path = self.write(Path(tmp), payload)
            result = EventsProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("MISSING", result.status)

            payload["empty_confirmed"] = True
            path = self.write(Path(tmp), payload)
            result = EventsProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("OK", result.status)

    # --- #970: strict dates, containers, verified-empty and read errors ---

    def empty_payload(self, as_of: str = "2026-08-08") -> dict:
        payload = self.complete_payload(as_of)
        for key in payload["events"]:
            payload["events"][key] = []
        payload["empty_confirmed"] = True
        return payload

    def collect(self, payload: dict, today: date = date(2026, 8, 8)):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), payload)
            return EventsProvider(path, today=today).collect()

    def collect_text(self, text: str | bytes):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "calendar.json"
            if isinstance(text, bytes):
                path.write_bytes(text)
            else:
                path.write_text(text, encoding="utf-8")
            return EventsProvider(path, today=date(2026, 8, 8)).collect()

    def test_as_of_with_arbitrary_suffix_is_not_truncated(self):
        for bad in ("2026-08-08garbage", "2026-08-08X10:00", "2026-08-08T25:00:00", " 2026-08-08"):
            with self.subTest(as_of=bad):
                result = self.collect(self.complete_payload(bad))
                self.assertNotEqual("OK", result.status)
                self.assertEqual("PARTIAL", result.status)
                self.assertIsNone(result.as_of)
                self.assertIn("explicit calendar as_of is invalid", result.reason)
                # Valid rows are preserved, only the date is unusable.
                self.assertEqual(1, len(result.data["earnings"]))

    def test_impossible_or_wrong_typed_as_of_is_invalid(self):
        for bad in ("2026-02-30", "2026-13-01", "20260808", "", 20260808, True, ["2026-08-08"]):
            with self.subTest(as_of=bad):
                result = self.collect(self.complete_payload(bad))
                self.assertEqual("PARTIAL", result.status)
                self.assertIsNone(result.as_of)

    def test_iso_timestamp_as_of_is_accepted(self):
        for good in ("2026-08-08T06:00:00+09:00", "2026-08-08 06:00:00", "2026-08-08T06:00:00Z"):
            with self.subTest(as_of=good):
                result = self.collect(self.complete_payload(good))
                self.assertEqual("OK", result.status)
                self.assertEqual("2026-08-08", result.as_of)

    def test_invalid_explicit_as_of_is_not_rescued_by_generated_at(self):
        payload = self.complete_payload("not-a-date")
        payload["generated_at"] = "2026-08-08T06:00:00+09:00"
        result = self.collect(payload)
        self.assertEqual("PARTIAL", result.status)
        self.assertIsNone(result.as_of)
        self.assertIn("explicit calendar as_of is invalid", result.reason)

    def test_empty_string_explicit_as_of_is_not_rescued_by_generated_at(self):
        payload = self.complete_payload("")
        payload["generated_at"] = "2026-08-08T06:00:00+09:00"
        result = self.collect(payload)
        self.assertEqual("PARTIAL", result.status)
        self.assertIsNone(result.as_of)

    def test_generated_at_is_used_only_when_as_of_is_absent(self):
        payload = self.complete_payload()
        del payload["as_of"]
        payload["generated_at"] = "2026-08-08T06:00:00+09:00"
        result = self.collect(payload)
        self.assertEqual("OK", result.status)
        self.assertEqual("2026-08-08", result.as_of)

        payload["generated_at"] = "2026-08-08nonsense"
        result = self.collect(payload)
        self.assertEqual("PARTIAL", result.status)
        self.assertIsNone(result.as_of)

    def test_event_with_invalid_date_is_excluded_and_not_ok(self):
        payload = self.complete_payload()
        payload["events"]["company"] = [
            {"title": "suffix date", "date": "2026-08-08 sometime"},
            {"title": "impossible date", "date": "2026-02-30"},
            {"title": "bad timestamp", "scheduled_at": "2026-08-08T99:00"},
            {"title": "non-string date", "date": 20260808},
            {"title": "valid date with bad timestamp", "date": "2026-08-08", "scheduled_at": "tomorrow"},
            {"title": "valid company event", "date": "2026-08-08"},
        ]
        result = self.collect(payload)
        self.assertEqual("PARTIAL", result.status)
        self.assertIn("ignored 5 malformed event item(s)", result.reason)
        self.assertEqual(["valid company event"], [e["title"] for e in result.data["company"]])
        # Other valid categories are retained.
        self.assertEqual(1, len(result.data["earnings"]))
        self.assertEqual(1, len(result.data["economic"]))

    def test_wrong_events_container_does_not_fall_back_to_top_level(self):
        for container in ([], "events", 1, None):
            with self.subTest(container=container):
                payload = self.empty_payload()
                payload["events"] = container
                # Top-level categories must not be read when "events" is present.
                for key in ("earnings", "economic", "policy", "market_calendar", "company"):
                    payload[key] = []
                result = self.collect(payload)
                self.assertEqual("MISSING", result.status)
                self.assertIn("'events' must be a JSON object", result.reason)

    def test_legacy_flat_calendar_without_events_key_still_reads(self):
        payload = self.complete_payload()
        events = payload.pop("events")
        payload.update(events)
        result = self.collect(payload)
        self.assertEqual("OK", result.status)
        self.assertEqual(1, len(result.data["earnings"]))

    def test_empty_confirmed_with_missing_category_is_not_verified_empty(self):
        payload = self.empty_payload()
        del payload["events"]["policy"]
        result = self.collect(payload)
        self.assertEqual("MISSING", result.status)
        self.assertIn("missing categories: policy", result.reason)

    def test_empty_confirmed_with_malformed_category_is_not_verified_empty(self):
        payload = self.empty_payload()
        payload["events"]["policy"] = {"not": "a list"}
        result = self.collect(payload)
        self.assertEqual("MISSING", result.status)
        self.assertIn("malformed", result.reason)

    def test_empty_confirmed_with_only_malformed_items_is_not_verified_empty(self):
        payload = self.empty_payload()
        payload["events"]["company"] = [{"title": "no date"}, "prose"]
        result = self.collect(payload)
        self.assertEqual("MISSING", result.status)
        self.assertIn("ignored 2 malformed event item(s)", result.reason)

    def test_empty_confirmed_without_complete_coverage_is_not_verified_empty(self):
        for coverage in ({"earnings": True}, None, "complete", {key: "true" for key in ("earnings", "economic", "policy", "market_calendar", "company")}):
            with self.subTest(coverage=coverage):
                payload = self.empty_payload()
                payload["coverage"] = coverage
                result = self.collect(payload)
                self.assertEqual("MISSING", result.status)
                self.assertIn("coverage", result.reason)

    def test_empty_confirmed_must_be_boolean_true(self):
        for flag in ("true", 1, False, None):
            with self.subTest(flag=flag):
                payload = self.empty_payload()
                payload["empty_confirmed"] = flag
                result = self.collect(payload)
                self.assertEqual("MISSING", result.status)
                self.assertIn("empty_confirmed", result.reason)

    def test_empty_confirmed_with_invalid_date_is_not_verified_empty(self):
        for bad in ("2026-08-08garbage", "2026-02-30", None):
            with self.subTest(as_of=bad):
                payload = self.empty_payload()
                payload["as_of"] = bad
                result = self.collect(payload)
                self.assertEqual("MISSING", result.status)
                self.assertIsNone(result.as_of)
                self.assertIn("as_of", result.reason)

    def test_valid_verified_empty_day_is_ok_and_stale_stays_stale(self):
        result = self.collect(self.empty_payload())
        self.assertEqual("OK", result.status)
        self.assertEqual("2026-08-08", result.as_of)
        self.assertTrue(all(result.data[key] == [] for key in ("earnings", "economic", "policy", "market_calendar", "company")))

        stale = self.collect(self.empty_payload("2026-08-05"))
        self.assertEqual("STALE", stale.status)

    def test_invalid_utf8_is_missing_not_exception(self):
        result = self.collect_text(b'{"as_of": "2026-08-08", "source": "\xff\xfe"}')
        self.assertEqual("MISSING", result.status)
        self.assertIn("failed to read", result.reason)

    def test_malformed_json_is_missing(self):
        result = self.collect_text('{"as_of": "2026-08-08", "events": {')
        self.assertEqual("MISSING", result.status)
        self.assertIn("failed to read", result.reason)

    def test_non_object_json_is_missing(self):
        result = self.collect_text('["2026-08-08"]')
        self.assertEqual("MISSING", result.status)
        self.assertIn("must be a JSON object", result.reason)

    def test_non_standard_constants_and_oversized_integers_are_missing(self):
        for literal in ("NaN", "Infinity", "-Infinity", "9" * 70, "9" * 5000):
            with self.subTest(literal=literal[:12]):
                payload = json.dumps(self.complete_payload())
                text = payload[:-1] + f', "importance": {literal}}}'
                result = self.collect_text(text)
                self.assertEqual("MISSING", result.status)
                self.assertIn("failed to read", result.reason)

    def test_ordinary_integer_fields_are_preserved(self):
        payload = self.complete_payload()
        payload["events"]["earnings"][0]["importance"] = 3
        result = self.collect(payload)
        self.assertEqual("OK", result.status)
        self.assertEqual(3, result.data["earnings"][0]["importance"])


if __name__ == "__main__":
    unittest.main()
