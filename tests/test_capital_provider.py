from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from scripts.morning_dataset.providers.capital import CapitalProvider


SCHEMA = """
CREATE TABLE capital_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_at TEXT NOT NULL,
    cash_buying_power REAL,
    margin_buying_power REAL,
    cash_ratio REAL,
    margin_exposure REAL,
    margin_ratio REAL,
    total_exposure REAL,
    reserve_amount REAL,
    source TEXT,
    source_version TEXT
);
"""


class CapitalProviderTest(unittest.TestCase):
    def database(self, root: Path, row: tuple | None = None) -> Path:
        path = root / "history.db"
        connection = sqlite3.connect(path)
        try:
            connection.executescript(SCHEMA)
            if row is not None:
                connection.execute(
                    """
                    INSERT INTO capital_snapshots (
                        snapshot_at, cash_buying_power, margin_buying_power,
                        cash_ratio, margin_exposure, margin_ratio,
                        total_exposure, reserve_amount, source, source_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    row,
                )
            connection.commit()
        finally:
            connection.close()
        return path

    def test_ok_from_fresh_canonical_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.database(
                Path(tmp),
                ("2026-08-08T08:30:00+09:00", 1_200_000, 3_000_000, 0.24, 2_400_000, 0.48, 5_000_000, 500_000, "brokerage_snapshot", "v1"),
            )
            result = CapitalProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("OK", result.status)
            self.assertEqual("2026-08-08", result.as_of)
            self.assertEqual(1_200_000, result.data["buying_power"]["cash"])
            self.assertEqual(3_000_000, result.data["buying_power"]["margin"])
            self.assertEqual(2_400_000, result.data["margin_usage"]["exposure"])
            self.assertEqual(500_000, result.data["target_reserve"])
            self.assertIsNone(result.data["cash_available"])

    def test_future_dated_snapshot_is_partial_not_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.database(
                Path(tmp),
                ("2026-08-09T08:30:00+09:00", 100, 200, None, None, None, None, None, "synthetic", "v1"),
            )
            result = CapitalProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertEqual("2026-08-09", result.as_of)
            self.assertIn("future", result.reason)
            self.assertIsNotNone(result.data)
            self.assertEqual(100, result.data["buying_power"]["cash"])

    def test_latest_snapshot_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.database(
                Path(tmp),
                ("2026-08-07", 100, 200, None, None, None, None, None, "old", "v1"),
            )
            connection = sqlite3.connect(path)
            try:
                connection.execute(
                    "INSERT INTO capital_snapshots (snapshot_at, cash_buying_power, margin_buying_power, source) VALUES (?, ?, ?, ?)",
                    ("2026-08-08", 300, 400, "new"),
                )
                connection.commit()
            finally:
                connection.close()
            result = CapitalProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual(300, result.data["buying_power"]["cash"])
            self.assertEqual("new", result.data["capital_state"]["source"])

    def test_stale_preserves_latest_known_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.database(
                Path(tmp),
                ("2026-08-01", 100, 200, None, 300, None, None, None, "manual", "v1"),
            )
            result = CapitalProvider(path, max_age_days=3, today=date(2026, 8, 8)).collect()
            self.assertEqual("STALE", result.status)
            self.assertEqual(100, result.data["buying_power"]["cash"])
            self.assertIn("7 days old", result.reason)

    def test_fresh_snapshot_without_buying_power_is_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.database(
                Path(tmp),
                ("2026-08-08", None, None, 0.30, 500, 0.20, 2_000, 200, "manual", "v1"),
            )
            result = CapitalProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertEqual(500, result.data["margin_usage"]["exposure"])
            self.assertIn("buying-power", result.reason)

    def test_empty_snapshot_values_are_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.database(
                Path(tmp),
                ("2026-08-08", None, None, None, None, None, None, None, "manual", "v1"),
            )
            result = CapitalProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("MISSING", result.status)
            self.assertIsNone(result.data)

    def test_no_snapshot_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.database(Path(tmp))
            result = CapitalProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("MISSING", result.status)

    def test_missing_database_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = CapitalProvider(Path(tmp) / "missing.db", today=date(2026, 8, 8)).collect()
            self.assertEqual("MISSING", result.status)

    def test_missing_table_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.db"
            sqlite3.connect(path).close()
            result = CapitalProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("MISSING", result.status)

    # --- #971: finite numeric facts, true zero, strict dates, read-only ---

    def collect_row(self, row: tuple, today: date = date(2026, 8, 8)):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.database(Path(tmp), row)
            return CapitalProvider(path, today=today).collect()

    def test_text_in_real_column_is_invalid_not_ok(self):
        # SQLite REAL affinity keeps unconvertible text as text.
        result = self.collect_row(
            ("2026-08-08", "lots", 3_000_000, 0.24, 2_400_000, 0.48, 5_000_000, 500_000, "synthetic", "v1")
        )
        self.assertEqual("PARTIAL", result.status)
        self.assertIsNone(result.data["buying_power"]["cash"])
        self.assertEqual(3_000_000, result.data["buying_power"]["margin"])
        self.assertIn("cash_buying_power", result.reason)
        self.assertIn("invalid", result.reason)

    def test_infinite_nan_and_blob_values_are_invalid(self):
        for bad in (float("inf"), float("-inf"), b"\x00\x01"):
            with self.subTest(value=bad):
                result = self.collect_row(
                    ("2026-08-08", bad, 3_000_000, 0.24, 2_400_000, bad, 5_000_000, 500_000, "synthetic", "v1")
                )
                self.assertEqual("PARTIAL", result.status)
                self.assertIsNone(result.data["buying_power"]["cash"])
                self.assertIsNone(result.data["margin_usage"]["ratio"])
                self.assertIn("cash_buying_power", result.reason)
                self.assertIn("margin_ratio", result.reason)
                # Valid mixed facts are retained.
                self.assertEqual(2_400_000, result.data["margin_usage"]["exposure"])
                self.assertEqual(500_000, result.data["target_reserve"])

    def test_invalid_buying_power_alone_cannot_make_snapshot_ok(self):
        result = self.collect_row(
            ("2026-08-08", float("inf"), "n/a", None, None, None, None, None, "synthetic", "v1")
        )
        self.assertNotEqual("OK", result.status)
        self.assertEqual("MISSING", result.status)
        self.assertIsNone(result.data)
        self.assertIn("invalid", result.reason)

    def test_invalid_buying_power_with_other_facts_is_partial(self):
        result = self.collect_row(
            ("2026-08-08", "n/a", float("inf"), 0.30, 500, 0.20, 2_000, 200, "synthetic", "v1")
        )
        self.assertEqual("PARTIAL", result.status)
        self.assertIn("buying-power", result.reason)
        self.assertIn("invalid", result.reason)
        self.assertEqual(500, result.data["margin_usage"]["exposure"])

    def test_true_zero_is_a_fact_not_missing(self):
        result = self.collect_row(
            ("2026-08-08", 0, 0.0, 0.0, 0, 0.0, 0, 0, "synthetic", "v1")
        )
        self.assertEqual("OK", result.status)
        self.assertEqual(0, result.data["buying_power"]["cash"])
        self.assertEqual(0, result.data["buying_power"]["margin"])
        self.assertEqual(0, result.data["target_reserve"])
        self.assertIsNone(result.data["cash_available"])

    def test_zero_buying_power_with_null_margin_is_ok(self):
        result = self.collect_row(
            ("2026-08-08", 0, None, None, None, None, None, None, "synthetic", "v1")
        )
        self.assertEqual("OK", result.status)
        self.assertEqual(0, result.data["buying_power"]["cash"])
        self.assertIsNone(result.data["buying_power"]["margin"])

    def test_numeric_text_is_converted_by_real_affinity_and_kept(self):
        result = self.collect_row(
            ("2026-08-08", "1200000", "3000000", None, None, None, None, None, "synthetic", "v1")
        )
        self.assertEqual("OK", result.status)
        self.assertEqual(1_200_000, result.data["buying_power"]["cash"])

    def test_snapshot_at_with_suffix_or_impossible_date_is_invalid(self):
        for bad in ("2026-08-08garbage", "2026-08-08X08:30", "2026-02-30", "2026-08-08T25:00:00", " 2026-08-08", "20260808"):
            with self.subTest(snapshot_at=bad):
                result = self.collect_row(
                    (bad, 100, 200, None, None, None, None, None, "synthetic", "v1")
                )
                self.assertEqual("PARTIAL", result.status)
                self.assertIsNone(result.as_of)
                self.assertIn("strict ISO", result.reason)
                self.assertEqual(100, result.data["buying_power"]["cash"])

    def test_iso_timestamp_snapshot_at_is_accepted(self):
        for good in ("2026-08-08T08:30:00+09:00", "2026-08-08 08:30:00", "2026-08-08T08:30:00Z", "2026-08-08"):
            with self.subTest(snapshot_at=good):
                result = self.collect_row(
                    (good, 100, 200, None, None, None, None, None, "synthetic", "v1")
                )
                self.assertEqual("OK", result.status)
                self.assertEqual("2026-08-08", result.as_of)

    def test_stale_and_future_keep_status_and_report_invalid_facts(self):
        stale = self.collect_row(
            ("2026-08-01", 100, "bad", None, None, None, None, None, "synthetic", "v1")
        )
        self.assertEqual("STALE", stale.status)
        self.assertIn("7 days old", stale.reason)
        self.assertIn("margin_buying_power", stale.reason)
        self.assertIsNone(stale.data["buying_power"]["margin"])

        future = self.collect_row(
            ("2026-08-09", 100, float("inf"), None, None, None, None, None, "synthetic", "v1")
        )
        self.assertEqual("PARTIAL", future.status)
        self.assertIn("future", future.reason)
        self.assertIn("margin_buying_power", future.reason)

    def test_collect_opens_database_read_only_and_does_not_modify_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.database(
                Path(tmp),
                ("2026-08-08", 100, 200, None, None, None, None, None, "synthetic", "v1"),
            )
            before = path.read_bytes()
            calls: list[tuple] = []
            original = sqlite3.connect

            def spy(*args, **kwargs):
                calls.append((args, kwargs))
                return original(*args, **kwargs)

            sqlite3.connect = spy
            try:
                result = CapitalProvider(path, today=date(2026, 8, 8)).collect()
            finally:
                sqlite3.connect = original
            self.assertEqual("OK", result.status)
            self.assertEqual(1, len(calls))
            self.assertIn("mode=ro", calls[0][0][0])
            self.assertTrue(calls[0][1].get("uri"))
            self.assertEqual(before, path.read_bytes())
            self.assertEqual(["history.db"], sorted(p.name for p in Path(tmp).iterdir()))

    def test_non_database_file_is_missing_not_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.db"
            path.write_bytes(b"not a sqlite database" * 10)
            result = CapitalProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("MISSING", result.status)
            self.assertIn("failed to read", result.reason)


    # --- #975 review 6097792141: metadata BLOB and strict JSON integration ---

    def test_blob_metadata_is_nulled_and_not_ok(self):
        for column_index, column in ((8, "source"), (9, "source_version")):
            with self.subTest(column=column):
                row = ["2026-08-08", 1_200_000, 3_000_000, 0.24, 2_400_000, 0.48, 5_000_000, 500_000, "synthetic", "v1"]
                row[column_index] = b"\x00\xffblob"
                result = self.collect_row(tuple(row))
                self.assertEqual("PARTIAL", result.status)
                self.assertIsNone(result.data["capital_state"][column])
                self.assertIn(f"invalid non-text capital metadata set to null: {column}", result.reason)
                # Numeric facts remain intact; no value is invented.
                self.assertEqual(1_200_000, result.data["buying_power"]["cash"])
                json.dumps(result.data, ensure_ascii=False, allow_nan=False)

    def test_numeric_metadata_in_text_column_is_kept_as_text(self):
        # TEXT affinity converts numbers to text, so this is still valid text metadata.
        result = self.collect_row(
            ("2026-08-08", 100, 200, None, None, None, None, None, 42, 1.5)
        )
        self.assertEqual("OK", result.status)
        self.assertEqual("42", result.data["capital_state"]["source"])
        self.assertEqual("1.5", result.data["capital_state"]["source_version"])

    def test_null_metadata_is_allowed(self):
        result = self.collect_row(
            ("2026-08-08", 100, 200, None, None, None, None, None, None, None)
        )
        self.assertEqual("OK", result.status)
        self.assertIsNone(result.data["capital_state"]["source"])

    def test_invalid_facts_and_metadata_are_both_reported(self):
        result = self.collect_row(
            ("2026-08-08", float("inf"), 200, None, None, None, None, None, b"blob", "v1")
        )
        self.assertEqual("PARTIAL", result.status)
        self.assertIn("cash_buying_power", result.reason)
        self.assertIn("metadata set to null: source", result.reason)

    def test_provider_output_builds_a_strict_json_dataset(self):
        from scripts.morning_dataset.generator import build_dataset_from_providers

        rows = (
            ("2026-08-08", 1_200_000, 3_000_000, 0.24, 2_400_000, 0.48, 5_000_000, 500_000, "synthetic", "v1"),
            ("2026-08-08", float("inf"), "n/a", float("-inf"), None, None, None, 0, b"blob", b"\x01"),
        )
        for row in rows:
            with self.subTest(row=row[1]):
                with tempfile.TemporaryDirectory() as tmp:
                    path = self.database(Path(tmp), row)
                    dataset = build_dataset_from_providers(
                        [CapitalProvider(path, today=date(2026, 8, 8))], as_of=date(2026, 8, 8)
                    )
                json.dumps(dataset, ensure_ascii=False, allow_nan=False)
                status = next(item for item in dataset["source_status"] if item["name"] == "capital")["status"]
                self.assertIn(status, {"OK", "PARTIAL"})


if __name__ == "__main__":
    unittest.main()
