from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts.earnings_driver_forward_per_adapter import (
    EarningsDriverForwardPerError,
    earnings_driver_to_simulator_input,
    simulate_earnings_driver,
)
from scripts.earnings_driver_research_adapter import build_company_research_driver_model


ROOT = Path(__file__).resolve().parents[1]


class EarningsDriverForwardPerAdapterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.research = json.loads(
            (ROOT / "data/research/company/6622/company-research-v1.json").read_text(encoding="utf-8")
        )
        cls.mapping = json.loads(
            (ROOT / "data/research/company/6622/earnings-driver-mapping-v1.json").read_text(encoding="utf-8")
        )
        cls.bundle = build_company_research_driver_model(cls.research, cls.mapping)
        cls.price = {"value": 11900, "as_of": "2026-07-29", "source": "Monex E2E reference"}

    def test_terminal_scenario_values_remain_explicit_in_handoff(self) -> None:
        handoff = earnings_driver_to_simulator_input(self.bundle, price=self.price)
        self.assertEqual(handoff["provenance"]["driver_model_status"], "PARTIAL")
        self.assertEqual(
            handoff["scenarios"]["base"]["provenance"]["earnings_derivation_kind"],
            "SCENARIO_TERMINAL_VALUE",
        )
        self.assertEqual(handoff["scenarios"]["base"]["net_income"], 17_000_000_000.0)
        self.assertEqual(handoff["share_basis"]["diluted_shares"], 23_607_976.0)

    def test_forward_per_matches_existing_daihen_reference(self) -> None:
        result = simulate_earnings_driver(self.bundle, price=self.price, target_pers=[20.0])
        base = result["scenario_results"]["base"]
        self.assertEqual(base["eps_source"], "NET_INCOME_DIV_SHARES")
        self.assertAlmostEqual(base["eps"], 720.10, places=2)
        self.assertAlmostEqual(base["forward_per"], 16.53, places=2)
        self.assertAlmostEqual(base["implied_prices"]["per_20"], 14401.91, places=2)
        self.assertEqual(result["provenance"]["driver_model_status"], "PARTIAL")

    def test_does_not_mutate_bundle(self) -> None:
        original = copy.deepcopy(self.bundle)
        first = earnings_driver_to_simulator_input(self.bundle, price=self.price)
        second = earnings_driver_to_simulator_input(self.bundle, price=self.price)
        self.assertEqual(self.bundle, original)
        self.assertEqual(first, second)

    def test_share_denominator_mismatch_fails_closed(self) -> None:
        broken = copy.deepcopy(self.bundle)
        broken["read_model"]["scenarios"]["bull"]["eps_preview_basis"]["share_denominator"] += 1
        with self.assertRaisesRegex(EarningsDriverForwardPerError, "share denominator mismatch"):
            earnings_driver_to_simulator_input(broken, price=self.price)

    def test_wrong_net_income_unit_fails_closed(self) -> None:
        broken = copy.deepcopy(self.bundle)
        ref = broken["model"]["outputs"]["base"]["net_income_ref"]
        for node in broken["model"]["nodes"]:
            if node["node_id"] == ref:
                node["unit"] = "JPY"
        with self.assertRaisesRegex(EarningsDriverForwardPerError, "requires explicit JPY_MN"):
            earnings_driver_to_simulator_input(broken, price=self.price)

    def test_price_requires_authority_fields(self) -> None:
        with self.assertRaisesRegex(EarningsDriverForwardPerError, "price.as_of is required"):
            earnings_driver_to_simulator_input(
                self.bundle, price={"value": 11900, "source": "Monex E2E reference"}
            )
        with self.assertRaisesRegex(EarningsDriverForwardPerError, "price.source is required"):
            earnings_driver_to_simulator_input(
                self.bundle, price={"value": 11900, "as_of": "2026-07-29"}
            )


if __name__ == "__main__":
    unittest.main()
