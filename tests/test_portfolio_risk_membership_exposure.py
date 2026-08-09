from __future__ import annotations

import copy
import unittest

from scripts.portfolio_risk_membership_exposure import (
    MembershipExposureError,
    calculate_membership_exposure,
)


class PortfolioRiskMembershipExposureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.portfolio = {
            "positions": [
                {"security_code": "6622", "position_type": "margin_long", "quantity": 100},
                {"security_code": "4063", "position_type": "margin_long", "quantity": 100},
            ]
        }
        self.prices = {"6622": 12000, "4063": 6200}
        self.catalog = {
            "authority": "CANONICAL",
            "source_ref": "membership:v1",
            "memberships": {
                "6622": {"themes": ["AI_INFRA", "POWER_GRID"], "sector": "ELECTRICAL_EQUIPMENT"},
                "4063": {"themes": ["AI_INFRA", "SEMICONDUCTOR"], "sector": "CHEMICALS"},
            },
        }
        self.action = {
            "security_code": "6622",
            "action": "ADD",
            "quantity": 100,
            "price": 12000,
            "account_type": "MARGIN",
        }

    def test_complete_membership_calculates_before_after_theme_and_sector(self) -> None:
        result = calculate_membership_exposure(
            self.portfolio,
            proposed_action=self.action,
            market_prices=self.prices,
            membership_catalog=self.catalog,
            portfolio_equity=5_000_000,
        )
        ai = result["theme_exposure"]["AI_INFRA"]
        self.assertEqual(ai["known_before_notional"], 1_820_000)
        self.assertEqual(ai["known_after_notional"], 3_020_000)
        self.assertAlmostEqual(ai["before_weight"], 0.364)
        self.assertAlmostEqual(ai["after_weight"], 0.604)
        electrical = result["sector_exposure"]["ELECTRICAL_EQUIPMENT"]
        self.assertEqual(electrical["known_before_notional"], 1_200_000)
        self.assertEqual(electrical["known_after_notional"], 2_400_000)
        self.assertEqual(result["coverage"]["status"], "CURRENT")
        self.assertIsNone(result["trade_action"])

    def test_unknown_membership_is_not_treated_as_zero(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        del catalog["memberships"]["4063"]
        result = calculate_membership_exposure(
            self.portfolio,
            proposed_action=self.action,
            market_prices=self.prices,
            membership_catalog=catalog,
            portfolio_equity=5_000_000,
        )
        self.assertEqual(result["coverage"]["status"], "UNKNOWN")
        self.assertEqual(result["coverage"]["unknown_membership_security_codes"], ["4063"])
        self.assertIsNone(result["theme_exposure"]["AI_INFRA"]["before_weight"])
        self.assertEqual(result["theme_exposure"]["AI_INFRA"]["known_before_notional"], 1_200_000)

    def test_missing_price_keeps_aggregate_unknown(self) -> None:
        result = calculate_membership_exposure(
            self.portfolio,
            proposed_action=self.action,
            market_prices={"6622": 12000},
            membership_catalog=self.catalog,
            portfolio_equity=5_000_000,
        )
        self.assertEqual(result["coverage"]["status"], "UNKNOWN")
        self.assertEqual(result["coverage"]["missing_price_security_codes"], ["4063"])
        self.assertIsNone(result["sector_exposure"]["ELECTRICAL_EQUIPMENT"]["after_weight"])

    def test_target_membership_unknown_is_explicit(self) -> None:
        action = dict(self.action)
        action["security_code"] = "9999"
        action["price"] = 1000
        result = calculate_membership_exposure(
            self.portfolio,
            proposed_action=action,
            market_prices=self.prices,
            membership_catalog=self.catalog,
            portfolio_equity=5_000_000,
        )
        self.assertEqual(result["target_membership_status"], "UNKNOWN")
        self.assertIn("9999", result["coverage"]["unknown_membership_security_codes"])
        self.assertEqual(result["coverage"]["status"], "UNKNOWN")

    def test_empty_theme_list_is_valid_canonical_no_theme_membership(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["memberships"]["6622"]["themes"] = []
        result = calculate_membership_exposure(
            self.portfolio,
            proposed_action=self.action,
            market_prices=self.prices,
            membership_catalog=catalog,
            portfolio_equity=5_000_000,
        )
        self.assertNotIn("POWER_GRID", result["theme_exposure"])
        self.assertEqual(result["coverage"]["status"], "CURRENT")

    def test_noncanonical_authority_rejected(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["authority"] = "AI_INFERRED"
        with self.assertRaises(MembershipExposureError):
            calculate_membership_exposure(
                self.portfolio,
                proposed_action=self.action,
                market_prices=self.prices,
                membership_catalog=catalog,
            )

    def test_invalid_numeric_rejected(self) -> None:
        action = dict(self.action)
        action["quantity"] = True
        with self.assertRaises(MembershipExposureError):
            calculate_membership_exposure(
                self.portfolio,
                proposed_action=action,
                market_prices=self.prices,
                membership_catalog=self.catalog,
            )

    def test_deterministic_and_non_mutating(self) -> None:
        portfolio = copy.deepcopy(self.portfolio)
        catalog = copy.deepcopy(self.catalog)
        action = copy.deepcopy(self.action)
        before_portfolio = copy.deepcopy(portfolio)
        before_catalog = copy.deepcopy(catalog)
        before_action = copy.deepcopy(action)
        first = calculate_membership_exposure(
            portfolio,
            proposed_action=action,
            market_prices=self.prices,
            membership_catalog=catalog,
            portfolio_equity=5_000_000,
        )
        second = calculate_membership_exposure(
            portfolio,
            proposed_action=action,
            market_prices=self.prices,
            membership_catalog=catalog,
            portfolio_equity=5_000_000,
        )
        self.assertEqual(first, second)
        self.assertEqual(portfolio, before_portfolio)
        self.assertEqual(catalog, before_catalog)
        self.assertEqual(action, before_action)


if __name__ == "__main__":
    unittest.main()
