import copy

import pytest

from scripts.decision_review_comparison import (
    DecisionReviewComparisonError,
    build_decision_review_comparison,
)


def decision():
    return {
        "decision_id": "decision:6622:abc",
        "security_code": "6622",
        "owner_judgment": {
            "why_now": "受注と利益成長を確認",
            "biggest_risk": "需要鈍化",
            "what_changes_my_mind": "利益前提の下方修正",
        },
    }


def snapshot():
    return {
        "decision_ref": "decision:6622:abc",
        "security_code": "6622",
        "valuation": {"ref": "val:old", "base": 720.0, "forward_per": 16.5},
        "hypothesis": {"ref": "hyp:old", "health": "INTACT"},
        "expectations": {"ref": "exp:old", "status": "OK", "sado_vs_consensus_gap_pct": 5.0},
        "portfolio": {"ref": "p:old", "freshness": "CURRENT"},
        "market_price": {"source_ref": "price:old", "status": "CURRENT", "value": 11900},
        "research": {"ref": "r:old", "status": "CURRENT"},
        "opportunity_set_ref": "opp:old",
    }


def current():
    return {
        "security_code": "6622",
        "valuation": {"ref": "val:new", "base": 780.0, "forward_per": 14.8},
        "hypothesis": {"ref": "hyp:new", "health": "STRENGTHENING"},
        "expectations": {"ref": "exp:new", "status": "OK", "sado_vs_consensus_gap_pct": 8.0},
        "portfolio": {"ref": "p:new", "freshness": "CURRENT"},
        "market_price": {"source_ref": "price:new", "status": "CURRENT", "value": 12500},
        "research": {"ref": "r:new", "status": "CURRENT"},
        "checkpoints": [],
    }


def test_reports_deterministic_state_and_numeric_changes_without_quality_score():
    result = build_decision_review_comparison(decision(), snapshot(), current())
    types = {x["type"] for x in result["changes"]}
    assert "EARNINGS_REVISION_UP" in types
    assert "VALUATION_CHEAPER" in types
    assert "HYPOTHESIS_STRENGTHENED" in types
    assert "EXPECTATION_GAP_WIDENED" in types
    assert result["decision_quality"] is None
    assert result["outcome"] is None
    assert result["trade_action"] is None
    assert result["material_threshold"] == "UNSET"


def test_broken_hypothesis_is_high_priority():
    now = current()
    now["hypothesis"]["health"] = "BROKEN"
    result = build_decision_review_comparison(decision(), snapshot(), now)
    assert result["review_summary"][0]["type"] == "HYPOTHESIS_BROKEN"


def test_missing_current_source_is_not_no_change():
    now = current()
    now["research"] = {"ref": None, "status": "MISSING"}
    result = build_decision_review_comparison(decision(), snapshot(), now)
    assert "SOURCE_MISSING" in {x["type"] for x in result["changes"]}


def test_stale_source_is_visible():
    now = current()
    now["portfolio"]["freshness"] = "STALE"
    result = build_decision_review_comparison(decision(), snapshot(), now)
    assert "SOURCE_STALE" in {x["type"] for x in result["changes"]}


def test_checkpoint_due_and_unhandled_are_distinct():
    now = current()
    now["checkpoints"] = [
        {"ref": "event:1", "status": "DUE"},
        {"ref": "event:2", "status": "OCCURRED_UNHANDLED"},
    ]
    result = build_decision_review_comparison(decision(), snapshot(), now)
    types = {x["type"] for x in result["changes"]}
    assert {"CHECKPOINT_DUE", "CHECKPOINT_OCCURRED_UNHANDLED"} <= types


def test_owner_context_is_left_side_only_and_preserved():
    d = decision()
    result = build_decision_review_comparison(d, snapshot(), current())
    assert result["owner_context"] == d["owner_judgment"]


def test_opportunity_set_ref_stays_at_decision_ref():
    now = current()
    now["opportunity_set_ref"] = "opp:new-winner"
    result = build_decision_review_comparison(decision(), snapshot(), now)
    assert result["opportunity_set_ref"] == "opp:old"


def test_summary_is_capped_at_five():
    now = current()
    now["hypothesis"]["health"] = "BROKEN"
    now["research"] = {"ref": None, "status": "MISSING"}
    now["portfolio"]["freshness"] = "STALE"
    now["checkpoints"] = [{"ref": f"e:{i}", "status": "OCCURRED_UNHANDLED"} for i in range(4)]
    result = build_decision_review_comparison(decision(), snapshot(), now)
    assert len(result["review_summary"]) == 5


def test_invalid_summary_limit_fails_closed():
    with pytest.raises(DecisionReviewComparisonError):
        build_decision_review_comparison(decision(), snapshot(), current(), max_change_summaries=6)


def test_security_mismatch_fails_closed():
    now = current()
    now["security_code"] = "7974"
    with pytest.raises(DecisionReviewComparisonError):
        build_decision_review_comparison(decision(), snapshot(), now)


def test_inputs_are_not_mutated():
    d, s, n = decision(), snapshot(), current()
    before = copy.deepcopy((d, s, n))
    build_decision_review_comparison(d, s, n)
    assert (d, s, n) == before


def test_identical_input_is_deterministic():
    a = build_decision_review_comparison(decision(), snapshot(), current())
    b = build_decision_review_comparison(decision(), snapshot(), current())
    assert a == b
