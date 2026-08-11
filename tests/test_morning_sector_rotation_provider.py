from __future__ import annotations

from datetime import date, datetime, timezone
import json
import tempfile
import unittest
from pathlib import Path

from scripts.morning_dataset.generator import build_dataset_from_providers
from scripts.morning_dataset.providers import SectorRotationProvider


def sector(entity_id: str, *, as_of: str, state: str, previous_state: str, breadth=None, completeness: str = "OK") -> dict:
    return {
        "kind": "SECTOR",
        "id": entity_id,
        "name": entity_id.upper(),
        "as_of": as_of,
        "state": state,
        "previous_state": previous_state,
        "state_since": as_of,
        "flow_score": 61.5,
        "scores": {
            "relative_strength": 12.0,
            "activity": 55.0,
            "breadth": breadth,
            "heat": 40.0,
            "acceleration": 70.0,
        },
        "data_completeness": completeness,
        "evidence": ["fixture"],
    }


class MorningSectorRotationProviderTests(unittest.TestCase):
    def write_history(self, rows: list[dict]) -> Path:
        self.temp = tempfile.TemporaryDirectory()
        path = Path(self.temp.name) / "sector-history.jsonl"
        path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
        return path

    def tearDown(self) -> None:
        temp = getattr(self, "temp", None)
        if temp is not None:
            temp.cleanup()

    def test_latest_sector_set_only_preserves_transition_and_missing_breadth(self) -> None:
        path = self.write_history([
            sector("sector:a", as_of="2026-08-08", state="COLD", previous_state="COLD", breadth=10.0),
            {"kind": "THEME", "id": "theme:x", "as_of": "2026-08-11", "state": "HOT"},
            sector("sector:a", as_of="2026-08-11", state="WARMING", previous_state="COLD", breadth=None),
            sector("sector:b", as_of="2026-08-11", state="INFLOW", previous_state="WARMING", breadth=65.0),
        ])
        result = SectorRotationProvider(path=path, expected_count=2).collect()

        self.assertEqual("OK", result.status)
        self.assertEqual("2026-08-11", result.as_of)
        self.assertEqual(2, len(result.data["sectors"]))
        rows = {row["id"]: row for row in result.data["sectors"]}
        self.assertEqual("COLD", rows["sector:a"]["previous_state"])
        self.assertEqual("WARMING", rows["sector:a"]["state"])
        self.assertIsNone(rows["sector:a"]["scores"]["breadth"])
        self.assertNotIn("theme:x", rows)

    def test_incomplete_latest_set_is_partial_not_fabricated(self) -> None:
        path = self.write_history([
            sector("sector:a", as_of="2026-08-11", state="WARMING", previous_state="COLD"),
        ])
        result = SectorRotationProvider(path=path, expected_count=2).collect()

        self.assertEqual("PARTIAL", result.status)
        self.assertEqual("2026-08-11", result.as_of)
        self.assertEqual(1, len(result.data["sectors"]))
        self.assertIn("1 / 2", result.reason or "")

    def test_non_ok_canonical_row_remains_partial(self) -> None:
        path = self.write_history([
            sector("sector:a", as_of="2026-08-11", state="WARMING", previous_state="COLD"),
            sector("sector:b", as_of="2026-08-11", state="COLD", previous_state="COLD", completeness="PARTIAL"),
        ])
        result = SectorRotationProvider(path=path, expected_count=2).collect()
        self.assertEqual("PARTIAL", result.status)
        self.assertIn("non-OK", result.reason or "")

    def test_provider_is_visible_as_independent_morning_source(self) -> None:
        path = self.write_history([
            sector("sector:a", as_of="2026-08-11", state="WARMING", previous_state="COLD"),
            sector("sector:b", as_of="2026-08-11", state="INFLOW", previous_state="WARMING"),
        ])
        payload = build_dataset_from_providers(
            [SectorRotationProvider(path=path, expected_count=2)],
            generated_at=datetime(2026, 8, 11, 7, 0, tzinfo=timezone.utc),
            as_of=date(2026, 8, 11),
        )

        self.assertEqual("2026-08-11", payload["sector_rotation"]["as_of"])
        status = {row["name"]: row for row in payload["source_status"]}
        self.assertEqual("OK", status["sector_rotation"]["status"])
        self.assertEqual("MISSING", status["market"]["status"])
        self.assertEqual("PARTIAL", payload["data_quality"]["status"])


if __name__ == "__main__":
    unittest.main()
