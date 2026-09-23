from copy import deepcopy

import pytest

from scripts.outcome_attribution import AXIS_ORDER, _project_axis, project_outcome_attribution


def _base_input():
    return {
        "episode_ref": "episode:1",
        "decision_refs": ["decision:1"],
        "evaluation_as_of": "2026-09-23T21:57:00+09:00",
        "axes": {},
        "observations": [],
        "owner_reflection": None,
    }


def test_missing_history_is_explicit_and_axis_order_is_stable():
    result = project_outcome_attribution(_base_input())

    assert tuple(result["axes"]) == AXIS_ORDER
    assert result["axes"]["thesis"]["status"] == "NOT_JUDGABLE"
    assert result["axes"]["timing"]["status"] == "NOT_JUDGABLE"
    assert result["axes"]["allocation"]["status"] == "NOT_JUDGABLE"
    assert result["axes"]["allocation"]["opportunity_set_ref"] is None
    assert result["axes"]["execution"]["status"] == "NOT_JUDGABLE"
    assert result["axes"]["execution"]["fidelity_ref"] is None
    assert result["axes"]["market_context"]["status"] == "UNAVAILABLE"
    assert result["axes"]["market_context"]["benchmark_refs"] == []
    assert result["axes"]["data_quality"]["status"] == "PARTIAL"


def test_axes_remain_independent_without_pl_or_hindsight_inference():
    source = _base_input()
    source["profit_loss"] = 123456  # intentionally outside the contract
    source["axes"] = {
        "thesis": {"status": "INVALIDATED", "refs": ["hypothesis:v1"]},
        "timing": {
            "status": "PARTIAL",
            "metrics": {"exit_latency_minutes": 5},
            "refs": ["decision:1"],
        },
        "execution": {"status": "MISMATCH", "fidelity_ref": "fidelity:1"},
        "market_context": {"status": "AVAILABLE", "benchmark_refs": ["benchmark:topix:1"]},
    }

    result = project_outcome_attribution(source)

    assert result["axes"]["thesis"]["status"] == "INVALIDATED"
    assert result["axes"]["timing"]["status"] == "PARTIAL"
    assert result["axes"]["execution"]["status"] == "MISMATCH"
    assert result["axes"]["market_context"]["status"] == "AVAILABLE"
    assert "profit_loss" not in result
    assert "score" not in result
    assert "recommendation" not in result


def test_canonical_refs_are_preserved_but_never_invented():
    source = _base_input()
    source["decision_refs"] = ["decision:1", "", None, 123]
    source["axes"] = {
        "allocation": {"status": "OBSERVED", "opportunity_set_ref": "opp:1"},
        "execution": {"status": "MATCH", "fidelity_ref": "fidelity:1"},
        "data_quality": {"status": "CONFLICTING", "coverage_ref": "coverage:1"},
    }

    result = project_outcome_attribution(source)

    assert result["decision_refs"] == ["decision:1"]
    assert result["axes"]["allocation"]["opportunity_set_ref"] == "opp:1"
    assert result["axes"]["execution"]["fidelity_ref"] == "fidelity:1"
    assert result["axes"]["data_quality"]["coverage_ref"] == "coverage:1"


def test_unknown_status_fails_closed_to_axis_missing_semantics():
    source = _base_input()
    source["axes"] = {
        "thesis": {"status": "GOOD"},
        "market_context": {"status": "NEUTRAL", "benchmark_refs": []},
    }

    result = project_outcome_attribution(source)

    assert result["axes"]["thesis"]["status"] == "NOT_JUDGABLE"
    assert result["axes"]["market_context"]["status"] == "UNAVAILABLE"


def test_unknown_axis_fails_closed_with_value_error():
    with pytest.raises(ValueError, match="unknown axis: sentiment"):
        _project_axis("sentiment", {})


def test_projection_is_deterministic_and_does_not_mutate_input():
    source = _base_input()
    source["axes"] = {
        "thesis": {"status": "SUPPORTED", "refs": ["hypothesis:v1"]},
        "timing": {"status": "OBSERVED", "metrics": {"review_latency_minutes": 12}},
    }
    source["observations"] = [{"kind": "FACT", "ref": "evidence:1"}]
    before = deepcopy(source)

    first = project_outcome_attribution(source)
    second = project_outcome_attribution(source)

    assert first == second
    assert source == before
    first["observations"][0]["kind"] = "MUTATED_OUTPUT"
    assert source == before


def test_projector_does_not_infer_owner_decision_time_from_fill():
    source = _base_input()
    source["fill_timestamp"] = "2026-09-23T10:00:00+09:00"
    source["axes"] = {"timing": {"status": "PARTIAL", "metrics": {}}}

    result = project_outcome_attribution(source)

    assert result["axes"]["timing"]["status"] == "PARTIAL"
    assert result["axes"]["timing"]["metrics"] == {}
    assert "fill_timestamp" not in result
