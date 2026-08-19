import unittest

from scripts.company_research import (
    CompanyResearchError,
    CompanyResearchRecord,
    build_forward_valuation_handoff,
    quality_gate_failures,
)


class CompanyResearchTests(unittest.TestCase):
    def _research(self, **overrides):
        payload = {
            "security_code": "7974",
            "company_name": "Nintendo Co., Ltd.",
            "as_of": "2026-08-09",
            "status": "CURRENT",
            "selection_context": {
                "candidate_sources": ["OWNER_PICK", "MONEY_FLOW"],
                "selection_reason": "Owner Pick Research Gap + discovery signal",
                "owner_pick": True,
                "candidate_as_of": "2026-08-09",
            },
            "facts": {
                "business_summary": {"statement": "Entertainment platform business"},
                "latest_financials": {
                    "revenue": 100,
                    "operating_profit": 20,
                    "source_ref": "ir:7974:fy2027q1",
                    "as_of": "2026-08-01",
                },
                "earnings_engine": {"drivers": ["hardware", "software", "digital mix"]},
            },
            "interpretation": {
                "growth_drivers": [{"statement": "platform cycle"}],
                "risks": [{"statement": "hardware demand miss"}],
                "valuation_context": {},
            },
            "scenarios": {
                "bear": {
                    "target_fiscal_year": "FY2028",
                    "eps": 100.0,
                    "assumptions": ["lower hardware sell-through"],
                    "source_type": "SADO_BEAR",
                },
                "base": {
                    "target_fiscal_year": "FY2028",
                    "eps": 130.0,
                    "assumptions": ["base platform adoption"],
                    "source_type": "SADO_BASE",
                },
                "bull": {
                    "target_fiscal_year": "FY2028",
                    "net_income": 500000,
                    "share_basis": {"shares": 1000, "as_of": "2026-08-01"},
                    "assumptions": ["strong software attach"],
                    "source_type": "SADO_BULL",
                },
            },
            "hypothesis": {
                "what_market_may_be_underestimating": "software monetization durability",
                "must_happen": ["installed base expands"],
                "key_kpis": ["hardware units", "software attach"],
                "invalidation_conditions": ["sell-through materially misses plan"],
                "expected_time_horizon": "12-24 months",
                "current_confidence": "MEDIUM",
            },
            "source_refs": ["ir:7974:fy2027q1"],
            "data_completeness": "COMPLETE",
        }
        payload.update(overrides)
        return payload

    def test_valid_current_record_passes_quality_gate(self):
        raw = self._research()
        self.assertEqual(quality_gate_failures(raw), [])
        record = CompanyResearchRecord.from_mapping(raw)
        self.assertEqual(record.status, "CURRENT")

    def test_missing_why_now_cannot_be_current(self):
        raw = self._research()
        raw["selection_context"] = dict(raw["selection_context"])
        raw["selection_context"]["selection_reason"] = ""
        with self.assertRaises(CompanyResearchError):
            CompanyResearchRecord.from_mapping(raw)

    def test_missing_source_as_of_cannot_be_current(self):
        raw = self._research()
        raw["facts"] = dict(raw["facts"])
        raw["facts"]["latest_financials"] = {"revenue": 100}
        with self.assertRaises(CompanyResearchError):
            CompanyResearchRecord.from_mapping(raw)

    def test_missing_risk_cannot_be_current(self):
        raw = self._research()
        raw["interpretation"] = dict(raw["interpretation"])
        raw["interpretation"]["risks"] = []
        with self.assertRaises(CompanyResearchError):
            CompanyResearchRecord.from_mapping(raw)

    def test_unavailable_scenario_reason_is_accepted(self):
        raw = self._research()
        raw["scenarios"] = dict(raw["scenarios"])
        raw["scenarios"]["bear"] = {"unavailable_reason": "share basis not yet verified"}
        CompanyResearchRecord.from_mapping(raw)

    def test_handoff_preserves_scenario_basis_without_inventing_net_income(self):
        handoff = build_forward_valuation_handoff(self._research())
        self.assertEqual(handoff["security_code"], "7974")
        self.assertEqual(handoff["scenarios"]["base"]["eps"], 130.0)
        self.assertIsNone(handoff["scenarios"]["base"]["net_income"])
        self.assertEqual(handoff["scenarios"]["bull"]["net_income"], 500000)

    def test_operating_profit_only_does_not_create_current_scenario_basis(self):
        raw = self._research()
        raw["scenarios"] = dict(raw["scenarios"])
        raw["scenarios"]["base"] = {
            "target_fiscal_year": "FY2028",
            "operating_profit": 1000,
            "assumptions": ["margin expansion"],
        }
        with self.assertRaises(CompanyResearchError):
            CompanyResearchRecord.from_mapping(raw)

    def test_legacy_company_research_without_field_remains_valid(self):
        raw = self._research()
        record = CompanyResearchRecord.from_mapping(raw)
        self.assertIsNone(record.government_evidence_maturity)

    def test_unknown_maturity_accepted(self):
        raw = self._research()
        raw["government_evidence_maturity"] = {
            "level": "UNKNOWN",
            "confidence": "UNKNOWN",
            "policy_program": None,
            "direct_support_amount": None,
            "supported_asset": None,
            "supported_asset_status": None,
            "revenue_attribution": "NOT_CONFIRMED",
            "profit_cf_attribution": "NOT_CONFIRMED",
            "as_of": None,
            "sources": [],
        }
        record = CompanyResearchRecord.from_mapping(raw)
        self.assertIsNotNone(record.government_evidence_maturity)
        self.assertEqual(record.government_evidence_maturity["level"], "UNKNOWN")

    def test_l3_production_start_evidence_accepted_without_auto_l4(self):
        raw = self._research()
        raw["government_evidence_maturity"] = {
            "level": "L3",
            "confidence": "CONFIRMED",
            "policy_program": "SBIR",
            "direct_support_amount": 522000000,
            "supported_asset": "SOTEN mass production line",
            "supported_asset_status": "MASS_PRODUCTION_STARTED",
            "revenue_attribution": "NOT_CONFIRMED",
            "profit_cf_attribution": "NOT_CONFIRMED",
            "as_of": "2026-08-15",
            "sources": ["ir:6232:sbir_announcement"],
        }
        record = CompanyResearchRecord.from_mapping(raw)
        self.assertEqual(record.government_evidence_maturity["level"], "L3")
        self.assertEqual(record.government_evidence_maturity["revenue_attribution"], "NOT_CONFIRMED")

    def test_l4_rejected_when_revenue_attribution_not_confirmed(self):
        raw = self._research()
        raw["government_evidence_maturity"] = {
            "level": "L4",
            "confidence": "CONFIRMED",
            "revenue_attribution": "NOT_CONFIRMED",
            "profit_cf_attribution": "NOT_CONFIRMED",
            "as_of": "2026-08-15",
            "sources": ["ir:6232:procurement"],
        }
        with self.assertRaises(CompanyResearchError) as ctx:
            CompanyResearchRecord.from_mapping(raw)
        self.assertIn("revenue_attribution=CONFIRMED", str(ctx.exception))

    def test_l5_rejected_when_profit_cf_attribution_not_confirmed(self):
        raw = self._research()
        raw["government_evidence_maturity"] = {
            "level": "L5",
            "confidence": "CONFIRMED",
            "revenue_attribution": "CONFIRMED",
            "profit_cf_attribution": "NOT_CONFIRMED",
            "as_of": "2026-08-15",
            "sources": ["ir:6232:financial_report"],
        }
        with self.assertRaises(CompanyResearchError) as ctx:
            CompanyResearchRecord.from_mapping(raw)
        self.assertIn("profit_cf_attribution=CONFIRMED", str(ctx.exception))

    def test_support_amount_can_remain_unknown_null_without_invention(self):
        raw = self._research()
        raw["government_evidence_maturity"] = {
            "level": "L2",
            "confidence": "CONFIRMED",
            "policy_program": "K Program",
            "direct_support_amount": None,
            "as_of": "2026-08-15",
            "sources": ["press_release:k_program"],
        }
        record = CompanyResearchRecord.from_mapping(raw)
        self.assertIsNone(record.government_evidence_maturity["direct_support_amount"])

    def test_source_and_as_of_required_when_confidence_confirmed_or_partial(self):
        raw = self._research()
        raw["government_evidence_maturity"] = {
            "level": "L1",
            "confidence": "PARTIAL",
            "policy_program": "Defense procurement",
            "as_of": None,
            "sources": [],
        }
        with self.assertRaises(CompanyResearchError):
            CompanyResearchRecord.from_mapping(raw)

    def test_acsl_6232_fixture_separates_subsidy_and_procurement(self):
        # ACSL fixture testing distinction between SBIR grant and Defense procurement order
        raw = self._research(
            security_code="6232",
            company_name="ACSL Ltd.",
            government_evidence_maturity={
                "level": "L3",
                "confidence": "CONFIRMED",
                "policy_program": "SBIR / K Program & MOD Procurement",
                "direct_support_amount": "SBIR: 5.22 oku yen grant / MOD: 5.2 oku yen order",
                "supported_asset": "SOTEN defense drone platform",
                "supported_asset_status": "MASS_PRODUCTION_DELIVERY",
                "revenue_attribution": "NOT_CONFIRMED",
                "profit_cf_attribution": "NOT_CONFIRMED",
                "as_of": "2026-08-15",
                "sources": ["ir:6232:sbir_grant_2025", "ir:6232:mod_soten_procurement_2025"],
            },
        )
        record = CompanyResearchRecord.from_mapping(raw)
        self.assertEqual(record.security_code, "6232")
        self.assertEqual(record.government_evidence_maturity["level"], "L3")


if __name__ == "__main__":
    unittest.main()
