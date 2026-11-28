from __future__ import annotations

from datetime import date, datetime, timezone
import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".github" / "pages"))

from scripts.morning_dataset.generator import build_dataset, write_dataset
from scripts.morning_dataset.validator import MorningDatasetValidationError, validate_dataset
from build_morning_dataset import build_page


class MorningDatasetTest(unittest.TestCase):
    def test_missing_sources_remain_missing_not_guessed(self) -> None:
        payload = build_dataset(
            generated_at=datetime(2026, 8, 7, 8, 40, tzinfo=timezone.utc),
            as_of=date(2026, 8, 7),
        )
        self.assertEqual("1.0", payload["schema_version"])
        self.assertEqual("MISSING", payload["data_quality"]["status"])
        self.assertEqual("0 / 8", payload["data_quality"]["completeness_label"])
        self.assertEqual(8, payload["data_quality"]["source_counts"]["MISSING"])
        self.assertIsNone(payload["capital"]["buying_power"])
        self.assertIsNone(payload["sector_rotation"])
        self.assertTrue(payload["warnings"])

    def test_supplied_facts_are_preserved_without_ai_ranking(self) -> None:
        candidates = [{"security_code": "6702", "score": 92.0}]
        dna = {"native_dna": {"type": "MOMENTUM"}, "environment_fit": {"score": 58}}
        payload = build_dataset(
            generated_at=datetime(2026, 8, 7, 8, 40, tzinfo=timezone.utc),
            as_of=date(2026, 8, 7),
            candidates=candidates,
            investor_dna=dna,
        )
        self.assertEqual(candidates, payload["candidates"])
        self.assertEqual(dna, payload["investor_dna"])
        self.assertNotIn("recommendation", payload)
        self.assertEqual("PARTIAL", payload["data_quality"]["status"])
        self.assertEqual("2 / 8", payload["data_quality"]["completeness_label"])

    def test_all_sources_produce_ok_quality(self) -> None:
        payload = build_dataset(
            market={}, portfolio={}, capital={}, candidates=[], investor_dna={}, events={}, watchlist=[], sector_rotation={}
        )
        self.assertEqual("OK", payload["data_quality"]["status"])
        self.assertEqual(1.0, payload["data_quality"]["completeness"])
        self.assertEqual("8 / 8", payload["data_quality"]["completeness_label"])
        self.assertEqual(8, payload["data_quality"]["source_counts"]["OK"])

    def test_partial_and_stale_sources_are_visible_but_not_counted_as_complete(self) -> None:
        payload = build_dataset(
            market={"indices": {"nikkei": 1}},
            portfolio={"positions": []},
            source_metadata={
                "market": {
                    "status": "STALE",
                    "as_of": "2026-08-06T15:30:00+09:00",
                    "source_reference": "market.json",
                    "reason": "previous trading day snapshot",
                },
                "portfolio": {
                    "status": "PARTIAL",
                    "as_of": "2026-08-07T08:30:00+09:00",
                    "source_reference": "Current_Status.md",
                    "reason": "buying power unavailable",
                },
            },
        )
        quality = payload["data_quality"]
        self.assertEqual("0 / 8", quality["completeness_label"])
        self.assertEqual(2, quality["usable_sources"])
        self.assertEqual(1, quality["source_counts"]["STALE"])
        self.assertEqual(1, quality["source_counts"]["PARTIAL"])
        self.assertEqual("PARTIAL", quality["status"])
        self.assertIn("previous trading day snapshot", payload["warnings"][0])

    def test_source_status_preserves_reason_and_reference(self) -> None:
        payload = build_dataset(
            investor_dna={"native_dna": {"type": "MOMENTUM"}},
            source_metadata={
                "investor_dna": {
                    "status": "OK",
                    "as_of": "2026-08-07T07:00:00+09:00",
                    "source_reference": "data/generated/investor-dna.json",
                }
            },
        )
        row = next(item for item in payload["source_status"] if item["name"] == "investor_dna")
        self.assertEqual("data/generated/investor-dna.json", row["source_reference"])
        self.assertEqual("2026-08-07T07:00:00+09:00", row["as_of"])
        self.assertIsNone(row["reason"])

    def test_diagnostics_sector_rotation_source_is_visible(self) -> None:
        payload = build_dataset(
            sector_rotation={"as_of": "2026-11-01", "sectors": [{"name": "電機・精密", "state": "WARMING"}]}
        )
        rendered = build_page(payload)
        self.assertIn("### sector_rotation — OK", rendered)
        self.assertIn("Raw JSONを見る — sector_rotation", rendered)
        self.assertIn("WARMING", rendered)

    def test_diagnostics_missing_sector_rotation_remains_missing(self) -> None:
        payload = build_dataset()
        rendered = build_page(payload)
        self.assertIn("### sector_rotation — MISSING", rendered)
        self.assertIn("- Status: MISSING", rendered)
        self.assertNotIn("### sector_rotation — OK", rendered)

    def test_diagnostics_ok_source_without_published_payload_is_explicitly_unavailable(self) -> None:
        # Actual Pages preview has source_status=OK but no top-level sector data.
        payload = build_dataset(
            sector_rotation={"as_of": "2026-10-29", "sectors": [{"name": "電機・精密"}]}
        )
        del payload["sector_rotation"]
        row = next(item for item in payload["source_status"] if item["name"] == "sector_rotation")
        self.assertEqual("OK", row["status"])

        rendered = build_page(payload)
        self.assertIn("### sector_rotation — OK", rendered)
        self.assertIn("Source status OK / Payload UNAVAILABLE", rendered)
        self.assertIn("Raw JSONは表示できません", rendered)
        self.assertIn("- Data: MISSING", rendered)
        self.assertNotIn("Raw JSONを見る — sector_rotation", rendered)

    def test_validator_rejects_bad_schema(self) -> None:
        payload = build_dataset()
        payload["schema_version"] = "999"
        with self.assertRaises(MorningDatasetValidationError):
            validate_dataset(payload)

    # --- #972: source inventory, quality consistency, strict finite JSON ---

    def mixed_payload(self) -> dict:
        return build_dataset(
            generated_at=datetime(2026, 8, 7, 8, 40, tzinfo=timezone.utc),
            as_of=date(2026, 8, 7),
            market={"indices": {"nikkei": 1}},
            portfolio={"positions": []},
            candidates=[],
            source_metadata={
                "market": {"status": "STALE", "reason": "previous day"},
                "portfolio": {"status": "PARTIAL", "reason": "buying power unavailable"},
            },
        )

    def assert_invalid(self, payload: dict, message: str) -> None:
        with self.assertRaises(MorningDatasetValidationError) as ctx:
            validate_dataset(payload)
        self.assertIn(message, str(ctx.exception))

    def test_generator_outputs_remain_valid(self) -> None:
        for payload in (
            build_dataset(),
            self.mixed_payload(),
            build_dataset(market={}, portfolio={}, capital={}, candidates=[], investor_dna={}, events={}, watchlist=[], sector_rotation={}),
        ):
            self.assertIs(payload, validate_dataset(payload))

    def test_bool_completeness_is_rejected(self) -> None:
        for value in (True, False):
            with self.subTest(value=value):
                payload = build_dataset()
                payload["data_quality"]["completeness"] = value
                self.assert_invalid(payload, "completeness must be numeric")

    def test_non_finite_or_oversized_completeness_is_rejected(self) -> None:
        for value in (float("nan"), float("inf"), 10**400):
            with self.subTest(value=str(value)[:8]):
                payload = build_dataset()
                payload["data_quality"]["completeness"] = value
                self.assert_invalid(payload, "completeness must be")

    def test_completeness_must_match_source_status(self) -> None:
        payload = self.mixed_payload()
        payload["data_quality"]["completeness"] = 1.0
        self.assert_invalid(payload, "completeness does not match")

    def test_contradictory_counts_are_rejected(self) -> None:
        cases = {
            "total_sources": 7,
            "ok_sources": 3,
            "available_sources": 5,
            "usable_sources": 8,
        }
        for field, value in cases.items():
            with self.subTest(field=field):
                payload = self.mixed_payload()
                payload["data_quality"][field] = value
                self.assert_invalid(payload, f"{field} does not match")

    def test_bool_or_negative_counts_are_rejected(self) -> None:
        for value in (True, -1, 1.0, "2"):
            with self.subTest(value=value):
                payload = self.mixed_payload()
                payload["data_quality"]["ok_sources"] = value
                self.assert_invalid(payload, "ok_sources must be a non-negative integer")

    def test_source_counts_must_match_and_be_complete(self) -> None:
        payload = self.mixed_payload()
        payload["data_quality"]["source_counts"]["STALE"] = 0
        payload["data_quality"]["source_counts"]["MISSING"] += 1
        self.assert_invalid(payload, "source_counts.STALE does not match")

        payload = self.mixed_payload()
        del payload["data_quality"]["source_counts"]["PARTIAL"]
        self.assert_invalid(payload, "source_counts must contain exactly")

        payload = self.mixed_payload()
        payload["data_quality"]["source_counts"] = []
        self.assert_invalid(payload, "source_counts must be an object")

    def test_completeness_label_and_status_must_match(self) -> None:
        payload = self.mixed_payload()
        payload["data_quality"]["completeness_label"] = "8 / 8"
        self.assert_invalid(payload, "completeness_label does not match")

        payload = self.mixed_payload()
        payload["data_quality"]["status"] = "OK"
        self.assert_invalid(payload, "data_quality.status does not match")

    def test_duplicate_source_name_is_rejected(self) -> None:
        payload = self.mixed_payload()
        payload["source_status"].append(dict(payload["source_status"][0]))
        self.assert_invalid(payload, "duplicate source status name: market")

    def test_missing_source_entry_is_rejected(self) -> None:
        payload = build_dataset()
        payload["source_status"] = [row for row in payload["source_status"] if row["name"] != "events"]
        self.assert_invalid(payload, "missing source status entries: events")

    def test_empty_source_inventory_is_rejected(self) -> None:
        payload = build_dataset()
        payload["source_status"] = []
        self.assert_invalid(payload, "missing source status entries")

    def test_unknown_or_empty_source_name_is_rejected(self) -> None:
        payload = build_dataset()
        payload["source_status"][0]["name"] = "markets"
        self.assert_invalid(payload, "unknown source status name: markets")

        for name in ("", "   ", None, 1, ["market"]):
            with self.subTest(name=name):
                payload = build_dataset()
                payload["source_status"][0]["name"] = name
                self.assert_invalid(payload, "source status needs name")

    def test_wrongly_typed_status_values_raise_validation_error_not_type_error(self) -> None:
        for value in (["OK"], {"OK": 1}, None, 1, "ok"):
            with self.subTest(value=value):
                payload = build_dataset()
                payload["source_status"][0]["status"] = value
                self.assert_invalid(payload, "invalid source status for market")

                payload = build_dataset()
                payload["data_quality"]["status"] = value
                self.assert_invalid(payload, "invalid data_quality.status")

    def test_wrongly_typed_containers_raise_validation_error(self) -> None:
        payload = build_dataset()
        payload["source_status"] = {"market": "OK"}
        self.assert_invalid(payload, "source_status must be an array")

        payload = build_dataset()
        payload["source_status"][0] = "market"
        self.assert_invalid(payload, "source_status entries must be objects")

        payload = build_dataset()
        payload["data_quality"] = []
        self.assert_invalid(payload, "data_quality must be an object")

        payload = build_dataset()
        payload["schema_version"] = ["1.0"]
        self.assert_invalid(payload, "unsupported schema_version")

    def test_non_finite_values_anywhere_are_rejected(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                payload = build_dataset(market={"indices": {"nikkei": {"change_pct": 0.5}}})
                payload["market"]["indices"]["nikkei"]["change_pct"] = value
                self.assert_invalid_strict_json(payload)

    def assert_invalid_strict_json(self, payload: dict) -> None:
        self.assert_invalid(payload, "strict finite JSON")

    def test_build_dataset_with_non_finite_input_raises_validation_error(self) -> None:
        with self.assertRaises(MorningDatasetValidationError):
            build_dataset(market={"indices": {"topix": float("nan")}})

    def test_non_serializable_and_circular_values_raise_validation_error(self) -> None:
        payload = build_dataset()
        payload["market"]["phase"] = {1, 2}
        self.assert_invalid_strict_json(payload)

        payload = build_dataset()
        loop: dict = {}
        loop["self"] = loop
        payload["market"]["phase"] = loop
        self.assert_invalid_strict_json(payload)

    def test_write_dataset_never_writes_non_standard_json(self) -> None:
        payload = build_dataset()
        payload["market"]["phase"] = float("nan")
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "morning.json"
            with self.assertRaises(MorningDatasetValidationError):
                write_dataset(payload, target)
            self.assertFalse(target.exists())

    def test_output_is_json_serializable(self) -> None:
        payload = build_dataset(market={"phase": {"name": "BULL"}})
        with tempfile.TemporaryDirectory() as temp_dir:
            path = write_dataset(payload, Path(temp_dir) / "morning.json")
            loaded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], loaded["schema_version"])


if __name__ == "__main__":
    unittest.main()
