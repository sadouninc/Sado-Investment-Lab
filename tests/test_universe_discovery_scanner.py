from __future__ import annotations

from copy import deepcopy
import unittest

from scripts.universe_discovery_scanner import UNKNOWN, UniverseScannerError, rank_universe


FIXTURE = [
    {
        "code": "6504",
        "company": "富士電機",
        "market": "Prime",
        "sector": "Electric Appliances",
        "market_cap": 2_000_000_000_000,
        "source_timestamp": "2026-08-11T12:00:00+09:00",
        "source_confidence": 90,
        "features": {
            "exposure_proxy": 88,
            "growth_proxy": 70,
            "capacity_proxy": 82,
            "expectation_proxy": 52,
        },
    },
    {
        "code": "6622",
        "company": "ダイヘン",
        "market": "Prime",
        "sector": "Electric Appliances",
        "market_cap": 350_000_000_000,
        "source_timestamp": "2026-08-11T12:00:00+09:00",
        "source_confidence": 85,
        "features": {
            "exposure_proxy": 86,
            "growth_proxy": 74,
            "capacity_proxy": UNKNOWN,
            "expectation_proxy": 66,
        },
    },
    {
        "code": "9999",
        "company": "Unknown Industrial",
        "market": "Standard",
        "sector": "Machinery",
        "market_cap": UNKNOWN,
        "source_timestamp": "2026-08-11T12:00:00+09:00",
        "source_confidence": 70,
        "features": {
            "exposure_proxy": 92,
            "growth_proxy": UNKNOWN,
            "capacity_proxy": UNKNOWN,
            "expectation_proxy": UNKNOWN,
        },
    },
]


class UniverseDiscoveryScannerTest(unittest.TestCase):
    def test_same_input_produces_same_ranking(self):
        self.assertEqual(rank_universe(FIXTURE), rank_universe(FIXTURE))

    def test_missing_feature_is_unknown_not_zero(self):
        result = rank_universe(FIXTURE)
        unknown = next(row for row in result["review_queue"] if row["code"] == "9999")
        self.assertEqual(UNKNOWN, unknown["score_breakdown"]["growth_proxy"])
        self.assertEqual(92.0, unknown["discovery_score"])
        self.assertIn("features.growth_proxy", unknown["missing_fields"])
        self.assertLess(unknown["score_confidence"], 1.0)

    def test_sparse_unknown_company_is_not_forced_to_bottom_by_missingness(self):
        result = rank_universe(FIXTURE)
        codes = [row["code"] for row in result["review_queue"]]
        self.assertEqual("9999", codes[0])

    def test_known_examples_are_not_hard_coded(self):
        modified = deepcopy(FIXTURE)
        for row in modified:
            if row["code"] == "6622":
                row["features"] = {
                    "exposure_proxy": 10,
                    "growth_proxy": 10,
                    "capacity_proxy": 10,
                    "expectation_proxy": 10,
                }
        result = rank_universe(modified)
        self.assertNotEqual("6622", result["review_queue"][0]["code"])

    def test_output_is_discovery_only_and_non_mutating(self):
        fixture = deepcopy(FIXTURE)
        before = deepcopy(fixture)
        result = rank_universe(fixture, top_n=2)
        self.assertEqual(before, fixture)
        self.assertEqual("DISCOVERY_ONLY", result["purpose"])
        self.assertFalse(result["is_recommendation"])
        self.assertEqual([], result["canonical_mutations"])
        self.assertEqual(2, len(result["review_queue"]))
        for row in result["review_queue"]:
            self.assertFalse(row["is_recommendation"])
            self.assertIsNone(row["trade_action"])
            self.assertIsNone(row["target_price"])
            self.assertIsNone(row["recommended_quantity"])
            self.assertEqual([], row["canonical_mutations"])
            self.assertEqual("STAGE2_IR_REVIEW", row["review_stage"])

    def test_exclusion_reason_removes_candidate_from_review_queue(self):
        fixture = deepcopy(FIXTURE)
        fixture[0]["exclusion_reason"] = "not an operating company"
        result = rank_universe(fixture)
        self.assertNotIn("6504", [row["code"] for row in result["review_queue"]])
        self.assertEqual("6504", result["excluded"][0]["code"])

    def test_invalid_scores_fail_closed(self):
        fixture = deepcopy(FIXTURE)
        fixture[0]["features"]["exposure_proxy"] = 101
        with self.assertRaises(UniverseScannerError):
            rank_universe(fixture)

    def test_top_n_must_be_positive_integer(self):
        for value in (0, -1, 1.5, True):
            with self.subTest(value=value), self.assertRaises(UniverseScannerError):
                rank_universe(FIXTURE, top_n=value)


if __name__ == "__main__":
    unittest.main()
