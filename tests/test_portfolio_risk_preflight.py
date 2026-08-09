import unittest

from scripts.portfolio_risk_preflight import RiskPreflightError, calculate_trade_impact


class PortfolioRiskPreflightTests(unittest.TestCase):
    def base_payload(self):
        return {
            "captured_at": "2026-08-09T16:17:00+09:00",
            "portfolio_ref": "portfolio:test:v1",
            "proposed_action": {
                "security_code": "6622",
                "action": "BUY",
                "quantity": 100,
                "price": 10000,
                "account_type": "CASH",
            },
            "before": {
                "cash_available": 2_000_000,
                "gross_exposure": 4_000_000,
                "margin_exposure": 0,
                "position_notional": 500_000,
                "portfolio_equity": 5_000_000,
            },
            "rules": {
                "single_name": {"source": "OWNER_DEFINED", "warn_limit": 0.25, "hard_limit": 0.35},
                "minimum_cash": {"source": "OWNER_DEFINED", "warn_limit": 700_000, "hard_limit": 300_000},
            },
            "data_status": "CURRENT",
        }

    def test_cash_buy_before_after(self):
        out = calculate_trade_impact(self.base_payload())
        self.assertEqual(out["after_if_executed"]["cash_available"], 1_000_000)
        self.assertEqual(out["after_if_executed"]["gross_exposure"], 5_000_000)
        self.assertEqual(out["after_if_executed"]["position_notional"], 1_500_000)
        self.assertAlmostEqual(out["after_if_executed"]["position_weight"], 0.3)
        self.assertIsNone(out["trade_action"])

    def test_owner_hard_rule_exceeded_blocks_review(self):
        p = self.base_payload()
        p["rules"]["single_name"] = {"source": "OWNER_DEFINED", "hard_limit": 0.2}
        out = calculate_trade_impact(p)
        result = out["guardrail_results"][0]
        self.assertEqual(result["result"], "BLOCK_REVIEW")

    def test_unset_rule_is_unknown_not_pass(self):
        p = self.base_payload()
        p["rules"]["single_name"] = {"source": "UNSET"}
        out = calculate_trade_impact(p)
        self.assertEqual(out["guardrail_results"][0]["result"], "UNKNOWN")

    def test_stale_portfolio_forces_unknown(self):
        p = self.base_payload()
        p["data_status"] = "STALE"
        out = calculate_trade_impact(p)
        self.assertTrue(all(x["result"] == "UNKNOWN" for x in out["guardrail_results"]))

    def test_margin_action_with_partial_data_keeps_unknowns(self):
        p = self.base_payload()
        p["proposed_action"]["account_type"] = "MARGIN"
        p["before"].pop("margin_exposure")
        p["before"].pop("cash_available")
        out = calculate_trade_impact(p)
        self.assertIsNone(out["after_if_executed"]["margin_exposure"])
        self.assertIsNone(out["after_if_executed"]["cash_available"])
        self.assertEqual(out["guardrail_results"][1]["result"], "UNKNOWN")

    def test_missing_quantity_or_price_fails_closed(self):
        for field in ("quantity", "price"):
            p = self.base_payload()
            p["proposed_action"][field] = None
            with self.assertRaises(RiskPreflightError):
                calculate_trade_impact(p)

    def test_invalid_numeric_fails_closed(self):
        for value in (-1, 0, float("nan"), float("inf"), True):
            p = self.base_payload()
            p["proposed_action"]["quantity"] = value
            with self.assertRaises(RiskPreflightError):
                calculate_trade_impact(p)

    def test_notional_conflict_fails_closed(self):
        p = self.base_payload()
        p["proposed_action"]["notional"] = 123
        with self.assertRaises(RiskPreflightError):
            calculate_trade_impact(p)

    def test_deterministic_same_input_same_output(self):
        p = self.base_payload()
        a = calculate_trade_impact(p)
        b = calculate_trade_impact(p)
        self.assertEqual(a, b)

    def test_sell_cannot_exceed_position(self):
        p = self.base_payload()
        p["proposed_action"]["action"] = "SELL"
        p["proposed_action"]["quantity"] = 1000
        with self.assertRaises(RiskPreflightError):
            calculate_trade_impact(p)


if __name__ == "__main__":
    unittest.main()
