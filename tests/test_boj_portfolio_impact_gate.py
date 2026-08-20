from __future__ import annotations

import json
from pathlib import Path
from scripts.boj_portfolio_impact_gate import (
    determine_position_side,
    evaluate_boj_signal,
    evaluate_portfolio_boj_impact,
    load_canonical_holdings,
    load_canonical_research_sensitivities,
    project_position_impact,
)


def test_market_probability_alone_capped_at_orange() -> None:
    signal_data = {
        "boj_state": "RED",
        "primary_evidence_present": False,
        "probability_only": True,
        "reason": "Market OIS implies 90% September hike probability.",
    }
    eval_result = evaluate_boj_signal(signal_data)
    assert eval_result["raw_state"] == "RED"
    assert eval_result["effective_state"] == "ORANGE"
    assert eval_result["probability_only"] is True
    assert eval_result["primary_evidence_present"] is False
    assert "[CAPPED_AT_ORANGE]" in eval_result["reason"]


def test_primary_evidence_allows_red() -> None:
    signal_data = {
        "boj_state": "RED",
        "primary_evidence_present": True,
        "probability_only": False,
        "reason": "BOJ Governor explicit hawkish press conference statement.",
    }
    eval_result = evaluate_boj_signal(signal_data)
    assert eval_result["raw_state"] == "RED"
    assert eval_result["effective_state"] == "RED"
    assert eval_result["primary_evidence_present"] is True


def test_missing_or_invalid_signal_fails_closed_to_unknown() -> None:
    # Invalid string state
    eval_invalid = evaluate_boj_signal({"boj_state": "INVALID_STATE"})
    assert eval_invalid["effective_state"] == "UNKNOWN"

    # Missing signal state key
    eval_missing = evaluate_boj_signal({})
    assert eval_missing["effective_state"] == "UNKNOWN"


def test_missing_sensitivity_defaults_to_unknown_fail_closed() -> None:
    position = {
        "security_code": "9999",
        "security_name": "Unknown Corp",
        "position_type": "cash",
        "quantity": 100,
    }
    signal_eval = {"effective_state": "RED", "raw_state": "RED", "primary_evidence_present": True, "probability_only": False, "reason": "RED test"}
    impact = project_position_impact(position, signal_eval)

    assert impact["rate_sensitivity"] == "UNKNOWN"
    assert impact["yen_sensitivity"] == "UNKNOWN"
    assert impact["energy_input_sensitivity"] == "UNKNOWN"
    assert impact["valuation_duration"] == "UNKNOWN"
    assert impact["balance_sheet_rate_risk"] == "UNKNOWN"
    assert impact["confidence"] == "UNKNOWN"
    # Missing sensitivity must fail-closed and cannot produce REDUCE_CANDIDATE or EXIT_REVIEW
    assert impact["boj_risk_action"] in {"WATCH", "HOLD"}
    assert impact["boj_risk_action"] != "REDUCE_CANDIDATE"
    assert impact["boj_risk_action"] != "EXIT_REVIEW"


def test_incomplete_mixed_sensitivity_fails_closed() -> None:
    position = {
        "security_code": "3778",
        "security_name": "さくらインターネット",
        "position_type": "margin_long",
        "quantity": 100,
    }
    signal_eval = {"effective_state": "RED", "raw_state": "RED", "primary_evidence_present": True, "probability_only": False, "reason": "RED test"}
    # Sensitivity map has HIGH for rate, but UNKNOWN for valuation_duration
    incomplete_sens_map = {
        "3778": {
            "rate_sensitivity": "HIGH",
            "yen_sensitivity": "MIXED",
            "energy_input_sensitivity": "HIGH",
            "valuation_duration": "UNKNOWN",
            "balance_sheet_rate_risk": "HIGH",
        }
    }
    risk_ctx = {"3778": {"thesis_invalidation": True}}
    impact = project_position_impact(position, signal_eval, sensitivity_map=incomplete_sens_map, risk_context=risk_ctx)

    # Incomplete facts fail closed to WATCH even under RED + thesis invalidation
    assert impact["boj_risk_action"] == "WATCH"
    assert impact["boj_risk_action"] != "EXIT_REVIEW"
    assert impact["boj_risk_action"] != "REDUCE_CANDIDATE"


def test_unknown_position_type_fails_closed() -> None:
    assert determine_position_side("cash") == "LONG"
    assert determine_position_side("margin_long") == "LONG"
    assert determine_position_side("margin_short") == "SHORT"
    assert determine_position_side("unsupported_side") == "UNKNOWN"

    position = {
        "security_code": "1321",
        "security_name": "ETF",
        "position_type": "unsupported_side",
        "quantity": 10,
    }
    signal_eval = {"effective_state": "ORANGE", "raw_state": "ORANGE", "primary_evidence_present": False, "probability_only": True, "reason": "ORANGE test"}
    impact = project_position_impact(position, signal_eval)

    assert impact["position_side"] == "UNKNOWN"
    assert impact["boj_risk_action"] == "WATCH"


def test_short_position_side_preserved() -> None:
    position = {
        "security_code": "3291",
        "security_name": "飯田グループホールディングス",
        "position_type": "margin_short",
        "quantity": 100,
    }
    signal_eval = {"effective_state": "RED", "raw_state": "RED", "primary_evidence_present": True, "probability_only": False, "reason": "RED test"}
    impact = project_position_impact(position, signal_eval)

    assert impact["position_side"] == "SHORT"
    assert impact["boj_risk_action"] not in {"REDUCE_CANDIDATE", "EXIT_REVIEW"}
    assert impact["boj_risk_action"] in {"HOLD", "WATCH"}


def test_position_scoped_risk_context_prevents_global_leak() -> None:
    pos_sakura = {
        "security_code": "3778",
        "security_name": "さくらインターネット",
        "position_type": "margin_long",
        "quantity": 100,
    }
    pos_ai = {
        "security_code": "247A",
        "security_name": "Aiロボティクス",
        "position_type": "cash",
        "quantity": 300,
    }
    sens_map = {
        "3778": {
            "rate_sensitivity": "HIGH", "yen_sensitivity": "MIXED", "energy_input_sensitivity": "HIGH",
            "valuation_duration": "HIGH", "balance_sheet_rate_risk": "HIGH",
        },
        "247A": {
            "rate_sensitivity": "HIGH", "yen_sensitivity": "MIXED", "energy_input_sensitivity": "MEDIUM",
            "valuation_duration": "HIGH", "balance_sheet_rate_risk": "HIGH",
        },
    }
    signal_eval = {"effective_state": "RED", "raw_state": "RED", "primary_evidence_present": True, "probability_only": False, "reason": "RED primary evidence"}

    # Scoped risk context ONLY targeting 3778
    risk_ctx = {"3778": {"thesis_invalidation": True}}

    impact_sakura = project_position_impact(pos_sakura, signal_eval, sensitivity_map=sens_map, risk_context=risk_ctx)
    impact_ai = project_position_impact(pos_ai, signal_eval, sensitivity_map=sens_map, risk_context=risk_ctx)

    assert impact_sakura["boj_risk_action"] == "EXIT_REVIEW"
    # 247A must NOT leak to EXIT_REVIEW
    assert impact_ai["boj_risk_action"] == "REDUCE_CANDIDATE"


def test_dynamic_canonical_research_artifact_loading() -> None:
    sensitivities = load_canonical_research_sensitivities()
    assert "3778" in sensitivities
    assert sensitivities["3778"]["rate_sensitivity"] == "HIGH"
    assert "06_Research/boj_evidence/3778_sakura_internet.md" in sensitivities["3778"]["evidence_refs"]


def test_deterministic_identical_input_identical_output() -> None:
    holdings = load_canonical_holdings()
    signal = {"boj_state": "ORANGE", "primary_evidence_present": False, "probability_only": True}

    res1 = evaluate_portfolio_boj_impact(holdings_input=holdings, boj_signal_input=signal)
    res2 = evaluate_portfolio_boj_impact(holdings_input=holdings, boj_signal_input=signal)

    assert res1 == res2
    assert json.dumps(res1, sort_keys=True) == json.dumps(res2, sort_keys=True)


def test_malformed_non_numeric_quantity_fails_closed() -> None:
    """Regression: malformed non-numeric quantity must not raise ValueError; fail closed to 0."""
    position = {
        "security_code": "3778",
        "security_name": "さくらインターネット",
        "position_type": "margin_long",
        "quantity": "abc",  # Non-numeric string
    }
    signal_eval = {
        "effective_state": "RED",
        "raw_state": "RED",
        "primary_evidence_present": True,
        "probability_only": False,
        "reason": "RED test",
    }
    # Should not raise ValueError/TypeError
    impact = project_position_impact(position, signal_eval)
    assert impact["quantity"] == 0
    assert impact["security_code"] == "3778"


def test_malformed_fractional_string_quantity_fails_closed() -> None:
    """Regression: fractional-string quantity must not raise ValueError; fail closed to 0."""
    position = {
        "security_code": "247A",
        "security_name": "Aiロボティクス",
        "position_type": "cash",
        "quantity": "123.45",  # Fractional string
    }
    signal_eval = {
        "effective_state": "ORANGE",
        "raw_state": "ORANGE",
        "primary_evidence_present": False,
        "probability_only": True,
        "reason": "ORANGE test",
    }
    # Should not raise ValueError/TypeError
    impact = project_position_impact(position, signal_eval)
    assert impact["quantity"] == 0
    assert impact["security_code"] == "247A"
