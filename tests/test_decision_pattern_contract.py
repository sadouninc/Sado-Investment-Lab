from copy import deepcopy

import pytest

from scripts.decision_pattern_contract import (
    PatternContractValidationError,
    pattern_identity,
    validate_pattern_record,
)


def _record(**overrides):
    value = {
        "pattern_id": "SELL_EARLY_STRONG_THESIS",
        "status": "POSSIBLE_PATTERN",
        "definition": "Explicit observable process pattern",
        "supporting_episode_refs": ["episode:1", "episode:2"],
        "counterexample_episode_refs": ["episode:3"],
        "sample_size": 3,
        "data_sufficiency": "INSUFFICIENT_DATA",
        "confidence": "LOW",
        "decision_quality_refs": ["decision-quality:1"],
        "outcome_refs": ["outcome:1"],
        "execution_fidelity_refs": ["execution-fidelity:1"],
        "retrospective_episode_refs": [],
        "explicit_psychology_context_refs": [],
        "suggested_guardrail": None,
        "owner_acknowledged": False,
    }
    value.update(overrides)
    return value


def test_supporting_and_counterexamples_are_preserved_independently():
    result = validate_pattern_record(_record())
    assert result["supporting_episode_refs"] == ["episode:1", "episode:2"]
    assert result["counterexample_episode_refs"] == ["episode:3"]
    assert result["sample_size"] == 3
    assert result["data_sufficiency"] == "INSUFFICIENT_DATA"


@pytest.mark.parametrize(
    "status",
    [
        "OBSERVATION",
        "POSSIBLE_PATTERN",
        "REPEATED_PATTERN",
        "ACTIONABLE_INSIGHT",
        "RETIRED",
    ],
)
def test_lifecycle_enum_is_explicit(status):
    assert validate_pattern_record(_record(status=status))["status"] == status


def test_invalid_lifecycle_and_sufficiency_fail_closed():
    with pytest.raises(PatternContractValidationError):
        validate_pattern_record(_record(status="PROMOTED_BY_COUNT"))
    with pytest.raises(PatternContractValidationError):
        validate_pattern_record(_record(data_sufficiency="ENOUGH_PROBABLY"))


def test_missing_required_or_unknown_field_fails_closed():
    missing = _record()
    del missing["counterexample_episode_refs"]
    with pytest.raises(PatternContractValidationError):
        validate_pattern_record(missing)
    with pytest.raises(PatternContractValidationError):
        validate_pattern_record(_record(trade_action="BUY"))


def test_sample_size_is_explicit_not_inferred_or_promoted():
    with pytest.raises(PatternContractValidationError):
        validate_pattern_record(_record(sample_size=99))
    result = validate_pattern_record(_record(status="OBSERVATION", data_sufficiency="INSUFFICIENT_DATA"))
    assert result["status"] == "OBSERVATION"
    assert result["data_sufficiency"] == "INSUFFICIENT_DATA"


def test_decision_quality_outcome_and_execution_fidelity_stay_separate():
    result = validate_pattern_record(_record())
    assert result["decision_quality_refs"] == ["decision-quality:1"]
    assert result["outcome_refs"] == ["outcome:1"]
    assert result["execution_fidelity_refs"] == ["execution-fidelity:1"]


def test_optional_reference_fields_remain_absent_when_not_supplied():
    source = _record()
    optional_ref_fields = (
        "decision_quality_refs",
        "outcome_refs",
        "execution_fidelity_refs",
        "retrospective_episode_refs",
        "explicit_psychology_context_refs",
    )
    for field in optional_ref_fields:
        del source[field]
    result = validate_pattern_record(source)
    for field in optional_ref_fields:
        assert field not in result


def test_retrospective_refs_must_be_observed_and_remain_explicit():
    result = validate_pattern_record(_record(retrospective_episode_refs=["episode:2"]))
    assert result["retrospective_episode_refs"] == ["episode:2"]
    with pytest.raises(PatternContractValidationError):
        validate_pattern_record(_record(retrospective_episode_refs=["episode:future"]))


def test_psychology_context_requires_explicit_refs_not_inference_fields():
    result = validate_pattern_record(
        _record(explicit_psychology_context_refs=["owner-context:1"])
    )
    assert result["explicit_psychology_context_refs"] == ["owner-context:1"]
    with pytest.raises(PatternContractValidationError):
        validate_pattern_record(_record(inferred_bias="FOMO"))


def test_support_counterexample_overlap_fails_closed():
    with pytest.raises(PatternContractValidationError):
        validate_pattern_record(
            _record(counterexample_episode_refs=["episode:2"], sample_size=2)
        )


def test_owner_acknowledgement_is_preserved_not_generated():
    no_ack = _record()
    del no_ack["owner_acknowledged"]
    result = validate_pattern_record(no_ack)
    assert "owner_acknowledged" not in result


def test_deterministic_identity_and_input_non_mutation():
    source = _record()
    before = deepcopy(source)
    first = pattern_identity(source)
    second = pattern_identity(source)
    assert first == second
    assert source == before
