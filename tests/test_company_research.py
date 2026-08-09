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


if __name__ == "__main__":
    unittest.main()
