from __future__ import annotations

import unittest

from scripts.candidate_selector import build_selector
from scripts.candidate_selector_workflow import build_research_handoff, derive_research_gap


CONFIG = {
    "schema_version": 1,
    "freshness_days": 90,
    "major_change_threshold": 80,
    "weights": {
        "investment_relevance": 0.30,
        "change_signal": 0.25,
        "research_gap": 0.20,
        "theme_relevance": 0.15,
        "valuation_interest": 0.10,
    },
}


def row(*, code: str | None, source: str, status: str = "NOT_STARTED") -> dict:
    return {
        "security_code": code,
        "company_name": "テスト企業",
        "candidate_sources": [source],
        "source_reasons": {source: ["test"]},
        "owner_pick": False,
        "owner_pick_note": None,
        "signals": {
            "investment_relevance": None,
            "change_signal": None,
            "research_gap": None,
            "theme_relevance": None,
            "valuation_interest": None,
        },
        "signal_reasons": {
            "investment_relevance": [],
            "change_signal": [],
            "research_gap": [],
            "theme_relevance": [],
            "valuation_interest": [],
        },
        "research_status": status,
        "last_researched_at": None,
        "updated_at": None,
    }


class CandidateSelectorWorkflowTests(unittest.TestCase):
    def test_fresh_research_lowers_research_gap_for_same_security_code(self) -> None:
        rows = [
            row(code="1111", source="WATCHLIST"),
            row(code="1111", source="RESEARCH_INDEX", status="CURRENT"),
        ]
        enriched = derive_research_gap(rows)
        self.assertTrue(all(item["signals"]["research_gap"] == 10.0 for item in enriched))

    def test_stale_research_raises_gap_and_no_research_is_highest(self) -> None:
        rows = [
            row(code="1111", source="RESEARCH_INDEX", status="STALE"),
            row(code="1111", source="WATCHLIST"),
            row(code="2222", source="WATCHLIST"),
        ]
        enriched = derive_research_gap(rows)
        gaps = {item["security_code"]: item["signals"]["research_gap"] for item in enriched}
        self.assertEqual(gaps["1111"], 90.0)
        self.assertEqual(gaps["2222"], 100.0)

    def test_unresolved_candidate_is_not_assigned_gap_by_name_guess(self) -> None:
        unresolved = row(code=None, source="WATCHLIST")
        enriched = derive_research_gap([unresolved])
        self.assertIsNone(enriched[0]["signals"]["research_gap"])

    def test_gap_changes_ranking_explainably(self) -> None:
        fresh = row(code="1111", source="RESEARCH_INDEX", status="CURRENT")
        stale = row(code="2222", source="RESEARCH_INDEX", status="STALE")
        result = build_selector(derive_research_gap([fresh, stale]), config=CONFIG, as_of=__import__("datetime").date(2026, 8, 9))
        self.assertEqual(result["ranked_candidates"][0]["security_code"], "2222")
        self.assertIn("research_gap", result["ranked_candidates"][0]["selection_reason"])

    def test_research_handoff_has_required_fields_and_approval_gate(self) -> None:
        candidate = {
            "security_code": "5803",
            "company_name": "フジクラ",
            "selection_reason": "theme_relevance 95",
            "candidate_sources": ["NEWS_THEME", "WATCHLIST"],
            "research_status": "STALE",
            "total_priority": 88.5,
        }
        handoff = build_research_handoff(candidate)
        self.assertEqual(handoff["security_code"], "5803")
        self.assertEqual(handoff["company_name"], "フジクラ")
        self.assertEqual(handoff["selection_reason"], "theme_relevance 95")
        self.assertEqual(handoff["candidate_sources"], ["NEWS_THEME", "WATCHLIST"])
        self.assertTrue(handoff["requires_human_approval"])
        self.assertFalse(handoff["auto_create_issue"])


if __name__ == "__main__":
    unittest.main()
