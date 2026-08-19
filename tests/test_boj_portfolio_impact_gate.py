from __future__ import annotations

import json
from pathlib import Path
from scripts.boj_portfolio_impact_gate import (
    evaluate_boj_signal,
    evaluate_portfolio_boj_impact,
    load_canonical_holdings,
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
    # missing sensitivity must not produce REDUCE_CANDIDATE or EXIT_REVIEW
    assert impact["boj_risk_action"] in {"WATCH", "HOLD"}
    assert impact["boj_risk_action"] != "REDUCE_CANDIDATE"
    assert impact["boj_risk_action"] != "EXIT_REVIEW"


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


def test_boj_red_alone_does_not_produce_exit_review() -> None:
    position = {
        "security_code": "3778",
        "security_name": "さくらインターネット",
        "position_type": "margin_long",
        "quantity": 100,
    }
    signal_eval = {"effective_state": "RED", "raw_state": "RED", "primary_evidence_present": True, "probability_only": False, "reason": "RED primary evidence"}
    impact = project_position_impact(position, signal_eval, risk_context=None)

    assert impact["boj_risk_action"] == "REDUCE_CANDIDATE"
    assert impact["boj_risk_action"] != "EXIT_REVIEW"


def test_boj_red_with_thesis_invalidation_produces_exit_review() -> None:
    position = {
        "security_code": "3778",
        "security_name": "さくらインターネット",
        "position_type": "margin_long",
        "quantity": 100,
    }
    signal_eval = {"effective_state": "RED", "raw_state": "RED", "primary_evidence_present": True, "probability_only": False, "reason": "RED primary evidence"}
    risk_ctx = {"thesis_invalidation": True}
    impact = project_position_impact(position, signal_eval, risk_context=risk_ctx)

    assert impact["boj_risk_action"] == "EXIT_REVIEW"


def test_deterministic_identical_input_identical_output() -> None:
    holdings = load_canonical_holdings()
    signal = {"boj_state": "ORANGE", "primary_evidence_present": False, "probability_only": True}

    res1 = evaluate_portfolio_boj_impact(holdings_input=holdings, boj_signal_input=signal)
    res2 = evaluate_portfolio_boj_impact(holdings_input=holdings, boj_signal_input=signal)

    assert res1 == res2
    assert json.dumps(res1, sort_keys=True) == json.dumps(res2, sort_keys=True)


def test_canonical_holdings_ssot_loading() -> None:
    holdings = load_canonical_holdings()
    assert holdings["status"] in {"VERIFIED", "PROVISIONAL", "OK"}
    assert len(holdings["positions"]) >= 1
    codes = [p["security_code"] for p in holdings["positions"]]
    assert "3778" in codes
    assert "247A" in codes
    assert "3291" in codes
