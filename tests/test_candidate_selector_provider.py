from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from scripts.morning_dataset.providers.candidate_selector import CandidateSelectorProvider


class CandidateSelectorProviderTest(unittest.TestCase):
    def write_snapshot(self, root: str, payload: dict) -> Path:
        path = Path(root) / "candidate-selector.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def test_reads_fresh_resolved_candidates_without_reranking(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_snapshot(tmp, {
                "as_of": "2026-08-11",
                "ranked_candidates": [
                    {
                        "security_code": "6232",
                        "company_name": "ACSL",
                        "research_status": "NOT_STARTED",
                        "total_priority": 72.5,
                        "owner_pick": True,
                        "candidate_sources": ["OWNER_PICK"],
                        "selection_reason": "Owner Pick",
                        "last_researched_at": None,
                    }
                ],
            })
            result = CandidateSelectorProvider(path, today=date(2026, 8, 11)).collect()
            self.assertEqual("OK", result.status)
            self.assertEqual("6232", result.data[0]["security_code"])
            self.assertEqual(72.5, result.data[0]["total_priority"])
            self.assertTrue(result.data[0]["owner_pick"])

    def test_unresolved_candidate_is_not_assigned_a_guessed_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_snapshot(tmp, {
                "as_of": "2026-08-11",
                "ranked_candidates": [
                    {"security_code": None, "company_name": "原子力", "research_status": "NOT_STARTED"},
                    {"security_code": "6232", "company_name": "ACSL", "research_status": "NOT_STARTED", "total_priority": 72.5},
                ],
            })
            result = CandidateSelectorProvider(path, today=date(2026, 8, 11)).collect()
            self.assertEqual("OK", result.status)
            self.assertEqual(["6232"], [row["security_code"] for row in result.data])

    def test_only_unresolved_candidates_are_missing_not_fabricated(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_snapshot(tmp, {
                "as_of": "2026-08-11",
                "ranked_candidates": [{"security_code": None, "company_name": "送電網"}],
            })
            result = CandidateSelectorProvider(path, today=date(2026, 8, 11)).collect()
            self.assertEqual("MISSING", result.status)
            self.assertIsNone(result.data)

    def test_unscored_candidates_are_partial_and_not_arbitrarily_ranked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_snapshot(tmp, {
                "as_of": "2026-11-28",
                "ranked_candidates": [
                    {"security_code": "4063", "company_name": "信越化学工業",
                     "research_status": "STALE", "total_priority": None},
                    {"security_code": "6622", "company_name": "ダイヘン",
                     "research_status": "STALE", "total_priority": None},
                ],
            })
            result = CandidateSelectorProvider(path, today=date(2026, 11, 28)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertIn("no scored priorities", result.reason)
            self.assertEqual(["4063", "6622"], [row["security_code"] for row in result.data])
            self.assertEqual([None, None], [row["rank"] for row in result.data])

    def test_unscored_row_is_never_numbered_in_mixed_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_snapshot(tmp, {
                "as_of": "2026-11-28",
                "ranked_candidates": [
                    {"security_code": "4063", "company_name": "信越化学工業", "total_priority": None},
                    {"security_code": "6232", "company_name": "ACSL", "total_priority": 72.5},
                    {"security_code": "6622", "company_name": "ダイヘン", "total_priority": None},
                    {"security_code": "2002", "company_name": "日清製粉グループ本社", "total_priority": 68},
                ],
            })
            result = CandidateSelectorProvider(path, today=date(2026, 11, 28)).collect()
            self.assertEqual("OK", result.status)
            self.assertEqual([None, 1, None, 2], [row["rank"] for row in result.data])
            self.assertEqual(72.5, result.data[1]["total_priority"])

    def test_nonfinite_boolean_and_text_priorities_cannot_create_ranks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_snapshot(tmp, {
                "as_of": "2026-11-28",
                "ranked_candidates": [
                    {"security_code": "1111", "company_name": "NaN", "total_priority": float("nan")},
                    {"security_code": "2222", "company_name": "Infinity", "total_priority": float("inf")},
                    {"security_code": "3333", "company_name": "Boolean", "total_priority": True},
                    {"security_code": "4444", "company_name": "Text", "total_priority": "90"},
                ],
            })
            result = CandidateSelectorProvider(path, today=date(2026, 11, 28)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertEqual([None] * 4, [row["rank"] for row in result.data])

    def test_stale_snapshot_preserves_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_snapshot(tmp, {
                "as_of": "2026-08-01",
                "ranked_candidates": [{"security_code": "6232", "company_name": "ACSL"}],
            })
            result = CandidateSelectorProvider(path, today=date(2026, 8, 11), max_age_days=3).collect()
            self.assertEqual("STALE", result.status)
            self.assertEqual("6232", result.data[0]["security_code"])

    def collect(self, payload, today=date(2026, 11, 28), **kwargs):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_snapshot(tmp, payload)
            return CandidateSelectorProvider(path, today=today, **kwargs).collect()

    def write_raw(self, root: str, raw: bytes) -> Path:
        path = Path(root) / "candidate-selector.json"
        path.write_bytes(raw)
        return path

    def test_future_dated_snapshot_is_partial_and_keeps_declared_as_of(self):
        result = self.collect({
            "as_of": "2026-11-30",
            "ranked_candidates": [
                {"security_code": "6622", "company_name": "ダイヘン", "research_status": "CURRENT", "total_priority": 80},
            ],
        })
        self.assertEqual("PARTIAL", result.status)
        self.assertEqual("2026-11-30", result.as_of)
        self.assertIn("in the future", result.reason)
        self.assertEqual(["6622"], [row["security_code"] for row in result.data])
        self.assertEqual(1, result.data[0]["rank"])

    def test_same_day_and_iso_datetime_snapshot_remain_ok(self):
        for as_of in ("2026-11-28", "2026-11-28T06:30:00+09:00"):
            with self.subTest(as_of=as_of):
                result = self.collect({
                    "as_of": as_of,
                    "ranked_candidates": [{"security_code": "6622", "company_name": "ダイヘン", "total_priority": 80}],
                })
                self.assertEqual("OK", result.status)
                self.assertEqual("2026-11-28", result.as_of)

    def test_invalid_or_non_string_as_of_is_partial_not_ok(self):
        for as_of in ("2026-02-30", "2026-11-28garbage", "28/11/2026", "20261128", "2026-W48-6",
                      20261128, None, ["2026-11-28"]):
            with self.subTest(as_of=as_of):
                result = self.collect({
                    "as_of": as_of,
                    "ranked_candidates": [{"security_code": "6622", "company_name": "ダイヘン", "total_priority": 80}],
                })
                self.assertEqual("PARTIAL", result.status)
                self.assertIsNone(result.as_of)
                self.assertIn("as_of is missing or invalid", result.reason)

    def test_invalid_utf8_snapshot_is_reported_without_raising(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_raw(tmp, b'{"as_of": "2026-11-28", "x": "' + bytes([0xFF, 0xFE]) + b'"}')
            result = CandidateSelectorProvider(path, today=date(2026, 11, 28)).collect()
        self.assertEqual("MISSING", result.status)
        self.assertIn("failed to read", result.reason)

    def test_truncated_json_is_missing_not_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = b'{"as_of": "2026-11-28", "ranked_candidates": ['
            result = CandidateSelectorProvider(self.write_raw(tmp, raw), today=date(2026, 11, 28)).collect()
        self.assertEqual("MISSING", result.status)
        self.assertIn("failed to read", result.reason)

    def test_oversized_integer_literal_priority_is_malformed_on_any_runtime(self):
        # The literal is bounded at parse time, so the outcome does not depend on
        # the interpreter's int-string conversion limit.
        for digits in (70, 5000, 100000):
            with self.subTest(digits=digits):
                raw = (
                    b'{"as_of": "2026-11-28", "ranked_candidates": ['
                    b'{"security_code": "1111", "company_name": "Huge", "total_priority": ' + b"9" * digits + b'},'
                    b'{"security_code": "6622", "company_name": "Daihen", "total_priority": 80}]}'
                )
                with tempfile.TemporaryDirectory() as tmp:
                    result = CandidateSelectorProvider(self.write_raw(tmp, raw), today=date(2026, 11, 28)).collect()
                self.assertEqual("PARTIAL", result.status)
                self.assertIn("malformed total_priority=1", result.reason)
                self.assertEqual(["1111", "6622"], [row["security_code"] for row in result.data])
                self.assertEqual([None, 1], [row["rank"] for row in result.data])
                self.assertEqual([None, 80], [row["total_priority"] for row in result.data])

    def test_ordinary_integer_priorities_are_unchanged_by_parse_bound(self):
        raw = b'{"as_of": "2026-11-28", "ranked_candidates": [{"security_code": "6622", "company_name": "D", "total_priority": 72}]}'
        with tempfile.TemporaryDirectory() as tmp:
            result = CandidateSelectorProvider(self.write_raw(tmp, raw), today=date(2026, 11, 28)).collect()
        self.assertEqual("OK", result.status)
        self.assertEqual(72, result.data[0]["total_priority"])
        self.assertIsInstance(result.data[0]["total_priority"], int)

    def test_malformed_primary_list_does_not_fall_back_to_candidates(self):
        for ranked in (None, 5, "6622", {"security_code": "6622"}):
            with self.subTest(ranked=ranked):
                result = self.collect({
                    "as_of": "2026-11-28",
                    "ranked_candidates": ranked,
                    "candidates": [{"security_code": "6622", "company_name": "ダイヘン", "total_priority": 80}],
                })
                self.assertEqual("MISSING", result.status)
                self.assertIn("ranked_candidates is present but is not a list", result.reason)
                self.assertIsNone(result.data)

    def test_legacy_candidates_field_still_used_when_primary_absent(self):
        result = self.collect({
            "as_of": "2026-11-28",
            "candidates": [{"security_code": "6622", "company_name": "ダイヘン", "total_priority": 80}],
        })
        self.assertEqual("OK", result.status)
        self.assertEqual(["6622"], [row["security_code"] for row in result.data])

    def test_malformed_rows_beyond_limit_are_still_inspected(self):
        rows = [{"security_code": f"{1000 + i}", "company_name": f"C{i}", "total_priority": 90 - i} for i in range(3)]
        rows.append({"security_code": "9999", "company_name": "Late", "total_priority": "bad"})
        result = self.collect({"as_of": "2026-11-28", "ranked_candidates": rows}, limit=2)
        self.assertEqual("PARTIAL", result.status)
        self.assertIn("malformed total_priority=1", result.reason)
        self.assertEqual(["1000", "1001"], [row["security_code"] for row in result.data])
        self.assertEqual([1, 2], [row["rank"] for row in result.data])

    def test_well_formed_rows_beyond_limit_keep_feed_ok(self):
        rows = [{"security_code": f"{1000 + i}", "company_name": f"C{i}", "total_priority": 90 - i} for i in range(5)]
        result = self.collect({"as_of": "2026-11-28", "ranked_candidates": rows}, limit=2)
        self.assertEqual("OK", result.status)
        self.assertEqual(2, len(result.data))

    def test_non_object_snapshot_and_non_list_candidates_are_not_ok(self):
        self.assertEqual("MISSING", self.collect([{"security_code": "6622"}]).status)
        result = self.collect({"as_of": "2026-11-28", "candidates": "6622"})
        self.assertEqual("MISSING", result.status)
        self.assertIn("no candidate list", result.reason)

    def test_overflowing_priority_is_nulled_and_never_ranked(self):
        result = self.collect({
            "as_of": "2026-11-28",
            "ranked_candidates": [
                {"security_code": "1111", "company_name": "Huge", "total_priority": 10 ** 400},
                {"security_code": "6622", "company_name": "ダイヘン", "total_priority": 80},
            ],
        })
        self.assertEqual("PARTIAL", result.status)
        self.assertIn("malformed total_priority=1", result.reason)
        self.assertEqual([None, 1], [row["rank"] for row in result.data])
        self.assertEqual([None, 80], [row["total_priority"] for row in result.data])

    def test_nonfinite_and_text_priorities_are_output_as_null(self):
        result = self.collect({
            "as_of": "2026-11-28",
            "ranked_candidates": [
                {"security_code": "1111", "company_name": "NaN", "total_priority": float("nan")},
                {"security_code": "2222", "company_name": "Text", "total_priority": "90"},
                {"security_code": "3333", "company_name": "Bool", "total_priority": False},
            ],
        })
        self.assertEqual("PARTIAL", result.status)
        self.assertEqual([None, None, None], [row["total_priority"] for row in result.data])
        self.assertIn("malformed total_priority=3", result.reason)
        # Output must stay strict-JSON serializable (no NaN/Infinity leaks downstream).
        json.dumps(result.data, allow_nan=False)

    def test_malformed_candidate_sources_are_not_guessed_and_feed_is_not_ok(self):
        for sources in (5, "OWNER_PICK", {"OWNER_PICK": True}, ["OWNER_PICK", 3], [""]):
            with self.subTest(sources=sources):
                result = self.collect({
                    "as_of": "2026-11-28",
                    "ranked_candidates": [
                        {"security_code": "6622", "company_name": "ダイヘン", "total_priority": 80,
                         "candidate_sources": sources},
                        {"security_code": "6232", "company_name": "ACSL", "total_priority": 70,
                         "candidate_sources": ["OWNER_PICK"], "owner_pick": True},
                    ],
                })
                self.assertEqual("PARTIAL", result.status)
                self.assertIn("malformed candidate_sources=1", result.reason)
                self.assertEqual([], result.data[0]["candidate_sources"])
                self.assertEqual(["OWNER_PICK"], result.data[1]["candidate_sources"])
                self.assertEqual([1, 2], [row["rank"] for row in result.data])
                self.assertTrue(result.data[1]["owner_pick"])

    def test_malformed_text_fields_and_rows_make_mixed_feed_partial(self):
        result = self.collect({
            "as_of": "2026-11-28",
            "ranked_candidates": [
                "6622 ダイヘン",
                {"security_code": "6622", "company_name": "ダイヘン", "total_priority": 80,
                 "research_status": {"state": "CURRENT"}, "last_researched_at": 20261127,
                 "selection_reason": ["score"]},
                {"security_code": None, "company_name": "原子力"},
            ],
        })
        self.assertEqual("PARTIAL", result.status)
        self.assertEqual(["6622"], [row["security_code"] for row in result.data])
        row = result.data[0]
        self.assertEqual("UNKNOWN", row["status"])
        self.assertIsNone(row["last_researched_at"])
        self.assertIsNone(row["selection_reason"])
        for key in ("non-object candidate row=1", "malformed research_status=1",
                    "malformed last_researched_at=1", "malformed selection_reason=1"):
            self.assertIn(key, result.reason)

    def test_stale_snapshot_reason_also_reports_malformed_fields(self):
        result = self.collect({
            "as_of": "2026-11-01",
            "ranked_candidates": [{"security_code": "6622", "company_name": "ダイヘン", "total_priority": "x"}],
        })
        self.assertEqual("STALE", result.status)
        self.assertIn("malformed total_priority=1", result.reason)

    def test_well_formed_mixed_snapshot_with_unresolved_rows_stays_ok(self):
        result = self.collect({
            "as_of": "2026-11-28",
            "ranked_candidates": [
                {"security_code": None, "company_name": "送電網"},
                {"security_code": "6622", "company_name": "ダイヘン", "total_priority": 80,
                 "research_status": "CURRENT", "candidate_sources": ["SCORE"],
                 "last_researched_at": "2026-11-27", "selection_reason": "score"},
                {"security_code": "4063", "company_name": "信越化学工業", "total_priority": None,
                 "research_status": "STALE"},
            ],
        })
        self.assertEqual("OK", result.status)
        self.assertIsNone(result.reason)
        self.assertEqual([1, None], [row["rank"] for row in result.data])

    def test_missing_snapshot_is_missing(self):
        result = CandidateSelectorProvider(Path("/missing/candidate-selector.json")).collect()
        self.assertEqual("MISSING", result.status)


if __name__ == "__main__":
    unittest.main()
