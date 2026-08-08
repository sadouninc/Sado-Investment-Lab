from __future__ import annotations

from datetime import date
import unittest

from scripts.candidate_selector import build_selector


CONFIG = {
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


def row(code="5803", name="フジクラ", owner=False, status="NOT_STARTED", researched=None, signals=None, sources=None):
    scores = signals or {key: 50 for key in CONFIG["weights"]}
    return {
        "security_code": code,
        "company_name": name,
        "candidate_sources": sources or ["WATCHLIST"],
        "source_reasons": {"WATCHLIST": ["監視対象"]},
        "owner_pick": owner,
        "owner_pick_note": "owner" if owner else None,
        "signals": scores,
        "signal_reasons": {key: [key] for key in CONFIG["weights"]},
        "research_status": status,
        "last_researched_at": researched,
        "updated_at": "2026-08-09",
    }


class CandidateSelectorTest(unittest.TestCase):
    def test_owner_pick_survives_low_score_without_bonus(self):
        low = {key: 1 for key in CONFIG["weights"]}
        high = {key: 90 for key in CONFIG["weights"]}
        result = build_selector(
            [row("5801", "古河電工", owner=True, signals=low), row("5803", "フジクラ", signals=high)],
            config=CONFIG,
            as_of=date(2026, 8, 9),
        )
        self.assertEqual(["5801"], [item["security_code"] for item in result["owner_picks"]])
        self.assertEqual("5803", result["ranked_candidates"][0]["security_code"])

    def test_same_code_merges_but_name_only_does_not(self):
        merged = build_selector(
            [row("5803", sources=["WATCHLIST"]), row("5803", sources=["THEME"])],
            config=CONFIG,
            as_of=date(2026, 8, 9),
        )
        self.assertEqual(1, len(merged["candidates"]))
        self.assertEqual(["THEME", "WATCHLIST"], merged["candidates"][0]["candidate_sources"])
        unresolved = build_selector(
            [row(None, "フジクラ"), row("5803", "フジクラ")],
            config=CONFIG,
            as_of=date(2026, 8, 9),
        )
        self.assertEqual(2, len(unresolved["candidates"]))

    def test_missing_signal_is_not_zero(self):
        scores = {key: None for key in CONFIG["weights"]}
        scores["investment_relevance"] = 100
        result = build_selector([row(signals=scores)], config=CONFIG, as_of=date(2026, 8, 9))
        self.assertEqual(100.0, result["candidates"][0]["total_priority"])

    def test_freshness_and_major_change_mark_stale(self):
        old = build_selector(
            [row(status="CURRENT", researched="2026-04-01")], config=CONFIG, as_of=date(2026, 8, 9)
        )
        self.assertEqual("STALE", old["candidates"][0]["research_status"])
        scores = {key: 50 for key in CONFIG["weights"]}
        scores["change_signal"] = 85
        changed = build_selector(
            [row(status="CURRENT", researched="2026-08-01", signals=scores)],
            config=CONFIG,
            as_of=date(2026, 8, 9),
        )
        self.assertEqual("STALE", changed["candidates"][0]["research_status"])

    def test_ranking_is_deterministic(self):
        a = row("5803", "フジクラ")
        b = row("4063", "信越化学", signals={key: 70 for key in CONFIG["weights"]})
        first = build_selector([a, b], config=CONFIG, as_of=date(2026, 8, 9))
        second = build_selector([b, a], config=CONFIG, as_of=date(2026, 8, 9))
        self.assertEqual(
            [(x["security_code"], x["total_priority"], x["selection_reason"]) for x in first["ranked_candidates"]],
            [(x["security_code"], x["total_priority"], x["selection_reason"]) for x in second["ranked_candidates"]],
        )


if __name__ == "__main__":
    unittest.main()
