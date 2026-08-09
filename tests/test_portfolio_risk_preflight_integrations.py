from copy import deepcopy

import pytest

from scripts.portfolio_risk_preflight_integrations import (
    RiskPreflightIntegrationError,
    decision_journal_ref,
    feasible_capital_context,
    japanese_confirmation_model,
    review_context,
)


def snapshot(*, data_status="CURRENT", results=None):
    return {
        "snapshot_id": "risk-preflight:6622:abc123",
        "captured_at": "2026-08-09T16:40:00+09:00",
        "portfolio_ref": "portfolio:2026-08-09",
        "proposed_action": {
            "security_code": "6622",
            "action": "BUY",
            "quantity": 100.0,
            "price": 10000.0,
            "notional": 1000000.0,
            "account_type": "CASH",
        },
        "before": {
            "position_notional": 800000.0,
            "cash_available": 2000000.0,
            "gross_exposure": 4000000.0,
            "margin_exposure": 1000000.0,
        },
        "after_if_executed": {
            "position_notional": 1800000.0,
            "position_weight": 0.18,
            "cash_available": 1000000.0,
            "gross_exposure": 5000000.0,
            "margin_exposure": 1000000.0,
        },
        "guardrail_results": results
        if results is not None
        else [
            {"guardrail": "SINGLE_NAME_CONCENTRATION", "result": "PASS", "rule_source": "OWNER_DEFINED"},
            {"guardrail": "MINIMUM_CASH", "result": "UNKNOWN", "rule_source": "UNSET", "reason": "上限ルール未設定"},
        ],
        "data_status": data_status,
        "trade_action": None,
    }


def test_decision_journal_ref_is_reference_only():
    result = decision_journal_ref(snapshot())
    assert result == {
        "type": "RISK_PREFLIGHT_SNAPSHOT",
        "ref": "risk-preflight:6622:abc123",
        "captured_at": "2026-08-09T16:40:00+09:00",
        "security_code": "6622",
        "data_status": "CURRENT",
    }
    assert "decision" not in result


def test_review_context_preserves_unknown_and_does_not_create_trade_action():
    result = review_context(snapshot())
    assert result["reasons"] == [
        {
            "guardrail": "MINIMUM_CASH",
            "result": "UNKNOWN",
            "reason": "上限ルール未設定",
        }
    ]
    assert result["requires_owner_review"] is False
    assert result["trade_action"] is None


def test_block_review_requires_owner_review_but_not_auto_sell():
    result = review_context(
        snapshot(
            results=[
                {
                    "guardrail": "SINGLE_NAME_CONCENTRATION",
                    "result": "BLOCK_REVIEW",
                    "reason": "Owner hard rule超過",
                }
            ]
        )
    )
    assert result["requires_owner_review"] is True
    assert result["trade_action"] is None


def test_feasible_capital_context_never_claims_verified_buying_power():
    result = feasible_capital_context(snapshot())
    assert result["feasibility"] == "UNKNOWN"
    assert result["brokerage_buying_power_verified"] is False
    assert result["unknown_constraints"] == ["MINIMUM_CASH"]
    assert result["after_if_executed"]["cash_available"] == 1000000.0


def test_defined_rule_block_is_exposed_as_context_only():
    result = feasible_capital_context(
        snapshot(results=[{"guardrail": "MINIMUM_CASH", "result": "BLOCK_REVIEW"}])
    )
    assert result["feasibility"] == "BLOCKED_BY_DEFINED_RULE"
    assert result["defined_rule_blocks"] == ["MINIMUM_CASH"]
    assert result["trade_action"] is None


def test_stale_portfolio_adds_unknown_review_and_capital_constraint():
    review = review_context(snapshot(data_status="STALE", results=[]))
    capital = feasible_capital_context(snapshot(data_status="STALE", results=[]))
    assert review["reasons"] == [
        {
            "guardrail": "PORTFOLIO_DATA_STATUS",
            "result": "UNKNOWN",
            "reason": "portfolio data_status=STALE",
        }
    ]
    assert capital["unknown_constraints"] == ["PORTFOLIO_DATA_STATUS"]
    assert capital["feasibility"] == "UNKNOWN"


def test_japanese_confirmation_model_keeps_membership_explicit():
    exposure = {
        "theme_exposure": [{"name": "AI・半導体", "before_weight": 0.38, "after_weight": 0.46}],
        "sector_exposure": [{"name": "電気機器", "before_weight": 0.25, "after_weight": 0.31}],
    }
    result = japanese_confirmation_model(snapshot(), membership_exposure=exposure)
    assert result["title"] == "売買前のポートフォリオ確認"
    assert result["theme_exposure"] == exposure["theme_exposure"]
    assert result["sector_exposure"] == exposure["sector_exposure"]
    assert result["trade_action"] is None
    assert "売買指示ではありません" in result["disclaimer"]


def test_model_is_deterministic_and_does_not_mutate_inputs():
    source = snapshot()
    exposure = {"theme_exposure": [], "sector_exposure": []}
    source_before = deepcopy(source)
    exposure_before = deepcopy(exposure)
    first = japanese_confirmation_model(source, membership_exposure=exposure)
    second = japanese_confirmation_model(source, membership_exposure=exposure)
    assert first == second
    assert source == source_before
    assert exposure == exposure_before


@pytest.mark.parametrize(
    "patch",
    [
        {"snapshot_id": ""},
        {"data_status": "VERIFIED"},
        {"guardrail_results": [{"guardrail": "X", "result": "SAFE"}]},
    ],
)
def test_invalid_integration_input_fails_closed(patch):
    source = snapshot()
    source.update(patch)
    with pytest.raises(RiskPreflightIntegrationError):
        decision_journal_ref(source)
