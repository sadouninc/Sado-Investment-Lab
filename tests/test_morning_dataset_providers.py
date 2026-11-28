from __future__ import annotations

from datetime import date, datetime, timezone
import json
import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.morning_dataset.generator import build_dataset_from_providers
from scripts.morning_dataset.providers import JsonFileProvider, ProviderResult, collect_providers


class StaticProvider:
    def __init__(self, result: ProviderResult) -> None:
        self.name = result.name
        self.result = result

    def collect(self) -> ProviderResult:
        return self.result


class MorningDatasetProviderTest(unittest.TestCase):
    def test_json_file_provider_returns_ok_with_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "market.json"
            path.write_text(json.dumps({"as_of": "2026-08-07", "phase": "BULL"}), encoding="utf-8")
            result = JsonFileProvider("market", path).collect()

        self.assertEqual("OK", result.status)
        self.assertEqual("2026-08-07", result.as_of)
        self.assertEqual({"as_of": "2026-08-07", "phase": "BULL"}, result.data)

    def test_missing_json_source_is_explicit(self) -> None:
        result = JsonFileProvider("market", Path("does-not-exist.json")).collect()
        self.assertEqual("MISSING", result.status)
        self.assertIn("does not exist", result.reason or "")

    def test_json_list_and_custom_as_of_getter_remain_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "items.json"
            path.write_text('[{"date":"2026-08-07","value":0}]', encoding="utf-8")
            result = JsonFileProvider(
                "items",
                path,
                as_of_getter=lambda data: data[0]["date"],
            ).collect()
        self.assertEqual("OK", result.status)
        self.assertEqual("2026-08-07", result.as_of)
        self.assertEqual(0, result.data[0]["value"])

    def test_null_remains_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "null.json"
            path.write_text("null", encoding="utf-8")
            result = JsonFileProvider("market", path).collect()
        self.assertEqual("MISSING", result.status)

    def test_scalar_json_roots_are_partial(self) -> None:
        for raw in ('"text"', "42", "true"):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as temp_dir:
                path = Path(temp_dir) / "scalar.json"
                path.write_text(raw, encoding="utf-8")
                result = JsonFileProvider("market", path).collect()
                self.assertEqual("PARTIAL", result.status)
                self.assertIn("object or list", result.reason or "")

    def test_invalid_utf8_and_malformed_json_are_partial_without_raw_content(self) -> None:
        fixtures = (b"\xff\xfeprivate", b'{"secret":')
        for raw in fixtures:
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as temp_dir:
                path = Path(temp_dir) / "broken.json"
                path.write_bytes(raw)
                result = JsonFileProvider("market", path).collect()
                self.assertEqual("PARTIAL", result.status)
                self.assertNotIn("private", result.reason or "")
                self.assertNotIn("secret", result.reason or "")

    def test_huge_integer_and_nonfinite_values_are_partial(self) -> None:
        huge = "9" * 5000
        fixtures = (f'{{"value":{huge}}}', '{"value":NaN}', '{"nested":[Infinity]}')
        for raw in fixtures:
            with self.subTest(kind=raw[:20]), tempfile.TemporaryDirectory() as temp_dir:
                path = Path(temp_dir) / "numeric.json"
                path.write_text(raw, encoding="utf-8")
                result = JsonFileProvider("market", path).collect()
                self.assertEqual("PARTIAL", result.status)
                self.assertIsNone(result.data)

    def test_float_overflow_and_deep_json_are_partial(self) -> None:
        deep = "[" * 2000 + "0" + "]" * 2000
        for raw in ('{"value":1e400}', deep):
            with self.subTest(kind=raw[:20]), tempfile.TemporaryDirectory() as temp_dir:
                path = Path(temp_dir) / "unsafe.json"
                path.write_text(raw, encoding="utf-8")
                result = JsonFileProvider("market", path).collect()
                self.assertEqual("PARTIAL", result.status)
                self.assertIsNone(result.data)

    def test_ordinary_finite_numbers_remain_strict_json_serializable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "finite.json"
            path.write_text('{"integer":42,"decimal":1.25,"nested":[0,-3.5]}', encoding="utf-8")
            result = JsonFileProvider("market", path).collect()
        self.assertEqual("OK", result.status)
        json.dumps(result.data, allow_nan=False)

    def test_read_error_is_partial_without_exception_detail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "market.json"
            path.write_text("{}", encoding="utf-8")
            with patch.object(Path, "read_text", side_effect=OSError("private location")):
                result = JsonFileProvider("market", path).collect()
        self.assertEqual("PARTIAL", result.status)
        self.assertNotIn("private", result.reason or "")

    def test_duplicate_provider_names_are_rejected(self) -> None:
        provider = StaticProvider(ProviderResult.ok("market", {"phase": "BULL"}))
        with self.assertRaises(ValueError):
            collect_providers([provider, provider])

    def test_provider_status_is_preserved_in_dataset(self) -> None:
        providers = [
            StaticProvider(
                ProviderResult.unavailable(
                    "market",
                    status="STALE",
                    data={"phase": "BULL"},
                    as_of="2026-08-06",
                    source_reference="data/market.json",
                    reason="older than freshness threshold",
                )
            ),
            StaticProvider(
                ProviderResult.ok(
                    "investor_dna",
                    {"native_dna": {"type": "MOMENTUM"}},
                    as_of="2026-08-07",
                    source_reference="data/investor-dna.json",
                )
            ),
        ]
        payload = build_dataset_from_providers(
            providers,
            generated_at=datetime(2026, 8, 7, 8, 45, tzinfo=timezone.utc),
            as_of=date(2026, 8, 7),
        )

        status = {row["name"]: row for row in payload["source_status"]}
        self.assertEqual("STALE", status["market"]["status"])
        self.assertEqual("older than freshness threshold", status["market"]["reason"])
        self.assertEqual("data/market.json", status["market"]["source_reference"])
        self.assertEqual("OK", status["investor_dna"]["status"])
        self.assertEqual("MISSING", status["portfolio"]["status"])
        self.assertEqual("PARTIAL", payload["data_quality"]["status"])
        self.assertIn("market source is stale", payload["warnings"][0])

    def test_ok_without_data_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ProviderResult(name="market", status="OK", data=None)


if __name__ == "__main__":
    unittest.main()

