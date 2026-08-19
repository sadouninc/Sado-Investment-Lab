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


class GovernmentEvidenceMaturityTests(unittest.TestCase):
    """Tests for optional government_evidence_maturity field (Issue #467 PR1)."""
    
    def _research(self, **overrides):
        """Minimal valid research without government_evidence_maturity."""
        payload = {
            "security_code": "6232",
            "company_name": "ACSL",
            "as_of": "2026-08-19",
            "status": "CURRENT",
            "selection_context": {
                "candidate_sources": ["OWNER_PICK"],
                "selection_reason": "Defense drone maturity comparison",
                "owner_pick": True,
                "candidate_as_of": "2026-08-19",
            },
            "facts": {
                "business_summary": {"statement": "Defense drone manufacturer"},
                "latest_financials": {
                    "revenue": 1000,
                    "source_ref": "ir:6232:fy2025",
                    "as_of": "2026-08-01",
                },
                "earnings_engine": {"drivers": ["defense procurement"]},
            },
            "interpretation": {
                "growth_drivers": [{"statement": "defense budget"}],
                "risks": [{"statement": "procurement delay"}],
                "valuation_context": {},
            },
            "scenarios": {
                "bear": {
                    "target_fiscal_year": "FY2027",
                    "eps": 10.0,
                    "assumptions": ["lower procurement"],
                },
                "base": {
                    "target_fiscal_year": "FY2027",
                    "eps": 20.0,
                    "assumptions": ["base procurement"],
                },
                "bull": {
                    "target_fiscal_year": "FY2027",
                    "eps": 30.0,
                    "assumptions": ["strong procurement"],
                },
            },
            "hypothesis": {
                "what_market_may_be_underestimating": "defense procurement scale",
                "must_happen": ["defense budget allocation"],
                "key_kpis": ["defense orders"],
                "invalidation_conditions": ["procurement cancel"],
                "expected_time_horizon": "12-24 months",
                "current_confidence": "MEDIUM",
            },
            "source_refs": ["ir:6232:fy2025"],
            "data_completeness": "COMPLETE",
        }
        payload.update(overrides)
        return payload
    
    def _gov_maturity(self, **overrides):
        """Minimal valid government_evidence_maturity field."""
        maturity = {
            "level": "L3",
            "confidence": "CONFIRMED",
            "policy_program": "SBIR Phase III",
            "direct_support_amount": 522000000,
            "supported_asset": "Defense SOTEN system",
            "supported_asset_status": "Production capability verified",
            "revenue_attribution": "NOT_CONFIRMED",
            "profit_cf_attribution": "NOT_CONFIRMED",
            "as_of": "2026-08-19",
            "sources": ["ir:6232:sbir-announcement"],
        }
        maturity.update(overrides)
        return maturity
    
    def test_legacy_research_without_field_remains_valid(self):
        """Legacy Company Research without government_evidence_maturity is valid."""
        raw = self._research()
        record = CompanyResearchRecord.from_mapping(raw)
        self.assertEqual(record.security_code, "6232")
    
    def test_unknown_maturity_accepted(self):
        """UNKNOWN maturity level is accepted as valid."""
        raw = self._research(
            government_evidence_maturity=self._gov_maturity(
                level="UNKNOWN",
                confidence="UNKNOWN",
                as_of=None,
                sources=[],
            )
        )
        record = CompanyResearchRecord.from_mapping(raw)
        self.assertEqual(record.security_code, "6232")
    
    def test_l3_with_production_evidence_accepted(self):
        """L3 with production/start evidence is accepted without revenue attribution."""
        raw = self._research(government_evidence_maturity=self._gov_maturity())
        record = CompanyResearchRecord.from_mapping(raw)
        self.assertEqual(record.security_code, "6232")
    
    def test_l4_rejected_when_revenue_attribution_not_confirmed(self):
        """L4 is rejected when revenue_attribution != CONFIRMED (mass production ≠ L4)."""
        raw = self._research(
            government_evidence_maturity=self._gov_maturity(
                level="L4",
                revenue_attribution="NOT_CONFIRMED",
            )
        )
        with self.assertRaisesRegex(
            CompanyResearchError,
            "L4 maturity requires revenue_attribution=CONFIRMED.*mass production started",
        ):
            CompanyResearchRecord.from_mapping(raw)
    
    def test_l4_accepted_when_revenue_attribution_confirmed(self):
        """L4 is accepted when revenue_attribution = CONFIRMED."""
        raw = self._research(
            government_evidence_maturity=self._gov_maturity(
                level="L4",
                revenue_attribution="CONFIRMED",
            )
        )
        record = CompanyResearchRecord.from_mapping(raw)
        self.assertEqual(record.security_code, "6232")
    
    def test_l4_rejected_when_revenue_attribution_not_applicable(self):
        """L4 is rejected when revenue_attribution = NOT_APPLICABLE."""
        raw = self._research(
            government_evidence_maturity=self._gov_maturity(
                level="L4",
                revenue_attribution="NOT_APPLICABLE",
            )
        )
        with self.assertRaisesRegex(
            CompanyResearchError,
            "L4 maturity requires revenue_attribution=CONFIRMED",
        ):
            CompanyResearchRecord.from_mapping(raw)
    
    def test_l5_rejected_when_profit_cf_attribution_not_confirmed(self):
        """L5 is rejected when profit_cf_attribution != CONFIRMED."""
        raw = self._research(
            government_evidence_maturity=self._gov_maturity(
                level="L5",
                revenue_attribution="CONFIRMED",
                profit_cf_attribution="NOT_CONFIRMED",
            )
        )
        with self.assertRaisesRegex(
            CompanyResearchError,
            "L5 maturity requires profit_cf_attribution=CONFIRMED",
        ):
            CompanyResearchRecord.from_mapping(raw)
    
    def test_l5_accepted_when_both_attributions_confirmed(self):
        """L5 is accepted when both revenue and profit/CF attributions are CONFIRMED."""
        raw = self._research(
            government_evidence_maturity=self._gov_maturity(
                level="L5",
                revenue_attribution="CONFIRMED",
                profit_cf_attribution="CONFIRMED",
            )
        )
        record = CompanyResearchRecord.from_mapping(raw)
        self.assertEqual(record.security_code, "6232")
    
    def test_support_amount_can_remain_null(self):
        """Support amount can remain null/unknown without rejection."""
        raw = self._research(
            government_evidence_maturity=self._gov_maturity(direct_support_amount=None)
        )
        record = CompanyResearchRecord.from_mapping(raw)
        self.assertEqual(record.security_code, "6232")
    
    def test_as_of_required_when_confidence_confirmed(self):
        """as_of is required when confidence is CONFIRMED."""
        raw = self._research(
            government_evidence_maturity=self._gov_maturity(confidence="CONFIRMED", as_of=None)
        )
        with self.assertRaisesRegex(
            CompanyResearchError,
            "CONFIRMED/PARTIAL confidence requires as_of",
        ):
            CompanyResearchRecord.from_mapping(raw)
    
    def test_sources_required_when_confidence_partial(self):
        """sources is required when confidence is PARTIAL."""
        raw = self._research(
            government_evidence_maturity=self._gov_maturity(confidence="PARTIAL", sources=[])
        )
        with self.assertRaisesRegex(
            CompanyResearchError,
            "CONFIRMED/PARTIAL confidence requires non-empty sources",
        ):
            CompanyResearchRecord.from_mapping(raw)
    
    def test_unknown_confidence_does_not_require_as_of_sources(self):
        """UNKNOWN confidence does not require as_of or sources."""
        raw = self._research(
            government_evidence_maturity=self._gov_maturity(
                level="UNKNOWN",
                confidence="UNKNOWN",
                as_of=None,
                sources=[],
            )
        )
        record = CompanyResearchRecord.from_mapping(raw)
        self.assertEqual(record.security_code, "6232")


if __name__ == "__main__":
    unittest.main()
