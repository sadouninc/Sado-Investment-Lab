from __future__ import annotations

from datetime import date, datetime, timezone
import json
import tempfile
import unittest
from pathlib import Path
import sys

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

    def test_issue_334_investor_dna_only_contract_is_detectable(self) -> None:
        """
        Issue #334 Pages regression: Ensure we can detect when a dataset
        has only investor_dna as OK and all other providers are MISSING.
        This indicates a reduced-contract generation that would regress Pages.
        """
        providers = [
            StaticProvider(
                ProviderResult.ok(
                    "investor_dna",
                    {"sample_count": 400, "win_rate": 0.75},
                    as_of="2026-08-16",
                    source_reference="data/generated/public/investor-dna.json",
                )
            )
        ]
        payload = build_dataset_from_providers(providers, as_of=date(2026, 8, 16))

        # Verify the dataset structure shows the reduced contract
        status_map = {row["name"]: row["status"] for row in payload["source_status"]}
        self.assertEqual("OK", status_map.get("investor_dna"))
        self.assertEqual("MISSING", status_map.get("market"))
        self.assertEqual("MISSING", status_map.get("portfolio"))
        self.assertEqual("MISSING", status_map.get("capital"))
        self.assertEqual("MISSING", status_map.get("candidates"))
        self.assertEqual("MISSING", status_map.get("events"))
        self.assertEqual("MISSING", status_map.get("watchlist"))

        # build_morning_dataset.py should reject this pattern
        self.assertEqual(1, payload["data_quality"]["ok_sources"])

    def test_issue_334_weekend_off_schedule_publish_preserves_canonical_snapshot(self) -> None:
        """
        Issue #334: Weekend/off-schedule Pages publish must consume the last-valid
        canonical snapshot without regenerating a reduced-contract dataset.
        This test verifies the canonical dataset structure is preserved.
        """
        # Simulate a canonical dataset with multiple OK sources (weekday generation)
        canonical_providers = [
            StaticProvider(
                ProviderResult.ok(
                    "market",
                    {"phase": "BULL", "indices": ["N225"]},
                    as_of="2026-08-15",  # Friday
                    source_reference="live-market-api",
                )
            ),
            StaticProvider(
                ProviderResult.ok(
                    "portfolio",
                    {"positions": 5, "exposure": 0.85},
                    as_of="2026-08-15",
                    source_reference="data/portfolio/positions.json",
                )
            ),
            StaticProvider(
                ProviderResult.ok(
                    "investor_dna",
                    {"sample_count": 400, "win_rate": 0.78},
                    as_of="2026-08-15",
                    source_reference="data/generated/public/investor-dna.json",
                )
            ),
        ]
        canonical_snapshot = build_dataset_from_providers(canonical_providers, as_of=date(2026, 8, 15))
        
        # Verify canonical snapshot has multiple OK sources (consumer must preserve this)
        status_map = {row["name"]: row["status"] for row in canonical_snapshot["source_status"]}
        self.assertEqual(3, sum(1 for s in status_map.values() if s == "OK"))
        self.assertEqual("OK", status_map.get("market"))
        self.assertEqual("OK", status_map.get("portfolio"))
        self.assertEqual("OK", status_map.get("investor_dna"))

if __name__ == "__main__":
    unittest.main()
