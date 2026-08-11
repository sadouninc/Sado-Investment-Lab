from __future__ import annotations

from copy import deepcopy
import math
import unittest

from scripts.risk_preflight_what_if import WhatIfIntentError, preview_what_if, validate_intent


PORTFOLIO = {
    "schema_version": 1,
    "as_of": "2026-08-08",
    "verification_status": "VERIFIED",
    "base_snapshot": "verified-2026-08-08",
    "authority": "test-fixture",
    "positions": [
        {
            "security_code": "6622",
            "security_name": "ダイヘン",
            "position_type": "margin_long",
            "quantity": 100,
        },
        {
            "security_code": "4063",
            "security_name": "信越化学工業",
            "position_type": "margin_long",
            "quantity": 100,
        },
    ],
}


class RiskPreflightWhatIfTest(unittest.TestCase):
    def preview(self, intent, **kwargs):
        prices = {"6622": 10000, "4063": 5000}
        prices.update(kwargs.pop("market_prices", {}))
        return preview_what_if(
            PORTFOLIO,
            intent,
            captured_at="2026-08-11T10:00:00+09:00",
            market_prices=prices,
            portfolio_equity=3_000_000,
            cash_available=1_500_000,
            max_age_days=3,
            rules=kwargs.pop("rules", {}),
            **kwargs,
        )

    def test_buy_100_delegates_to_existing_risk_preflight(self):
        result = self.preview(
            {"security_code": "6622", "action": "BUY", "quantity": 100, "price": 10000, "account_type": "MARGIN"}
        )
        self.assertEqual("CALCULATED", result["state"])
        self.assertTrue(result["ephemeral"])
        self.assertFalse(result["is_order"])
        self.assertEqual([], result["canonical_mutations"])
        impact = result["risk_preflight"]
        self.assertEqual(2_000_000, impact["after_if_executed"]["position_notional"])
        self.assertAlmostEqual(2 / 3, impact["after_if_executed"]["position_weight"])
        self.assertIsNone(impact["trade_action"])

    def test_quantity_must_be_positive_integer(self):
        for quantity in (0, -1, 1.5, True, "100"):
            with self.subTest(quantity=quantity), self.assertRaises(WhatIfIntentError):
                validate_intent({"security_code": "6622", "action": "BUY", "quantity": quantity, "price": 10000})

    def test_price_rejects_zero_negative_nan_and_inf(self):
        for price in (0, -1, math.nan, math.inf, -math.inf, True):
            with self.subTest(price=price), self.assertRaises(WhatIfIntentError):
                validate_intent({"security_code": "6622", "action": "BUY", "quantity": 100, "price": price})

    def test_stale_or_unavailable_market_price_fails_closed(self):
        for status, expected in (("STALE", "SOURCE_STALE"), ("UNAVAILABLE", "SOURCE_UNAVAILABLE"), ("UNKNOWN", "SOURCE_UNAVAILABLE")):
            with self.subTest(status=status):
                with self.assertRaises(WhatIfIntentError) as caught:
                    validate_intent({
                        "security_code": "6622",
                        "action": "BUY",
                        "quantity": 100,
                        "price": 10000,
                        "price_status": status,
                    })
                self.assertEqual(expected, caught.exception.state)

    def test_manual_price_is_explicit_assumption_not_guessed_quote(self):
        result = validate_intent({"security_code": "6622", "action": "BUY", "quantity": 100, "price": 9999})
        self.assertEqual("USER_INPUT", result["price_source"])
        self.assertIsNone(result["price_status"])

    def test_sell_over_verified_holding_is_not_judgable(self):
        with self.assertRaises(WhatIfIntentError) as caught:
            self.preview({"security_code": "6622", "action": "SELL", "quantity": 200, "price": 10000, "account_type": "MARGIN"})
        self.assertEqual("NOT_JUDGABLE", caught.exception.state)

    def test_sell_unknown_account_does_not_infer_cash_or_margin(self):
        with self.assertRaises(WhatIfIntentError) as caught:
            self.preview({"security_code": "6622", "action": "SELL", "quantity": 100, "price": 10000, "account_type": "UNKNOWN"})
        self.assertEqual("NOT_JUDGABLE", caught.exception.state)

    def test_unset_rules_remain_unknown(self):
        result = self.preview({"security_code": "6622", "action": "BUY", "quantity": 100, "price": 10000, "account_type": "MARGIN"})
        self.assertTrue(result["risk_preflight"]["guardrail_results"])
        self.assertTrue(all(row["result"] == "UNKNOWN" for row in result["risk_preflight"]["guardrail_results"]))

    def test_preview_does_not_mutate_portfolio_or_intent(self):
        portfolio = deepcopy(PORTFOLIO)
        intent = {"security_code": "6622", "action": "BUY", "quantity": 100, "price": 10000, "account_type": "MARGIN"}
        portfolio_before = deepcopy(portfolio)
        intent_before = deepcopy(intent)
        preview_what_if(
            portfolio,
            intent,
            captured_at="2026-08-11T10:00:00+09:00",
            market_prices={"6622": 10000, "4063": 5000},
            portfolio_equity=3_000_000,
            max_age_days=3,
        )
        self.assertEqual(portfolio_before, portfolio)
        self.assertEqual(intent_before, intent)

    def test_same_inputs_are_deterministic(self):
        intent = {"security_code": "6622", "action": "BUY", "quantity": 100, "price": 10000, "account_type": "MARGIN"}
        self.assertEqual(self.preview(intent), self.preview(intent))


if __name__ == "__main__":
    unittest.main()
