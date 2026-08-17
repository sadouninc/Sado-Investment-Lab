from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts.daihen_operational_read_model import (
    DaihenOperationalReadModelError,
    build_daihen_operational_read_model,
)
from scripts.fair_per_evidence import (
    FACTOR_OPTIONALITY,
    REQUIRED_FACTORS,
    STAGE_OPERATING_EVIDENCE,
    CanonicalPriceGate,
    EPSScenario,
    FactorEvidence,
    FairPERRange,
    HistoricalValuationAnchor,
    build_fair_per_evidence_record,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data/fixtures/acceptance/6622-daihen-operational-v1.json"
GENERATED_AT = "2026-08-09T19:20:00+09:00"


def _fair_per_record(
    *,
    symbol: str = "6622",
    identity_status: str = "VERIFIED",
    freshness_status: str = "FRESH",
    provider_status: str = "OK",
    not_market_truth: bool = False,
):
    factors = [
        FactorEvidence(
            factor=factor,
            summary=f"{factor} evidence",
            as_of="2026-08-17",
            confidence="MEDIUM",
            source_ref=f"fair-per:6622:{factor}",
            stage=STAGE_OPERATING_EVIDENCE if factor == FACTOR_OPTIONALITY else None,
        )
        for factor in REQUIRED_FACTORS
    ]
    return build_fair_per_evidence_record(
        security_id=f"TSE:{symbol}",
        symbol=symbol,
        exchange="TSE",
        factors=factors,
        historical_valuation_anchor=HistoricalValuationAnchor(
            anchor_low=12.0,
            anchor_high=22.0,
            accounting_basis="IFRS",
            included_periods=("FY2024", "FY2025"),
            excluded_periods=(),
        ),
        eps_scenario=EPSScenario(
            bear_eps=500.0,
            base_eps=600.0,
            bull_eps=700.0,
            scenario_as_of="2026-08-17",
        ),
        fair_per_range=FairPERRange(
            fair_per_low=15.0,
            fair_per_high=18.0,
            confidence="MEDIUM",
        ),
        canonical_price=CanonicalPriceGate(
            identity_status=identity_status,
            freshness_status=freshness_status,
            provider_status=provider_status,
            not_market_truth=not_market_truth,
            price=12000.0,
            price_as_of="2026-08-17",
        ),
        strengthening=("受注の利益転換",),
        invalidation=("受注失速",),
        next_checkpoint=("FY2027-Q2",),
    )


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

    def test_missing_fair_per_artifact_only_marks_subprojection_unavailable(self):
        result = build_daihen_operational_read_model(self.fixture, generated_at=GENERATED_AT)
        fair_per = result["valuation"]["fair_per_evidence"]
        self.assertEqual(fair_per["status"], "UNAVAILABLE")
        self.assertEqual(fair_per["current_valuation_status"], "UNKNOWN")
        self.assertIsNone(fair_per["implied_expectation"]["current_per"])
        self.assertEqual(result["valuation"]["base"]["eps"], 720.1)
        self.assertEqual(result["overall_status"], "PARTIAL")

    def test_fresh_fair_per_evidence_is_projected_losslessly(self):
        record = _fair_per_record()
        result = build_daihen_operational_read_model(
            self.fixture,
            generated_at=GENERATED_AT,
            fair_per_evidence=record,
        )
        fair_per = result["valuation"]["fair_per_evidence"]
        self.assertEqual(fair_per["status"], "AVAILABLE")
        self.assertEqual(fair_per["fair_per_range"]["fair_per_low"], 15.0)
        self.assertEqual(fair_per["fair_per_range"]["fair_per_high"], 18.0)
        self.assertEqual(fair_per["fair_per_range"]["confidence"], "MEDIUM")
        self.assertTrue(fair_per["canonical_price"]["usable_for_current_valuation"])
        self.assertEqual(fair_per["current_valuation_status"], "AVAILABLE")
        self.assertEqual(fair_per["implied_expectation"]["current_per"], 20.0)
        self.assertEqual(fair_per["implied_expectation"]["expectation_gap_to_low"], 5.0)
        self.assertEqual(fair_per["implied_expectation"]["expectation_gap_to_high"], 2.0)
        self.assertIsNone(fair_per["implied_expectation"]["implied_scenario"])
        self.assertEqual(
            fair_per["factors"][FACTOR_OPTIONALITY]["stage"],
            STAGE_OPERATING_EVIDENCE,
        )
        self.assertIn("fair-per:6622:optionality", result["source_refs"])
        self.assertEqual(fair_per["strengthening"], ["受注の利益転換"])
        self.assertEqual(fair_per["invalidation"], ["受注失速"])
        self.assertEqual(fair_per["next_checkpoint"], ["FY2027-Q2"])
        self.assertNotIn("entry_zone", fair_per)
        self.assertNotIn("decision_action", fair_per)

    def test_unusable_fair_per_price_gate_keeps_current_valuation_unknown(self):
        record = _fair_per_record(freshness_status="STALE")
        result = build_daihen_operational_read_model(
            self.fixture,
            generated_at=GENERATED_AT,
            fair_per_evidence=record,
        )
        fair_per = result["valuation"]["fair_per_evidence"]
        self.assertFalse(fair_per["canonical_price"]["usable_for_current_valuation"])
        self.assertEqual(fair_per["canonical_price"]["price"], 12000.0)
        self.assertEqual(fair_per["canonical_price"]["freshness_status"], "STALE")
        self.assertEqual(fair_per["current_valuation_status"], "UNKNOWN")
        self.assertIsNone(fair_per["implied_expectation"]["current_per"])
        self.assertIsNone(fair_per["implied_expectation"]["expectation_gap_to_low"])
        self.assertIsNone(fair_per["implied_expectation"]["expectation_gap_to_high"])
        self.assertIsNone(fair_per["implied_expectation"]["implied_scenario"])

    def test_unknown_and_failed_price_gates_also_fail_closed(self):
        cases = (
            {"identity_status": "VERIFIED", "freshness_status": "UNKNOWN", "provider_status": "OK"},
            {"identity_status": "FAILED", "freshness_status": "FRESH", "provider_status": "OK"},
            {"identity_status": "VERIFIED", "freshness_status": "FRESH", "provider_status": "FAILED"},
        )
        for case in cases:
            with self.subTest(case=case):
                record = _fair_per_record(**case)
                result = build_daihen_operational_read_model(
                    self.fixture,
                    generated_at=GENERATED_AT,
                    fair_per_evidence=record,
                )
                fair_per = result["valuation"]["fair_per_evidence"]
                self.assertFalse(fair_per["canonical_price"]["usable_for_current_valuation"])
                self.assertEqual(fair_per["current_valuation_status"], "UNKNOWN")
                self.assertIsNone(fair_per["implied_expectation"]["current_per"])
                self.assertIsNone(fair_per["implied_expectation"]["expectation_gap_to_low"])
                self.assertIsNone(fair_per["implied_expectation"]["expectation_gap_to_high"])
                self.assertIsNone(fair_per["implied_expectation"]["implied_scenario"])

    def test_fair_per_projection_rejects_wrong_security(self):
        record = _fair_per_record(symbol="6758")
        with self.assertRaises(DaihenOperationalReadModelError):
            build_daihen_operational_read_model(
                self.fixture,
                generated_at=GENERATED_AT,
                fair_per_evidence=record,
            )


if __name__ == "__main__":
    unittest.main()
