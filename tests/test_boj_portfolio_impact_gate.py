from __future__ import annotations

import json
from scripts.boj_portfolio_impact_gate import (
    determine_position_side,
    evaluate_boj_signal,
    evaluate_portfolio_boj_impact,
    load_canonical_holdings,
    load_canonical_research_sensitivities,
    parse_position_quantity,
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
    """Valid primary BOJ evidence with tightening indication allows RED classification."""
    signal_data = {
        "boj_state": "RED",
        "primary_evidence": {
            "primary_evidence_present": True,
            "evidence_status": "VALID",
            "indicates_near_term_tightening": True,
            "evidence_refs": [{"ref_id": "gov-1", "source_title": "Governor Press Conference", "evidence_type": "GOVERNOR_SPEECH"}],
        },
        "market_factors": {"market_implied_probability": 0.75},
    }
    eval_result = evaluate_boj_signal(signal_data)
    assert eval_result["raw_state"] == "RED"
    assert eval_result["effective_state"] == "RED"
    assert eval_result["primary_evidence_present"] is True
    assert eval_result["probability_only"] is False


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


def test_malformed_and_fractional_quantity_fail_closed() -> None:
    # Valid quantities
    assert parse_position_quantity(100) == (100, True)
    assert parse_position_quantity("100") == (100, True)
    assert parse_position_quantity(None) == (0, True)

    # Non-numeric string quantity
    val_non_numeric, valid_non_numeric = parse_position_quantity("abc")
    assert val_non_numeric == "abc"
    assert valid_non_numeric is False

    # Fractional string quantity
    val_fractional, valid_fractional = parse_position_quantity("100.5")
    assert val_fractional == "100.5"
    assert valid_fractional is False

    # Position evaluation with non-numeric quantity
    pos_non_numeric = {
        "security_code": "3778",
        "security_name": "さくらインターネット",
        "position_type": "margin_long",
        "quantity": "abc",
    }
    signal_eval = {"effective_state": "RED", "raw_state": "RED", "primary_evidence_present": True, "probability_only": False, "reason": "RED test"}
    impact_non_numeric = project_position_impact(pos_non_numeric, signal_eval)

    assert impact_non_numeric["quantity"] == "abc"
    assert impact_non_numeric["boj_risk_action"] == "WATCH"
    assert "Malformed quantity" in impact_non_numeric["notes"]

    # Position evaluation with fractional string quantity
    pos_fractional = {
        "security_code": "3778",
        "security_name": "さくらインターネット",
        "position_type": "margin_long",
        "quantity": "100.5",
    }
    impact_fractional = project_position_impact(pos_fractional, signal_eval)

    assert impact_fractional["quantity"] == "100.5"
    assert impact_fractional["boj_risk_action"] == "WATCH"
    assert "Malformed quantity" in impact_fractional["notes"]


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


def test_adapter_with_real_canonical_ledger_shape():
    """
    Adapter-level regression: evaluate_boj_signal with real canonical ledger shape.
    
    Real canonical ledger identified by Luna review 5238569928:
    - boj_state=ORANGE
    - policy_delta=STRENGTHENS_ORANGE  
    - policy_pricing.next_meeting_hike_probability_pct=80.0
    - interpretation.red_gate=NOT_MET_PRIMARY_EVIDENCE_REQUIRED
    
    Expected: effective_state=ORANGE
    Market probability alone must NOT produce RED without valid primary evidence.
    """
    real_canonical_signal = {
        "boj_state": "ORANGE",
        "policy_delta": "STRENGTHENS_ORANGE",
        "policy_pricing": {
            "next_meeting_hike_probability_pct": 80.0
        },
        "interpretation": {
            "red_gate": "NOT_MET_PRIMARY_EVIDENCE_REQUIRED"
        }
    }
    
    result = evaluate_boj_signal(real_canonical_signal)
    
    # Core assertions: market probability alone cannot produce RED
    assert result is not None
    assert "effective_state" in result
    assert result["effective_state"] == "ORANGE"
    
    # Additional guardrails
    assert result.get("primary_evidence_present") is not True  # No valid primary evidence
    
    # Market probability is recorded but does not elevate to RED
    assert result.get("market_implied_probability_pct") == 80.0


def test_adapter_policy_delta_strengthens_orange_maps_to_market_prob_rising():
    """
    Adapter-level regression: policy_delta=STRENGTHENS_ORANGE with sub-50% market probability.
    
    Proves ORANGE is preserved via market_prob_rising when policy_delta indicates strengthening,
    even when market probability is below 50%.
    
    Guardrails:
    - Do NOT infer inflation_upside, hawkish_breadth_expanding, macro_pressures from policy_delta
    - Only market_prob_rising is set from policy_delta=STRENGTHENS_ORANGE
    """
    signal_with_delta = {
        "boj_state": "ORANGE",
        "policy_delta": "STRENGTHENS_ORANGE",
        "policy_pricing": {
            "next_meeting_hike_probability_pct": 35.0  # sub-50%
        },
        "interpretation": {
            "red_gate": "NOT_MET_PRIMARY_EVIDENCE_REQUIRED"
        }
    }
    
    result = evaluate_boj_signal(signal_with_delta)
    
    # ORANGE should be preserved via market_prob_rising from policy_delta
    assert result["effective_state"] == "ORANGE"
    assert result.get("primary_evidence_present") is not True
    assert result.get("market_implied_probability_pct") == 35.0


def test_adapter_control_no_delta_no_unrelated_factor_manufactured():
    """
    Control test: same sub-50% market probability WITHOUT policy_delta.
    
    Proves that no unrelated hawkish factor is manufactured when policy_delta is absent.
    The signal should downgrade appropriately based on sub-50% probability alone.
    """
    signal_without_delta = {
        "boj_state": "ORANGE",
        # NO policy_delta
        "policy_pricing": {
            "next_meeting_hike_probability_pct": 35.0  # sub-50%
        },
        "interpretation": {
            "red_gate": "NOT_MET_PRIMARY_EVIDENCE_REQUIRED"
        }
    }
    
    result = evaluate_boj_signal(signal_without_delta)
    
    # Without policy_delta strengthening signal, sub-50% probability should not maintain ORANGE
    # This verifies no unrelated factor is manufactured
    assert result["effective_state"] == "GREEN"
    assert result.get("market_implied_probability_pct") == 35.0
