from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from scripts.morning_dataset.providers.candidates import CandidatesProvider


SCHEMA = """
CREATE TABLE candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at TEXT NOT NULL,
    security_code TEXT,
    horizon TEXT,
    universe_state TEXT,
    long_score REAL,
    today_score REAL,
    risk_score REAL,
    personal_fit REAL,
    capital_feasibility REAL,
    rotation_score REAL,
    rank INTEGER,
    status TEXT,
    confidence REAL,
    model_name TEXT,
    model_version TEXT
);
CREATE TABLE candidate_factors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL,
    factor_type TEXT,
    factor_key TEXT,
    value_numeric REAL,
    value_text TEXT,
    contribution REAL,
    polarity TEXT,
    source_reference TEXT
);
"""


class CandidatesProviderTest(unittest.TestCase):
    def db(self, root: Path) -> Path:
        path = root / "history.db"
        conn = sqlite3.connect(path)
        conn.executescript(SCHEMA)
        conn.commit()
        conn.close()
        return path

    def insert(self, path: Path, generated_at: str, code: str | None, rank: int, status: str | None, today_score: float = 80):
        conn = sqlite3.connect(path)
        cur = conn.execute(
            """
            INSERT INTO candidates (
                generated_at, security_code, horizon, universe_state,
                long_score, today_score, risk_score, personal_fit,
                capital_feasibility, rotation_score, rank, status,
                confidence, model_name, model_version
            ) VALUES (?, ?, 'SHORT_SWING', 'ACTIVE', 70, ?, 20, 80, 90, 60, ?, ?, 0.8, 'candidate-v1', '1')
            """,
            (generated_at, code, today_score, rank, status),
        )
        conn.commit()
        conn.close()
        return cur.lastrowid

    def test_reads_latest_snapshot_in_rank_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.db(Path(tmp))
            self.insert(path, "2026-08-07T08:00:00+09:00", "1111", 1, "WATCH")
            self.insert(path, "2026-08-08T08:00:00+09:00", "2222", 2, "WATCH", 85)
            cid = self.insert(path, "2026-08-08T08:00:00+09:00", "3333", 1, "BUY_CANDIDATE", 90)
            conn = sqlite3.connect(path)
            conn.execute(
                "INSERT INTO candidate_factors (candidate_id, factor_type, factor_key, value_text, polarity) VALUES (?, 'positive', 'theme', 'AI strength', 'positive')",
                (cid,),
            )
            conn.commit()
            conn.close()

            result = CandidatesProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("OK", result.status)
            self.assertEqual(["3333", "2222"], [row["security_code"] for row in result.data])
            self.assertEqual("AI strength", result.data[0]["reasons"][0]["value_text"])

    def test_stale_snapshot_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.db(Path(tmp))
            self.insert(path, "2026-08-01", "1111", 1, "WATCH")
            result = CandidatesProvider(path, max_age_days=3, today=date(2026, 8, 8)).collect()
            self.assertEqual("STALE", result.status)
            self.assertTrue(result.data)

    def test_missing_database_is_missing(self):
        result = CandidatesProvider(Path("/missing/history.db")).collect()
        self.assertEqual("MISSING", result.status)

    def test_missing_table_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.db"
            sqlite3.connect(path).close()
            result = CandidatesProvider(path).collect()
            self.assertEqual("MISSING", result.status)

    def test_incomplete_identity_is_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.db(Path(tmp))
            self.insert(path, "2026-08-08", None, 1, "WATCH")
            result = CandidatesProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)

    def test_limit_keeps_compact_top_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.db(Path(tmp))
            for rank in range(1, 13):
                self.insert(path, "2026-08-08", str(1000 + rank), rank, "WATCH", 100-rank)
            result = CandidatesProvider(path, limit=5, today=date(2026, 8, 8)).collect()
            self.assertEqual(5, len(result.data))
            self.assertEqual([1, 2, 3, 4, 5], [row["rank"] for row in result.data])


class CandidatesProviderIntegrityTest(unittest.TestCase):
    """#981: SQLite affinity does not guarantee types; invalid values must not pass as OK."""

    TODAY = date(2026, 8, 8)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "history.db"
        conn = sqlite3.connect(self.path)
        conn.executescript(SCHEMA)
        conn.commit()
        conn.close()

    def tearDown(self):
        self._tmp.cleanup()

    def add(self, generated_at="2026-08-08T08:00:00+09:00", **overrides):
        values = {
            "generated_at": generated_at,
            "security_code": "1111",
            "horizon": "SHORT_SWING",
            "universe_state": "ACTIVE",
            "long_score": 70,
            "today_score": 80,
            "risk_score": 20,
            "personal_fit": 80,
            "capital_feasibility": 90,
            "rotation_score": 60,
            "rank": 1,
            "status": "WATCH",
            "confidence": 0.8,
            "model_name": "candidate-v1",
            "model_version": "1",
        }
        values.update(overrides)
        columns = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        conn = sqlite3.connect(self.path)
        cur = conn.execute(f"INSERT INTO candidates ({columns}) VALUES ({marks})", tuple(values.values()))
        conn.commit()
        conn.close()
        return cur.lastrowid

    def add_factor(self, candidate_id, **overrides):
        values = {
            "candidate_id": candidate_id,
            "factor_type": "positive",
            "factor_key": "theme",
            "value_numeric": 1.5,
            "value_text": "AI strength",
            "contribution": 0.25,
            "polarity": "positive",
            "source_reference": "research/theme.md",
        }
        values.update(overrides)
        columns = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        conn = sqlite3.connect(self.path)
        conn.execute(f"INSERT INTO candidate_factors ({columns}) VALUES ({marks})", tuple(values.values()))
        conn.commit()
        conn.close()

    def execute(self, sql, params=()):
        conn = sqlite3.connect(self.path)
        conn.execute(sql, params)
        conn.commit()
        conn.close()

    def collect(self):
        result = CandidatesProvider(self.path, today=self.TODAY).collect()
        # Whatever the status, provider output must stay strict-JSON serializable.
        json.dumps({"data": result.data, "meta": result.metadata()}, allow_nan=False)
        return result

    # --- normal / true zero -------------------------------------------------

    def test_clean_snapshot_with_factors_is_ok(self):
        cid = self.add()
        self.add_factor(cid)
        result = self.collect()
        self.assertEqual("OK", result.status)
        self.assertEqual("2026-08-08", result.as_of)
        reason = result.data[0]["reasons"][0]
        self.assertEqual(1.5, reason["value_numeric"])
        self.assertEqual("AI strength", reason["value_text"])

    def test_true_zero_and_null_facts_are_kept_as_ok(self):
        cid = self.add(long_score=0, today_score=0.0, confidence=None, rank=None)
        self.add_factor(cid, value_numeric=0, contribution=None, value_text=None)
        result = self.collect()
        self.assertEqual("OK", result.status)
        row = result.data[0]
        self.assertEqual(0, row["long_score"])
        self.assertEqual(0.0, row["today_score"])
        self.assertIsNone(row["confidence"])
        self.assertIsNone(row["rank"])
        self.assertEqual(0, row["reasons"][0]["value_numeric"])

    def test_integral_real_rank_is_stored_as_integer_and_ok(self):
        self.add(rank=2.0)
        result = self.collect()
        self.assertEqual("OK", result.status)
        self.assertEqual(2, result.data[0]["rank"])

    # --- non-finite / non-numeric / blob ------------------------------------

    def test_nonfinite_candidate_scores_are_nulled_and_partial(self):
        for value in (float("inf"), float("-inf")):
            with self.subTest(value=value):
                self.execute("DELETE FROM candidates")
                self.add(today_score=value)
                result = self.collect()
                self.assertEqual("PARTIAL", result.status)
                self.assertIsNone(result.data[0]["today_score"])
                self.assertIn("candidate[1].today_score", result.reason)

    def test_nan_is_stored_as_null_and_stays_ok(self):
        # SQLite itself converts NaN to NULL, so it surfaces as a missing fact.
        self.add(risk_score=float("nan"))
        result = self.collect()
        self.assertEqual("OK", result.status)
        self.assertIsNone(result.data[0]["risk_score"])

    def test_text_and_blob_in_numeric_columns_are_invalid(self):
        self.add(personal_fit="high", capital_feasibility=b"\x00\x01")
        result = self.collect()
        self.assertEqual("PARTIAL", result.status)
        row = result.data[0]
        self.assertIsNone(row["personal_fit"])
        self.assertIsNone(row["capital_feasibility"])
        self.assertIn("candidate[1].personal_fit", result.reason)
        self.assertIn("candidate[1].capital_feasibility", result.reason)

    def test_blob_in_text_columns_is_invalid_and_not_reencoded(self):
        self.add(model_name=b"candidate-v1", status=b"WATCH")
        result = self.collect()
        self.assertEqual("PARTIAL", result.status)
        row = result.data[0]
        self.assertIsNone(row["model_name"])
        self.assertIsNone(row["status"])
        self.assertIn("candidate[1].model_name", result.reason)

    def test_undecodable_text_does_not_abort_and_keeps_other_rows(self):
        self.add(security_code="2222", rank=2)
        self.add(security_code="1111", rank=1)
        self.execute("UPDATE candidates SET horizon = CAST(x'ff' AS TEXT) WHERE security_code = '1111'")
        result = self.collect()
        self.assertEqual("PARTIAL", result.status)
        self.assertEqual(["1111", "2222"], [row["security_code"] for row in result.data])
        self.assertIsNone(result.data[0]["horizon"])
        self.assertEqual("SHORT_SWING", result.data[1]["horizon"])
        self.assertIn("candidate[1].horizon", result.reason)

    def test_invalid_factor_values_are_nulled_and_partial(self):
        cid = self.add()
        self.add_factor(cid, value_numeric=float("inf"), contribution="big", source_reference=b"\x00")
        self.add_factor(cid)
        result = self.collect()
        self.assertEqual("PARTIAL", result.status)
        first, second = result.data[0]["reasons"]
        self.assertIsNone(first["value_numeric"])
        self.assertIsNone(first["contribution"])
        self.assertIsNone(first["source_reference"])
        self.assertEqual("AI strength", first["value_text"])
        self.assertEqual(1.5, second["value_numeric"])
        for label in ("value_numeric", "contribution", "source_reference"):
            self.assertIn(f"candidate[1].reasons[1].{label}", result.reason)

    def test_reason_never_contains_raw_values(self):
        self.add(personal_fit="SECRET-VALUE", model_name=b"SECRET-BLOB")
        result = self.collect()
        self.assertNotIn("SECRET", result.reason)

    # --- rank -----------------------------------------------------------------

    def test_non_positive_or_fractional_rank_is_invalid(self):
        for value in (0, -1, 1.5, "first", True):
            with self.subTest(value=value):
                self.execute("DELETE FROM candidates")
                self.add(rank=value)
                result = self.collect()
                if value is True:
                    # SQLite stores True as INTEGER 1; it is read back as a valid rank.
                    self.assertEqual("OK", result.status)
                    self.assertEqual(1, result.data[0]["rank"])
                    continue
                self.assertEqual("PARTIAL", result.status)
                self.assertIsNone(result.data[0]["rank"])
                self.assertIn("candidate[1].rank", result.reason)

    # --- dates ----------------------------------------------------------------

    def test_future_snapshot_is_partial_not_ok(self):
        self.add(generated_at="2026-08-09T08:00:00+09:00")
        result = self.collect()
        self.assertEqual("PARTIAL", result.status)
        self.assertEqual("2026-08-09", result.as_of)
        self.assertIn("future", result.reason)
        self.assertTrue(result.data)

    def test_malformed_generated_at_is_partial_without_truncation(self):
        for value in (
            "2026-08-08garbage",
            "2026-08-08T25:00:00",
            "2026-02-30",
            " 2026-08-08",
            "2026-08-08 ",
            "20260808",
            "2026-8-8",
        ):
            with self.subTest(value=value):
                self.execute("DELETE FROM candidates")
                self.add(generated_at=value)
                result = self.collect()
                self.assertEqual("PARTIAL", result.status)
                self.assertIsNone(result.as_of)
                self.assertIn("strict ISO", result.reason)

    def test_strict_iso_date_and_datetime_forms_are_accepted(self):
        for value in ("2026-08-08", "2026-08-08T08:00:00", "2026-08-08 08:00:00", "2026-08-08T08:00:00+09:00"):
            with self.subTest(value=value):
                self.execute("DELETE FROM candidates")
                self.add(generated_at=value)
                result = self.collect()
                self.assertEqual("OK", result.status)
                self.assertEqual("2026-08-08", result.as_of)

    def test_blob_generated_at_fails_closed(self):
        self.add(generated_at="2026-08-08")
        self.add(generated_at=b"2026-08-08", security_code="9999")
        result = self.collect()
        self.assertEqual("MISSING", result.status)
        self.assertIsNone(result.data)
        self.assertIn("generated_at", result.reason)

    def test_undecodable_generated_at_fails_closed(self):
        self.add(generated_at="2026-08-08")
        self.execute(
            "INSERT INTO candidates (generated_at, security_code, rank, status) VALUES (CAST(x'ffff' AS TEXT), '9999', 1, 'WATCH')"
        )
        result = self.collect()
        self.assertEqual("MISSING", result.status)
        self.assertIn("generated_at", result.reason)

    def test_stale_snapshot_reports_invalid_values_too(self):
        self.add(generated_at="2026-08-01", today_score=float("inf"))
        result = self.collect()
        self.assertEqual("STALE", result.status)
        self.assertIn("candidate[1].today_score", result.reason)

    # --- generator integration ----------------------------------------------

    def test_provider_output_passes_through_dataset_strict_serialization(self):
        from scripts.morning_dataset.generator import build_dataset_from_providers

        cid = self.add(today_score=float("inf"), model_name=b"x")
        self.add_factor(cid, value_numeric=float("-inf"))
        provider = CandidatesProvider(self.path, today=self.TODAY)
        dataset = build_dataset_from_providers([provider], as_of=self.TODAY)
        json.dumps(dataset, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
