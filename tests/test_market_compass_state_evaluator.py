"""Tests for Market Compass state evaluator v0.1 (#586 B3)."""

from copy import deepcopy

from scripts.market_compass_state_evaluator import (
    evaluate_market_compass_universe_states,
    evaluate_security_state,
)


def test_avoid_state_on_integrity_fail_or_unknown_or_unquantified():
    sec_fail = {
        "security_code": "1321",
        "fundamental_integrity": "FAIL",
        "scores": {
            "excess_decline": 20,
            "valuation_reset": 20,
            "fundamental_strength": 20,
            "risk_stabilization": 20,
        },
    }
    res_fail = evaluate_security_state(sec_fail)
    assert res_fail["evaluation_status"] == "EVALUATED"
    assert res_fail["market_compass_state"] == "AVOID"

    sec_unknown = {
        "security_code": "1321",
        "fundamental_integrity": "UNKNOWN",
        "scores": {
            "excess_decline": 20,
            "valuation_reset": 20,
            "fundamental_strength": 20,
            "risk_stabilization": 20,
        },
    }
    res_unknown = evaluate_security_state(sec_unknown)
    assert res_unknown["evaluation_status"] == "EVALUATED"
    assert res_unknown["market_compass_state"] == "AVOID"

    sec_unquantified = {
        "security_code": "1321",
        "fundamental_integrity": "PASS",
        "unquantified_deterioration": True,
        "scores": {
            "excess_decline": 20,
            "valuation_reset": 20,
            "fundamental_strength": 20,
            "risk_stabilization": 20,
        },
    }
    res_unquantified = evaluate_security_state(sec_unquantified)
    assert res_unquantified["evaluation_status"] == "EVALUATED"
    assert res_unquantified["market_compass_state"] == "AVOID"


def test_watch_state_boundaries():
    # Pass/Review integrity, total < 50 OR risk_stabilization < 10
    sec1 = {
        "security_code": "247A",
        "fundamental_integrity": "PASS",
        "scores": {
            "excess_decline": 10,
            "valuation_reset": 10,
            "fundamental_strength": 10,
            "risk_stabilization": 9,
        },
    }
    res1 = evaluate_security_state(sec1)
    assert res1["evaluation_status"] == "EVALUATED"
    assert res1["market_compass_state"] == "WATCH"
    assert res1["score_total"] == 39

    sec2 = {
        "security_code": "247A",
        "fundamental_integrity": "REVIEW",
        "scores": {
            "excess_decline": 20,
            "valuation_reset": 20,
            "fundamental_strength": 20,
            "risk_stabilization": 5,
        },
    }
    res2 = evaluate_security_state(sec2)
    assert res2["evaluation_status"] == "EVALUATED"
    assert res2["market_compass_state"] == "WATCH"
    assert res2["score_total"] == 65


def test_buy_watch_state_boundaries():
    sec = {
        "security_code": "3778",
        "membership": "REENTRY_WATCH",
        "fundamental_integrity": "PASS",
        "scores": {
            "excess_decline": 15,
            "valuation_reset": 15,
            "fundamental_strength": 15,
            "risk_stabilization": 10,
        },
    }
    res = evaluate_security_state(sec)
    assert res["evaluation_status"] == "EVALUATED"
    assert res["market_compass_state"] == "BUY_WATCH"
    assert res["score_total"] == 55


def test_reentry_ready_state_boundaries():
    sec = {
        "security_code": "6702",
        "membership": "REENTRY_WATCH",
        "fundamental_integrity": "PASS",
        "confidence": "HIGH",
        "verified_stabilization_count": 3,
        "scores": {
            "excess_decline": 20,
            "valuation_reset": 20,
            "fundamental_strength": 15,
            "risk_stabilization": 15,
        },
    }
    res = evaluate_security_state(sec)
    assert res["evaluation_status"] == "EVALUATED"
    assert res["market_compass_state"] == "REENTRY_READY"
    assert res["score_total"] == 70


def test_reentry_ready_fails_closed_when_confidence_low_or_insufficient_stabilization():
    sec_low_conf = {
        "security_code": "6702",
        "membership": "REENTRY_WATCH",
        "fundamental_integrity": "PASS",
        "confidence": "LOW",
        "verified_stabilization_count": 4,
        "scores": {
            "excess_decline": 20,
            "valuation_reset": 20,
            "fundamental_strength": 15,
            "risk_stabilization": 15,
        },
    }
    res_low_conf = evaluate_security_state(sec_low_conf)
    # Should fall through to BUY_WATCH since BUY_WATCH criteria are met and REENTRY_READY rejected
    assert res_low_conf["evaluation_status"] == "EVALUATED"
    assert res_low_conf["market_compass_state"] == "BUY_WATCH"

    sec_low_stab = {
        "security_code": "6702",
        "membership": "REENTRY_WATCH",
        "fundamental_integrity": "PASS",
        "confidence": "HIGH",
        "verified_stabilization_count": 2,
        "scores": {
            "excess_decline": 20,
            "valuation_reset": 20,
            "fundamental_strength": 15,
            "risk_stabilization": 15,
        },
    }
    res_low_stab = evaluate_security_state(sec_low_stab)
    assert res_low_stab["evaluation_status"] == "EVALUATED"
    assert res_low_stab["market_compass_state"] == "BUY_WATCH"


def test_membership_unknown_fails_closed_preventing_buy_watch_and_reentry_ready():
    sec_buy_watch = {
        "security_code": "3778",
        "membership": "MEMBERSHIP_UNKNOWN",
        "fundamental_integrity": "PASS",
        "scores": {
            "excess_decline": 15,
            "valuation_reset": 15,
            "fundamental_strength": 15,
            "risk_stabilization": 10,
        },
    }
    res_bw = evaluate_security_state(sec_buy_watch)
    assert res_bw["evaluation_status"] == "UNKNOWN"
    assert res_bw["market_compass_state"] is None
    assert res_bw["reason"] == "MEMBERSHIP_UNKNOWN_FAIL_CLOSED"

    sec_reentry = {
        "security_code": "6702",
        "membership": "MEMBERSHIP_UNKNOWN",
        "fundamental_integrity": "PASS",
        "confidence": "HIGH",
        "verified_stabilization_count": 3,
        "scores": {
            "excess_decline": 20,
            "valuation_reset": 20,
            "fundamental_strength": 15,
            "risk_stabilization": 15,
        },
    }
    res_rr = evaluate_security_state(sec_reentry)
    assert res_rr["evaluation_status"] == "UNKNOWN"
    assert res_rr["market_compass_state"] is None
    assert res_rr["reason"] == "MEMBERSHIP_UNKNOWN_FAIL_CLOSED"


def test_unknown_score_fails_closed_without_coercing_to_zero():
    sec_missing_score = {
        "security_code": "7011",
        "membership": "CURRENT_HOLDING",
        "fundamental_integrity": "PASS",
        "scores": {
            "excess_decline": 20,
            "valuation_reset": None,  # forward PER unavailable => Valuation Reset UNKNOWN
            "fundamental_strength": 15,
            "risk_stabilization": 15,
        },
    }
    res = evaluate_security_state(sec_missing_score)
    assert res["evaluation_status"] == "UNKNOWN"
    assert res["market_compass_state"] is None
    assert res["score_total"] is None
    assert res["reason"] == "SCORE_UNKNOWN"


def test_evaluate_market_compass_universe_states_preserves_immutability():
    universe = {
        "schema_version": 1,
        "as_of": "2026-08-23",
        "current_holdings": [
            {
                "security_code": "1321",
                "membership": "CURRENT_HOLDING",
                "fundamental_integrity": "PASS",
                "scores": {
                    "excess_decline": 5,
                    "valuation_reset": 5,
                    "fundamental_strength": 5,
                    "risk_stabilization": 5,
                },
            }
        ],
        "reentry_watch": [],
        "membership_unknown": [],
    }
    universe_copy = deepcopy(universe)
    evaluated = evaluate_market_compass_universe_states(universe)

    assert universe == universe_copy
    assert len(evaluated["current_holdings"]) == 1
    assert evaluated["current_holdings"][0]["evaluation_status"] == "EVALUATED"
    assert evaluated["current_holdings"][0]["market_compass_state"] == "WATCH"
