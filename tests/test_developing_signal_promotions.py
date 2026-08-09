from __future__ import annotations

import unittest

from scripts.developing_signal_promotions import (
    DevelopingSignalPromotionError,
    promote_to_candidate,
    promote_to_company_research,
    promote_to_hypothesis_evidence,
    promote_to_theme_research,
)
from scripts.developing_signal_registry import validate_signal


BASE = {
    "signal_key": "power-grid-orders",
    "title": "電力インフラ需要の継続兆候",
    "signal_type": "COMPANY",
    "status": "STRENGTHENING",
    "direction": "STRENGTHENING",
    "first_observed_at": "2026-08-09T09:00:00+09:00",
    "last_observed_at": "2026-08-09T12:00:00+09:00",
    "created_by": "ASAHI",
    "summary": "複数の継続材料が確認された。",
    "why_it_may_matter": "受注と利益成長のResearch更新につながる可能性がある。",
    "source_refs": ["fact:power-grid:1"],
    "related_entities": [{"type": "COMPANY", "id": "6622"}],
    "related_hypothesis_refs": ["hypothesis:6622:power-grid"],
    "strengthening_conditions": ["受注増加"],
    "invalidation_conditions": ["受注減速"],
    "next_checkpoint": "2026-08-12T09:00:00+09:00",
    "expires_at": None,
    "promotion_target_candidates": ["CANDIDATE_SIGNAL", "COMPANY_RESEARCH", "HYPOTHESIS"],
    "observations": [],
}


class DevelopingSignalPromotionTests(unittest.TestCase):
    def signal(self):
        return validate_signal(dict(BASE))

    def test_candidate_handoff_is_explicit_and_does_not_force_rank_or_trade(self):
        result = promote_to_candidate(
            self.signal(),
            at="2026-08-09T13:00:00+09:00",
            candidate_ref="candidate:6622:2026-08-09",
        )
        self.assertEqual(result["signal"]["status"], "PROMOTED")
        self.assertEqual(result["signal"]["promotion_ref"], "candidate:6622:2026-08-09")
        self.assertEqual(result["handoff"]["candidate_source"], "DEVELOPING_SIGNAL")
        self.assertEqual(result["handoff"]["security_code"], "6622")
        self.assertFalse(result["handoff"]["auto_select"])
        self.assertIsNone(result["handoff"]["score_override"])
        self.assertIsNone(result["handoff"]["trade_action"])

    def test_candidate_identity_is_not_guessed_when_multiple_companies_exist(self):
        signal = dict(BASE, related_entities=[
            {"type": "COMPANY", "id": "6622"},
            {"type": "COMPANY", "id": "6504"},
        ])
        with self.assertRaisesRegex(DevelopingSignalPromotionError, "security_code is required"):
            promote_to_candidate(
                validate_signal(signal),
                at="2026-08-09T13:00:00+09:00",
                candidate_ref="candidate:x",
            )

    def test_company_research_handoff_preserves_explicit_start_gate(self):
        result = promote_to_company_research(
            self.signal(),
            at="2026-08-09T13:00:00+09:00",
            research_ref="research:6622",
            mode="REFRESH",
            company_name="ダイヘン",
        )
        handoff = result["handoff"]
        self.assertEqual(handoff["target"], "COMPANY_RESEARCH")
        self.assertEqual(handoff["research_action_candidate"], "REFRESH")
        self.assertTrue(handoff["requires_start_research_gate"])
        self.assertFalse(handoff["start_research"])
        self.assertEqual(handoff["candidate_sources"], ["DEVELOPING_SIGNAL"])

    def test_company_research_rejects_unknown_mode_and_conflicting_identity(self):
        with self.assertRaisesRegex(DevelopingSignalPromotionError, "START or REFRESH"):
            promote_to_company_research(
                self.signal(), at="2026-08-09T13:00:00+09:00", research_ref="research:6622", mode="AUTO"
            )
        with self.assertRaisesRegex(DevelopingSignalPromotionError, "conflicts"):
            promote_to_company_research(
                self.signal(),
                at="2026-08-09T13:00:00+09:00",
                research_ref="research:6504",
                mode="START",
                security_code="6504",
            )

    def test_hypothesis_handoff_is_candidate_evidence_only(self):
        result = promote_to_hypothesis_evidence(
            self.signal(),
            at="2026-08-09T13:00:00+09:00",
            hypothesis_ref="hypothesis:6622:power-grid",
            evidence_ref="evidence:signal:6622:001",
            relation="SUPPORTING",
        )
        handoff = result["handoff"]
        self.assertEqual(handoff["target"], "HYPOTHESIS_MONITOR")
        self.assertEqual(handoff["evidence_status"], "CANDIDATE")
        self.assertFalse(handoff["auto_confidence_change"])
        self.assertEqual(handoff["source_refs"], ["fact:power-grid:1"])
        self.assertEqual(result["signal"]["promotion_ref"], "evidence:signal:6622:001")

    def test_hypothesis_relation_must_be_explicit(self):
        with self.assertRaisesRegex(DevelopingSignalPromotionError, "unsupported"):
            promote_to_hypothesis_evidence(
                self.signal(),
                at="2026-08-09T13:00:00+09:00",
                hypothesis_ref="hypothesis:6622:power-grid",
                evidence_ref="evidence:1",
                relation="POSITIVE",
            )

    def test_theme_research_handoff_keeps_source_by_reference(self):
        result = promote_to_theme_research(
            self.signal(),
            at="2026-08-09T13:00:00+09:00",
            theme_ref="theme-research:power-infrastructure",
        )
        self.assertEqual(result["handoff"]["target"], "THEME_RESEARCH")
        self.assertEqual(result["handoff"]["source_refs"], ["fact:power-grid:1"])
        self.assertFalse(result["handoff"]["auto_research_complete"])
        self.assertEqual(result["signal"]["status"], "PROMOTED")

    def test_terminal_signal_cannot_be_promoted_twice(self):
        first = promote_to_candidate(
            self.signal(), at="2026-08-09T13:00:00+09:00", candidate_ref="candidate:6622:2026-08-09"
        )["signal"]
        with self.assertRaisesRegex(ValueError, "terminal signal"):
            promote_to_theme_research(
                first,
                at="2026-08-09T14:00:00+09:00",
                theme_ref="theme-research:power-infrastructure",
            )


if __name__ == "__main__":
    unittest.main()
