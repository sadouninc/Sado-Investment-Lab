import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reasoning_research_actions import build_guided_research_plan


def coverage(**statuses):
    defaults = {
        "why_candidate": "SUPPORTED", "business_driver": "SUPPORTED",
        "base_scenario": "SUPPORTED", "bear_bull_range": "SUPPORTED",
        "valuation": "SUPPORTED", "hypothesis": "SUPPORTED",
        "invalidation": "DEFINED", "market_expectation": "SUPPORTED",
        "next_evidence": "DEFINED",
    }
    defaults.update(statuses)
    return {
        "security_code": "6622", "as_of": "2026-08-09T22:30:00+09:00",
        "sections": {name: {"status": status} for name, status in defaults.items()},
        "canonical_refs": ["company-research:6622"],
        "owner_uncertainties": [], "system_uncertainties": [],
    }


def test_all_supported_has_prompts_but_no_forced_actions():
    out = build_guided_research_plan(coverage())
    assert len(out["guided_prompts"]) == 9
    assert out["next_research_actions"] == []
    assert out["semantics"]["trade_recommendation"] is None


def test_base_partial_maps_to_earnings_driver_research():
    out = build_guided_research_plan(coverage(base_scenario="PARTIAL"))
    assert out["next_research_actions"][0]["action"] == "CHECK_EARNINGS_DRIVER"
    assert "Base利益" in out["next_research_actions"][0]["prompt_ja"]


def test_invalidation_not_defined_maps_to_define_invalidation():
    out = build_guided_research_plan(coverage(invalidation="NOT_YET_DEFINED"))
    assert out["next_research_actions"][0]["action"] == "DEFINE_INVALIDATION"


def test_consensus_unavailable_is_not_neutral_and_maps_to_safe_review():
    out = build_guided_research_plan(coverage(market_expectation="UNAVAILABLE"))
    action = out["next_research_actions"][0]
    assert action["status"] == "UNAVAILABLE"
    assert action["action"] == "REVIEW_WITHOUT_CONSENSUS"


def test_stale_valuation_requests_refresh():
    out = build_guided_research_plan(coverage(valuation="STALE"))
    assert out["next_research_actions"][0]["action"] == "REFRESH_PRICE_BASIS"


def test_conflict_is_prioritized_and_actions_are_bounded_to_three():
    out = build_guided_research_plan(coverage(
        hypothesis="CONFLICTING", invalidation="NOT_YET_DEFINED", valuation="STALE",
        why_candidate="UNKNOWN", market_expectation="UNAVAILABLE"))
    assert len(out["next_research_actions"]) == 3
    assert [row["action"] for row in out["next_research_actions"]] == [
        "RESOLVE_HYPOTHESIS_CONFLICT", "DEFINE_INVALIDATION", "REFRESH_PRICE_BASIS"]


def test_partial_never_becomes_trade_prohibition_or_recommendation():
    out = build_guided_research_plan(coverage(base_scenario="PARTIAL", bear_bull_range="PARTIAL"))
    text = repr(out)
    for forbidden in ("DO_NOT_TRADE", "'BUY'", "'SELL'", "'ADD'", "'REDUCE'"):
        assert forbidden not in text
    assert out["semantics"]["partial_does_not_prohibit_trade"] is True


def test_owner_assumption_is_validation_action_not_system_confidence():
    out = build_guided_research_plan(coverage(base_scenario="OWNER_ASSUMPTION"))
    assert out["next_research_actions"][0]["action"] == "VALIDATE_OWNER_ASSUMPTION"
    assert "confidence" not in repr(out).lower()


def test_deterministic_and_non_mutating():
    source = coverage(base_scenario="PARTIAL", next_evidence="UNKNOWN")
    before = copy.deepcopy(source)
    assert build_guided_research_plan(source) == build_guided_research_plan(source)
    assert source == before


@pytest.mark.parametrize("value", [0, 4, True, 1.5])
def test_max_actions_fail_closed(value):
    with pytest.raises(ValueError):
        build_guided_research_plan(coverage(), max_actions=value)
