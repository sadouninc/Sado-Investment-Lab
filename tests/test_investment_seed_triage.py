import pytest

from scripts.investment_seed_triage import (
    TRIAGE_DIMENSIONS,
    evaluate_research_candidate_readiness,
    validate_triage_contract,
)


def contract(**overrides):
    base = {
        "origin_seed_ref": "seed:2026-08-13:example",
        "provenance": {
            "observation_refs": ["seed:2026-08-13:example#observation"],
            "inference_refs": ["analysis:transmission:1"],
        },
        "dimensions": {
            "novelty": {
                "level": "HIGH",
                "rationale": "Primary disclosure changes the prior baseline.",
                "evidence_refs": ["ev:1"],
            },
            "magnitude": {
                "level": "MEDIUM",
                "rationale": "Material enough to affect the relevant equipment category.",
                "evidence_refs": ["ev:1"],
            },
            "transmission_plausibility": {
                "level": "HIGH",
                "rationale": "Supply constraint can reach orders and revenue.",
                "evidence_refs": ["ev:1"],
            },
            "signal_lead": {
                "level": "MEDIUM",
                "rationale": "Observed before the next earnings disclosure.",
                "evidence_refs": ["ev:1"],
            },
            "japan_equity_relevance": {
                "level": "HIGH",
                "rationale": "Japanese listed suppliers participate in the value chain.",
                "evidence_refs": ["ev:1"],
            },
            "expectation_gap_potential": {
                "level": "MEDIUM",
                "rationale": "Market pricing still requires validation.",
                "evidence_refs": ["ev:1"],
            },
            "evidence_quality": {
                "level": "HIGH",
                "rationale": "Primary source is available.",
                "evidence_refs": ["ev:1"],
            },
            "counter_evidence_strength": {
                "level": "LOW",
                "rationale": "Known cancellation risk is currently limited.",
                "evidence_refs": ["ce:1"],
            },
        },
        "evidence": [
            {
                "evidence_id": "ev:1",
                "statement": "Lead time extended in the primary disclosure.",
                "source_refs": ["primary:example:1"],
            }
        ],
        "counter_evidence": [
            {
                "evidence_id": "ce:1",
                "statement": "Customer capex may be delayed.",
                "source_refs": ["challenge:example:1"],
            }
        ],
        "transmission_paths": [
            "AI data-center capex -> transformer demand -> supplier orders -> revenue"
        ],
        "japan_equity_links": ["value-chain:power-equipment-japan"],
        "next_checkpoint": "Check the next supplier order disclosure.",
        "beyond_topic_reason": "The signal has a concrete order/revenue transmission path.",
    }
    base.update(overrides)
    return base


def test_all_eight_dimensions_are_required_and_remain_independent():
    validated = validate_triage_contract(contract())
    assert tuple(validated["dimensions"]) == TRIAGE_DIMENSIONS
    assert validated["dimensions"]["novelty"]["level"] == "HIGH"
    assert validated["dimensions"]["magnitude"]["level"] == "MEDIUM"

    missing = contract()
    del missing["dimensions"]["signal_lead"]
    with pytest.raises(ValueError, match="missing triage dimensions"):
        validate_triage_contract(missing)


def test_observation_inference_evidence_and_counter_evidence_provenance_are_separate():
    validated = validate_triage_contract(contract())
    assert validated["provenance"]["observation_refs"] == [
        "seed:2026-08-13:example#observation"
    ]
    assert validated["provenance"]["inference_refs"] == ["analysis:transmission:1"]
    assert validated["evidence"][0]["source_refs"] == ["primary:example:1"]
    assert validated["counter_evidence"][0]["source_refs"] == ["challenge:example:1"]


def test_dimension_evidence_refs_must_resolve_without_silent_merging():
    invalid = contract()
    invalid["dimensions"]["novelty"]["evidence_refs"] = ["missing:1"]
    with pytest.raises(ValueError, match="unknown refs"):
        validate_triage_contract(invalid)

    overlap = contract()
    overlap["counter_evidence"][0]["evidence_id"] = "ev:1"
    with pytest.raises(ValueError, match="must remain distinct"):
        validate_triage_contract(overlap)


def test_ready_decision_is_explainable_and_never_auto_transitions_or_invests():
    result = evaluate_research_candidate_readiness(contract())
    assert result["decision"] == "READY_FOR_RESEARCH_CANDIDATE"
    assert result["blocking_reasons"] == []
    assert "TRANSMISSION_PATH_PRESENT" in result["passed_checks"]
    assert "TRIAGE_DIMENSIONS_EXPLICIT" in result["passed_checks"]
    assert result["auto_transition"] is False
    assert result["investment_decision"] is None


def test_missing_gate_inputs_return_deterministic_blocking_reasons():
    candidate = contract(
        counter_evidence=[],
        next_checkpoint=None,
        beyond_topic_reason=None,
        japan_equity_links=[],
    )
    candidate["dimensions"]["counter_evidence_strength"]["evidence_refs"] = []
    result = evaluate_research_candidate_readiness(candidate)
    assert result["decision"] == "NEEDS_MORE_EVIDENCE"
    codes = {item["code"] for item in result["blocking_reasons"]}
    assert {
        "COUNTER_EVIDENCE_PRESENT",
        "NEXT_CHECKPOINT_PRESENT",
        "BEYOND_TOPIC_REASON_PRESENT",
        "JAPAN_EQUITY_LINK_PRESENT",
    } <= codes


def test_dimension_levels_stay_visible_without_becoming_a_black_box_score():
    candidate = contract()
    candidate["dimensions"]["counter_evidence_strength"]["level"] = "HIGH"
    candidate["dimensions"]["transmission_plausibility"]["level"] = "LOW"
    result = evaluate_research_candidate_readiness(candidate)
    assert result["decision"] == "READY_FOR_RESEARCH_CANDIDATE"
    assert result["dimension_snapshot"]["counter_evidence_strength"] == "HIGH"
    assert result["dimension_snapshot"]["transmission_plausibility"] == "LOW"
    assert "score" not in result
    assert result["auto_transition"] is False
