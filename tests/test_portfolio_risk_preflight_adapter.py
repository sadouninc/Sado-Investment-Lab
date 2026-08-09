from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.portfolio_risk_preflight_adapter import (
    PortfolioRiskAdapterError,
    build_preflight_payload_from_canonical,
    calculate_trade_impact_from_canonical,
    canonical_data_status,
)


BASE_PORTFOLIO = {
    "schema_version": 1,
    "as_of": "2026-08-09",
    "verification_status": "VERIFIED",
    "base_snapshot": "verified-2026-08-09",
    "authority": "sbi_verified_position_snapshot",
    "positions": [
        {"security_code": "6622", "security_name": "ダイヘン", "position_type": "margin_long", "account_type": "特定", "quantity": 100},
        {"security_code": "4063", "security_name": "信越化学工業", "position_type": "cash", "account_type": "特定", "quantity": 100},
    ],
}


def proposed(**overrides):
    value = {
        "security_code": "6622",
        "action": "ADD",
        "quantity": 100,
        "price": 15000,
        "account_type": "MARGIN",
    }
    value.update(overrides)
    return value


def test_verified_portfolio_builds_current_before_from_explicit_inputs():
    payload = build_preflight_payload_from_canonical(
        BASE_PORTFOLIO,
        captured_at="2026-08-09T16:20:00+09:00",
        proposed_action=proposed(),
        market_prices={"6622": 15000, "4063": 6200},
        cash_available=1_200_000,
        portfolio_equity=5_000_000,
        max_age_days=0,
    )
    assert payload["data_status"] == "CURRENT"
    assert payload["before"]["position_notional"] == 1_500_000
    assert payload["before"]["gross_exposure"] == 2_120_000
    assert payload["before"]["margin_exposure"] == 1_500_000
    assert payload["before"]["cash_available"] == 1_200_000
    assert payload["before"]["portfolio_equity"] == 5_000_000
    assert payload["portfolio_ref"] == "verified-2026-08-09"


def test_proposed_trade_price_is_explicit_target_valuation_fallback():
    payload = build_preflight_payload_from_canonical(
        BASE_PORTFOLIO,
        captured_at="2026-08-09T16:20:00+09:00",
        proposed_action=proposed(price=14000),
        market_prices={"4063": 6200},
        max_age_days=0,
    )
    assert payload["before"]["position_notional"] == 1_400_000
    assert payload["before"]["gross_exposure"] == 2_020_000


def test_missing_non_target_prices_keep_aggregate_exposure_unknown():
    payload = build_preflight_payload_from_canonical(
        BASE_PORTFOLIO,
        captured_at="2026-08-09T16:20:00+09:00",
        proposed_action=proposed(),
        market_prices={},
        max_age_days=0,
    )
    assert payload["data_status"] == "CURRENT"
    assert payload["before"]["position_notional"] == 1_500_000
    assert payload["before"]["gross_exposure"] is None
    assert payload["before"]["margin_exposure"] is None
    assert payload["before"]["cash_available"] is None
    assert payload["before"]["portfolio_equity"] is None


def test_missing_optional_metrics_remain_unknown_in_guardrails():
    result = calculate_trade_impact_from_canonical(
        BASE_PORTFOLIO,
        captured_at="2026-08-09T16:20:00+09:00",
        proposed_action=proposed(),
        market_prices={"6622": 15000, "4063": 6200},
        max_age_days=0,
        rules={"single_name": {"source": "UNSET"}, "minimum_cash": {"source": "UNSET"}},
    )
    statuses = {item["guardrail"]: item["result"] for item in result["guardrail_results"]}
    assert statuses == {"SINGLE_NAME_CONCENTRATION": "UNKNOWN", "MINIMUM_CASH": "UNKNOWN"}
    assert result["trade_action"] is None


def test_owner_defined_concentration_rule_can_evaluate_when_equity_is_explicit():
    result = calculate_trade_impact_from_canonical(
        BASE_PORTFOLIO,
        captured_at="2026-08-09T16:20:00+09:00",
        proposed_action=proposed(),
        market_prices={"6622": 15000, "4063": 6200},
        portfolio_equity=5_000_000,
        max_age_days=0,
        rules={"single_name": {"source": "OWNER_DEFINED", "hard_limit": 0.50, "warn_limit": 0.40}},
    )
    concentration = result["guardrail_results"][0]
    assert result["after_if_executed"]["position_weight"] == pytest.approx(0.60)
    assert concentration["result"] == "BLOCK_REVIEW"
    assert concentration["rule_source"] == "OWNER_DEFINED"
    assert result["trade_action"] is None


def test_provisional_mismatch_and_stale_status_fail_closed():
    provisional = copy.deepcopy(BASE_PORTFOLIO)
    provisional["verification_status"] = "PROVISIONAL"
    assert canonical_data_status(provisional, captured_at="2026-08-09T16:20:00+09:00", max_age_days=0) == "PARTIAL"

    mismatch = copy.deepcopy(BASE_PORTFOLIO)
    mismatch["verification_status"] = "MISMATCH"
    assert canonical_data_status(mismatch, captured_at="2026-08-09T16:20:00+09:00", max_age_days=0) == "UNKNOWN"

    stale = copy.deepcopy(BASE_PORTFOLIO)
    stale["as_of"] = "2026-08-08"
    assert canonical_data_status(stale, captured_at="2026-08-09T16:20:00+09:00", max_age_days=0) == "STALE"


def test_stale_portfolio_forces_rule_results_unknown():
    stale = copy.deepcopy(BASE_PORTFOLIO)
    stale["as_of"] = "2026-08-08"
    result = calculate_trade_impact_from_canonical(
        stale,
        captured_at="2026-08-09T16:20:00+09:00",
        proposed_action=proposed(),
        market_prices={"6622": 15000, "4063": 6200},
        portfolio_equity=5_000_000,
        cash_available=2_000_000,
        max_age_days=0,
        rules={
            "single_name": {"source": "OWNER_DEFINED", "hard_limit": 0.50},
            "minimum_cash": {"source": "OWNER_DEFINED", "hard_limit": 100_000},
        },
    )
    assert result["data_status"] == "STALE"
    assert all(item["result"] == "UNKNOWN" for item in result["guardrail_results"])


def test_margin_short_target_is_rejected_in_v1_adapter():
    portfolio = copy.deepcopy(BASE_PORTFOLIO)
    portfolio["positions"] = [
        {"security_code": "6622", "security_name": "ダイヘン", "position_type": "margin_short", "account_type": "特定", "quantity": 100}
    ]
    with pytest.raises(PortfolioRiskAdapterError, match="margin_short target"):
        build_preflight_payload_from_canonical(
            portfolio,
            captured_at="2026-08-09T16:20:00+09:00",
            proposed_action=proposed(),
            max_age_days=0,
        )


def test_invalid_numeric_and_future_as_of_fail_closed():
    bad = copy.deepcopy(BASE_PORTFOLIO)
    bad["positions"][0]["quantity"] = True
    with pytest.raises(PortfolioRiskAdapterError):
        build_preflight_payload_from_canonical(
            bad,
            captured_at="2026-08-09T16:20:00+09:00",
            proposed_action=proposed(),
            max_age_days=0,
        )

    future = copy.deepcopy(BASE_PORTFOLIO)
    future["as_of"] = "2026-08-10"
    with pytest.raises(PortfolioRiskAdapterError, match="must not be after"):
        canonical_data_status(future, captured_at="2026-08-09T16:20:00+09:00", max_age_days=0)


def test_adapter_is_deterministic_and_does_not_mutate_input():
    portfolio = copy.deepcopy(BASE_PORTFOLIO)
    original = copy.deepcopy(portfolio)
    kwargs = dict(
        captured_at="2026-08-09T16:20:00+09:00",
        proposed_action=proposed(),
        market_prices={"6622": 15000, "4063": 6200},
        max_age_days=0,
    )
    first = build_preflight_payload_from_canonical(portfolio, **kwargs)
    second = build_preflight_payload_from_canonical(portfolio, **kwargs)
    assert first == second
    assert portfolio == original


def test_repository_current_portfolio_contract_is_consumable():
    path = Path("data/portfolio/current.json")
    portfolio = json.loads(path.read_text(encoding="utf-8"))
    payload = build_preflight_payload_from_canonical(
        portfolio,
        captured_at="2026-08-09T16:20:00+09:00",
        proposed_action=proposed(),
        max_age_days=1,
    )
    assert payload["portfolio_ref"] == "verified-2026-08-08"
    assert payload["before"]["verification_status"] == "VERIFIED"
    assert payload["before"]["position_notional"] == 1_500_000
    assert payload["before"]["gross_exposure"] is None
