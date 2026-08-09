from __future__ import annotations

import copy
import unittest

from scripts.research_revision_adapter import (
    ResearchRevisionAdapterError,
    build_scenario_revision_candidate,
)


def research(*, code: str = "6622", fiscal_year: str = "FY2027", base_eps: float = 500.0):
    source = "fixture://ir/6622/fy2027"
    return {
        "security_code": code,
        "company_name": "ダイヘン",
        "as_of": "2026-08-09",
        "status": "CURRENT",
        "selection_context": {
            "selection_reason": "First E2E validation",
            "candidate_sources": ["candidate:6622"],
        },
        "facts": {
            "latest_financials": {
                "revenue": 100,
                "source_ref": source,
                "as_of": "2026-08-04",
            },
            "earnings_engine": {"summary": "data center / grid demand"},
        },
        "interpretation": {
            "growth_drivers": ["データセンター需要"],
            "risks": ["需要鈍化"],
        },
        "scenarios": {
            "bear": {
                "target_fiscal_year": fiscal_year,
                "eps": 400.0,
                "net_income": None,
                "share_basis": {"basis": "DILUTED", "shares": 23_000_000},
                "assumptions": ["需要鈍化"],
                "source_type": "SADO_SCENARIO",
                "source_refs": [source],
                "as_of": "2026-08-09",
            },
            "base": {
                "target_fiscal_year": fiscal_year,
                "eps": base_eps,
                "net_income": None,
                "share_basis": {"basis": "DILUTED", "shares": 23_000_000},
                "assumptions": ["会社計画近辺"],
                "source_type": "SADO_SCENARIO",
                "source_refs": [source],
                "as_of": "2026-08-09",
            },
            "bull": {
                "target_fiscal_year": fiscal_year,
                "eps": 650.0,
                "net_income": None,
                "share_basis": {"basis": "DILUTED", "shares": 23_000_000},
                "assumptions": ["需要上振れ"],
                "source_type": "SADO_SCENARIO",
                "source_refs": [source],
                "as_of": "2026-08-09",
            },
        },
        "hypothesis": {
            "what_market_may_be_underestimating": "電力インフラ需要",
            "must_happen": ["受注維持"],
            "invalidation_conditions": ["受注急減"],
            "expected_time_horizon": "12-24m",
            "current_confidence": "MEDIUM",
        },
        "source_refs": [source],
        "data_completeness": "COMPLETE",
    }


def build(before, after, **kwargs):
    params = {
        "revised_at": "2026-08-09T16:20:00+09:00",
        "trigger_type": "EARNINGS",
        "trigger_ref": "event:6622:fy2027q1",
        "reasoning": "Q1 evidenceを反映してBase EPSを更新",
        "evidence_refs": ["fact:6622:q1"],
        "materiality": "MATERIAL",
        "author_type": "OWNER",
    }
    params.update(kwargs)
    return build_scenario_revision_candidate(before, after, **params)


class ResearchRevisionAdapterTests(unittest.TestCase):
    def test_base_eps_revision_creates_append_ready_scenario_revision(self):
        before = research(base_eps=500.0)
        after = research(base_eps=560.0)
        revision = build(before, after)
        self.assertIsNotNone(revision)
        assert revision is not None
        self.assertEqual(revision["artifact_type"], "SCENARIO")
        self.assertEqual(revision["target_fiscal_year"], "FY2027")
        self.assertEqual(revision["change_summary"], "Base シナリオを更新")
        eps_change = next(row for row in revision["changed_fields"] if row["path"] == "scenarios.base.eps")
        self.assertEqual(eps_change["before"], 500.0)
        self.assertEqual(eps_change["after"], 560.0)
        self.assertEqual(eps_change["numeric_delta"], {"absolute": 60.0, "pct": 12.0})
        self.assertEqual(eps_change["source_type_before"], "SADO_SCENARIO")
        self.assertEqual(eps_change["source_type_after"], "SADO_SCENARIO")
        self.assertEqual(revision["evidence_refs"], ["fact:6622:q1"])
        self.assertEqual(revision["reasoning"], "Q1 evidenceを反映してBase EPSを更新")

    def test_identical_research_creates_no_revision(self):
        current = research()
        self.assertIsNone(build(current, copy.deepcopy(current)))

    def test_fiscal_year_rollover_is_not_encoded_as_numeric_revision(self):
        with self.assertRaises(ResearchRevisionAdapterError):
            build(research(fiscal_year="FY2027"), research(fiscal_year="FY2028", base_eps=560.0))

    def test_source_type_change_is_explicit_change_not_silent_overwrite(self):
        before = research()
        after = research()
        after["scenarios"]["base"]["source_type"] = "COMPANY_GUIDANCE"
        revision = build(before, after)
        assert revision is not None
        source_change = next(row for row in revision["changed_fields"] if row["path"] == "scenarios.base.source_type")
        self.assertEqual(source_change["before"], "SADO_SCENARIO")
        self.assertEqual(source_change["after"], "COMPANY_GUIDANCE")
        self.assertEqual(revision["scenario_source_types"]["base"], "COMPANY_GUIDANCE")

    def test_share_basis_change_is_preserved_with_numeric_revision_context(self):
        before = research(base_eps=500.0)
        after = research(base_eps=520.0)
        after["scenarios"]["base"]["share_basis"] = {"basis": "DILUTED", "shares": 24_000_000}
        revision = build(before, after)
        assert revision is not None
        eps_change = next(row for row in revision["changed_fields"] if row["path"] == "scenarios.base.eps")
        self.assertEqual(eps_change["share_basis_before"]["shares"], 23_000_000)
        self.assertEqual(eps_change["share_basis_after"]["shares"], 24_000_000)
        self.assertTrue(any(row["path"] == "scenarios.base.share_basis" for row in revision["changed_fields"]))

    def test_security_code_mismatch_fails_closed(self):
        with self.assertRaises(ResearchRevisionAdapterError):
            build(research(code="6622"), research(code="9999", base_eps=560.0))

    def test_reasoning_is_required_only_when_actual_change_exists(self):
        unchanged = research()
        self.assertIsNone(build(unchanged, copy.deepcopy(unchanged), reasoning=""))
        with self.assertRaises(ResearchRevisionAdapterError):
            build(research(base_eps=500.0), research(base_eps=560.0), reasoning="")

    def test_inputs_are_not_mutated_and_rerun_is_deterministic(self):
        before = research(base_eps=500.0)
        after = research(base_eps=560.0)
        before_copy = copy.deepcopy(before)
        after_copy = copy.deepcopy(after)
        first = build(before, after)
        second = build(before, after)
        self.assertEqual(first, second)
        self.assertEqual(before, before_copy)
        self.assertEqual(after, after_copy)


if __name__ == "__main__":
    unittest.main()
