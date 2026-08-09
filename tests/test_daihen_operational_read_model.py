from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts.daihen_operational_read_model import (
    DaihenOperationalReadModelError,
    build_daihen_operational_read_model,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data/fixtures/acceptance/6622-daihen-operational-v1.json"
GENERATED_AT = "2026-08-09T19:20:00+09:00"


class DaihenOperationalReadModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_realistic_partial_is_valid_and_keeps_canonical_refs(self):
        result = build_daihen_operational_read_model(self.fixture, generated_at=GENERATED_AT)
        self.assertEqual(result["security_code"], "6622")
        self.assertEqual(result["overall_status"], "PARTIAL")
        self.assertEqual(result["valuation"]["base"]["eps"], 720.1)
        self.assertIn("company-research:6622:2026-08-09", result["source_refs"])
        self.assertIn("expectations", result["missing_components"])
        self.assertIn("portfolio_preflight", result["missing_components"])

    def test_stale_price_is_not_silently_current(self):
        payload = copy.deepcopy(self.fixture)
        payload["valuation"]["status"] = "OK"
        result = build_daihen_operational_read_model(payload, generated_at=GENERATED_AT)
        self.assertEqual(result["valuation"]["status"], "PARTIAL")
        self.assertEqual(result["freshness"]["overall"], "STALE")
        self.assertIn("valuation", result["freshness"]["stale_components"])
        self.assertIn("PRICE_STALE_FOR_E2E", result["valuation"]["warnings"])

    def test_consensus_unavailable_does_not_create_zero_gap(self):
        result = build_daihen_operational_read_model(self.fixture, generated_at=GENERATED_AT)
        self.assertEqual(result["expectations"]["status"], "UNAVAILABLE")
        self.assertIsNone(result["expectations"]["external_consensus_ref"])
        self.assertNotIn("gap", result["expectations"])
        self.assertNotEqual(result["overall_status"], "UNAVAILABLE")

    def test_historical_decision_snapshot_is_copied_not_rewritten(self):
        payload = copy.deepcopy(self.fixture)
        original = copy.deepcopy(payload)
        result = build_daihen_operational_read_model(payload, generated_at=GENERATED_AT)
        historical = result["decision_history"]["historical_snapshot_ref"]
        payload["decision_history"]["historical_snapshot_ref"] = "decision-snapshot:6622:mutated-current"
        self.assertEqual(historical, "decision-snapshot:6622:latest:immutable")
        self.assertEqual(original, self.fixture)

    def test_basis_conflict_forces_needs_review_without_calculation(self):
        payload = copy.deepcopy(self.fixture)
        payload["valuation"]["status"] = "OK"
        payload["valuation"]["freshness"] = "CURRENT"
        payload["valuation"]["basis_conflict"] = True
        payload["valuation"]["reason_codes"] = ["FISCAL_YEAR_BASIS_CONFLICT"]
        result = build_daihen_operational_read_model(payload, generated_at=GENERATED_AT)
        self.assertEqual(result["valuation"]["status"], "NEEDS_REVIEW")
        self.assertEqual(result["overall_status"], "NEEDS_REVIEW")
        self.assertNotIn("comparison", result["valuation"])

    def test_no_mutation_and_deterministic_for_same_inputs(self):
        payload = copy.deepcopy(self.fixture)
        before = copy.deepcopy(payload)
        first = build_daihen_operational_read_model(payload, generated_at=GENERATED_AT)
        second = build_daihen_operational_read_model(payload, generated_at=GENERATED_AT)
        self.assertEqual(first, second)
        self.assertEqual(payload, before)

    def test_read_model_rejects_trade_recommendation_fields(self):
        payload = copy.deepcopy(self.fixture)
        payload["review_context"]["recommendation"] = "BUY"
        with self.assertRaises(DaihenOperationalReadModelError):
            build_daihen_operational_read_model(payload, generated_at=GENERATED_AT)

    def test_wrong_security_code_fails_closed(self):
        payload = copy.deepcopy(self.fixture)
        payload["security_code"] = "4063"
        with self.assertRaises(DaihenOperationalReadModelError):
            build_daihen_operational_read_model(payload, generated_at=GENERATED_AT)

    def test_generated_at_requires_timezone(self):
        with self.assertRaises(DaihenOperationalReadModelError):
            build_daihen_operational_read_model(self.fixture, generated_at="2026-08-09T19:20:00")


if __name__ == "__main__":
    unittest.main()
