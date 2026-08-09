from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts.earnings_driver_research_adapter import (
    EarningsDriverAdapterError,
    build_company_research_driver_model,
    calculate_eps_preview,
)


ROOT = Path(__file__).resolve().parents[1]
RESEARCH_PATH = ROOT / "data/research/company/6622/company-research-v1.json"
MAPPING_PATH = ROOT / "data/research/company/6622/earnings-driver-mapping-v1.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class DaihenEarningsDriverAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.research = load_json(RESEARCH_PATH)
        self.mapping = load_json(MAPPING_PATH)

    def test_daihen_research_maps_to_partial_driver_model(self) -> None:
        result = build_company_research_driver_model(self.research, self.mapping)
        self.assertEqual(result["model"]["status"], "PARTIAL")
        self.assertEqual(result["evaluated"]["status"], "PARTIAL")
        self.assertEqual(result["read_model"]["status"], "PARTIAL")

    def test_observed_guidance_and_sado_scenarios_are_separated(self) -> None:
        result = build_company_research_driver_model(self.research, self.mapping)
        nodes = {node["node_id"]: node for node in result["model"]["nodes"]}

        self.assertEqual(nodes["q1_company_revenue"]["node_type"], "OBSERVED")
        self.assertEqual(nodes["q1_company_revenue"]["value"], 55507.0)
        self.assertEqual(nodes["guidance_net_income"]["node_type"], "EXTERNAL")
        self.assertEqual(nodes["guidance_net_income"]["value"], 16500.0)

        for scenario, expected in (("bear", 13500.0), ("base", 17000.0), ("bull", 20000.0)):
            terminal = nodes[f"{scenario}_net_income_terminal"]
            self.assertEqual(terminal["node_type"], "ASSUMPTION")
            self.assertEqual(terminal["value"], expected)
            self.assertIsNone(terminal["formula"])

    def test_segment_sums_are_safe_derived_checks_not_annualization(self) -> None:
        result = build_company_research_driver_model(self.research, self.mapping)
        evaluated = {node["node_id"]: node for node in result["evaluated"]["nodes"]}
        self.assertEqual(evaluated["segment_revenue_sum"]["value"], 55465.0)
        self.assertEqual(evaluated["segment_operating_profit_sum"]["value"], 5278.0)

        node_ids = {node["node_id"] for node in result["model"]["nodes"]}
        self.assertFalse(any("annual" in node_id.lower() for node_id in node_ids))
        self.assertFalse(any("q1_x4" in node_id.lower() for node_id in node_ids))

    def test_eps_preview_uses_explicit_share_denominator(self) -> None:
        result = build_company_research_driver_model(self.research, self.mapping)
        base = result["read_model"]["scenarios"]["base"]
        self.assertAlmostEqual(base["eps_preview_jpy"], 720.0956, places=3)
        self.assertEqual(base["eps_preview_basis"]["net_income_unit"], "JPY_MN")
        self.assertEqual(base["eps_preview_basis"]["share_denominator"], 23607976.0)
        self.assertEqual(base["eps_preview_basis"]["canonical_status"], "READ_MODEL_ONLY")

    def test_read_model_is_japanese_first_and_discloses_partial_derivation(self) -> None:
        projection = build_company_research_driver_model(self.research, self.mapping)["read_model"]["projection_ja"]
        self.assertIn("Base純利益170億円", projection["headline_ja"])
        self.assertIn("会社予想165億円", projection["headline_ja"])
        self.assertTrue(projection["main_drivers_ja"])
        self.assertIn("機械的に算出しているわけではありません", projection["derivation_status_ja"])

    def test_adapter_does_not_mutate_research_or_mapping(self) -> None:
        research_before = copy.deepcopy(self.research)
        mapping_before = copy.deepcopy(self.mapping)
        first = build_company_research_driver_model(self.research, self.mapping)
        second = build_company_research_driver_model(self.research, self.mapping)
        self.assertEqual(self.research, research_before)
        self.assertEqual(self.mapping, mapping_before)
        self.assertEqual(first, second)

    def test_fiscal_year_mismatch_fails_closed(self) -> None:
        changed = copy.deepcopy(self.research)
        changed["scenarios"]["base"]["target_fiscal_year"] = "FY2028"
        with self.assertRaisesRegex(EarningsDriverAdapterError, "fiscal year mismatch"):
            build_company_research_driver_model(changed, self.mapping)

    def test_unknown_qualitative_assumption_is_not_invented_or_silently_translated(self) -> None:
        changed = copy.deepcopy(self.research)
        changed["scenarios"]["base"]["assumptions"].append("Unknown future growth rate")
        with self.assertRaisesRegex(EarningsDriverAdapterError, "missing Japanese label"):
            build_company_research_driver_model(changed, self.mapping)

    def test_non_current_research_cannot_be_promoted_to_driver_model(self) -> None:
        changed = copy.deepcopy(self.research)
        changed["status"] = "NEEDS_REVIEW"
        with self.assertRaisesRegex(EarningsDriverAdapterError, "must be CURRENT"):
            build_company_research_driver_model(changed, self.mapping)

    def test_eps_preview_rejects_bad_denominator(self) -> None:
        with self.assertRaisesRegex(EarningsDriverAdapterError, "positive"):
            calculate_eps_preview(net_income_million_jpy=17000, shares=0)
        with self.assertRaisesRegex(EarningsDriverAdapterError, "numeric"):
            calculate_eps_preview(net_income_million_jpy="17000", shares=23607976)


if __name__ == "__main__":
    unittest.main()
