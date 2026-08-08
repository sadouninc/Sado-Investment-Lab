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


class CandidateSelectorTest(unittest.TestCase):
    pass


if __name__ == "__main__":
    unittest.main()
