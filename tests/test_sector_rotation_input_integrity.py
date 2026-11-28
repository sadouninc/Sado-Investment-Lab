from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from scripts.morning_dataset.providers import SectorRotationProvider


def sector(entity_id: str, *, value: float | int | None = 0, evidence=None) -> dict:
    return {
        "kind": "SECTOR",
        "id": entity_id,
        "name": entity_id,
        "as_of": "2026-11-11",
        "state": "WARMING",
        "previous_state": "COLD",
        "state_since": "2026-11-11",
        "flow_score": value,
        "scores": {
            "relative_strength": value,
            "activity": value,
            "breadth": None,
            "heat": value,
            "acceleration": value,
        },
        "data_completeness": "OK",
        "evidence": ["fixture"] if evidence is None else evidence,
    }


class SectorRotationInputIntegrityTests(unittest.TestCase):
    def write_rows(self, rows: list[dict]) -> tuple[tempfile.TemporaryDirectory, Path]:
        temp = tempfile.TemporaryDirectory()
        path = Path(temp.name) / "sector-history.jsonl"
        path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
        return temp, path

    def collect(self, rows: list[dict], *, expected_count: int):
        temp, path = self.write_rows(rows)
        self.addCleanup(temp.cleanup)
        return SectorRotationProvider(path=path, expected_count=expected_count, report_date=date(2026, 11, 12)).collect()

    def test_normal_set_preserves_true_zero_and_missing_score(self) -> None:
        rows = [sector(f"sector:{index}") for index in range(17)]
        result = self.collect(rows, expected_count=17)
        self.assertEqual("OK", result.status)
        self.assertEqual(17, len(result.data["sectors"]))
        self.assertEqual(0, result.data["sectors"][0]["flow_score"])
        self.assertIsNone(result.data["sectors"][0]["scores"]["breadth"])

    def test_duplicate_id_is_partial_even_when_unique_count_matches(self) -> None:
        rows = [sector("sector:a"), sector("sector:b"), sector("sector:b")]
        result = self.collect(rows, expected_count=2)
        self.assertEqual("PARTIAL", result.status)
        self.assertIn("input integrity", result.reason or "")
        self.assertEqual(2, len(result.data["sectors"]))

    def test_wrong_numeric_types_are_partial_and_sanitized(self) -> None:
        rows = [sector("sector:a", value="bad"), sector("sector:b", value=True)]
        result = self.collect(rows, expected_count=2)
        self.assertEqual("PARTIAL", result.status)
        for row in result.data["sectors"]:
            self.assertIsNone(row["flow_score"])
            self.assertIsNone(row["scores"]["relative_strength"])

    def test_malformed_evidence_is_partial_without_character_splitting(self) -> None:
        result = self.collect([sector("sector:a", evidence="not-a-list")], expected_count=1)
        self.assertEqual("PARTIAL", result.status)
        self.assertEqual([], result.data["sectors"][0]["evidence"])

    def test_invalid_utf8_json_and_huge_number_do_not_escape(self) -> None:
        fixtures = (
            b"\xff\xfeprivate",
            b'{"kind":"SECTOR"',
            b'{"kind":"SECTOR","value":' + b"9" * 5000 + b"}",
            b'{"kind":"SECTOR","flow_score":NaN}',
            b'{"kind":"SECTOR","flow_score":Infinity}',
        )
        for raw in fixtures:
            with self.subTest(size=len(raw)), tempfile.TemporaryDirectory() as temp_dir:
                path = Path(temp_dir) / "sector-history.jsonl"
                path.write_bytes(raw)
                result = SectorRotationProvider(path=path, report_date=date(2026, 11, 12)).collect()
                self.assertNotEqual("OK", result.status)
                self.assertNotIn("private", result.reason or "")

    def test_huge_integer_in_otherwise_valid_row_is_non_ok(self) -> None:
        huge = "9" * 5000
        raw = (
            '{"kind":"SECTOR","id":"sector:a","as_of":"2026-11-11",'
            '"name":"A","state":"WARMING","previous_state":"COLD",'
            '"state_since":"2026-11-11","flow_score":' + huge + ',"scores":{},'
            '"data_completeness":"OK","evidence":[]}'
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sector-history.jsonl"
            path.write_text(raw, encoding="utf-8")
            result = SectorRotationProvider(path=path, expected_count=1, report_date=date(2026, 11, 12)).collect()
        self.assertNotEqual("OK", result.status)
        self.assertIsNone(result.data)

    def test_nested_nonfinite_metadata_is_rejected_at_decode(self) -> None:
        raw = json.dumps(sector("sector:a"), ensure_ascii=False).replace('["fixture"]', '[{"value":1e400}]')
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sector-history.jsonl"
            path.write_text(raw, encoding="utf-8")
            result = SectorRotationProvider(path=path, expected_count=1, report_date=date(2026, 11, 12)).collect()
        self.assertNotEqual("OK", result.status)
        self.assertIsNone(result.data)

    def test_deep_evidence_and_non_string_id_are_partial(self) -> None:
        deep = "leaf"
        for _ in range(101):
            deep = [deep]
        rows = [sector("sector:valid"), sector("sector:deep", evidence=deep), sector("sector:bad-id")]
        rows[2]["id"] = ["not", "a", "string"]
        result = self.collect(rows, expected_count=2)
        self.assertEqual("PARTIAL", result.status)
        sectors = {row["id"]: row for row in result.data["sectors"]}
        self.assertEqual([], sectors["sector:deep"]["evidence"])
        json.dumps(result.data, allow_nan=False)

    def test_mixed_valid_and_missing_or_invalid_as_of_is_partial(self) -> None:
        valid = sector("sector:valid")
        missing = sector("sector:missing")
        missing.pop("as_of")
        invalid = sector("sector:invalid")
        invalid["as_of"] = "not-a-date"
        result = self.collect([valid, missing, invalid], expected_count=1)
        self.assertEqual("PARTIAL", result.status)
        self.assertEqual(["sector:valid"], [row["id"] for row in result.data["sectors"]])
        self.assertNotIn("not-a-date", result.reason or "")


if __name__ == "__main__":
    unittest.main()

