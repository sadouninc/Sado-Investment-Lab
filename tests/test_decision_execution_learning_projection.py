from copy import deepcopy

import pytest

from scripts.decision_execution_learning_projection import (
    PROJECTION_VERSION,
    project_execution_fidelity_learning,
)


def _record():
    return {
        "decision_quality": {
            "status": "UNKNOWN",
            "canonical_refs": ["decision:42"],
            "details": {"explicit_only": True},
        },
        "execution_fidelity": {
            "status": "PARTIAL_MATCH",
            "canonical_refs": ["intent:42", "execution:99"],
        },
        "outcome": {
            "status": "NEGATIVE",
            "canonical_refs": ["outcome:42"],
            "details": {"pnl": -100},
        },
    }


def test_projection_preserves_independent_axes_and_refs():
    result = project_execution_fidelity_learning(_record())

    assert result["projection_version"] == PROJECTION_VERSION
    assert result["decision_quality"]["status"] == "UNKNOWN"
    assert result["execution_fidelity"]["status"] == "PARTIAL_MATCH"
    assert result["outcome"]["status"] == "NEGATIVE"
    assert result["decision_quality"]["canonical_refs"] == ["decision:42"]
    assert result["execution_fidelity"]["canonical_refs"] == [
        "intent:42",
        "execution:99",
    ]


@pytest.mark.parametrize(
    "fidelity",
    ["UNKNOWN", "NOT_JUDGABLE", "NOT_EXECUTED", "PARTIAL_MATCH"],
)
def test_fail_closed_fidelity_states_are_not_collapsed(fidelity):
    record = _record()
    record["execution_fidelity"]["status"] = fidelity
    assert (
        project_execution_fidelity_learning(record)["execution_fidelity"]["status"]
        == fidelity
    )


def test_negative_outcome_does_not_infer_decision_quality():
    result = project_execution_fidelity_learning(_record())
    assert result["outcome"]["status"] == "NEGATIVE"
    assert result["decision_quality"]["status"] == "UNKNOWN"


@pytest.mark.parametrize("bad", [None, "", "PARTIAL", "BUY", 1])
def test_malformed_or_unsupported_fidelity_fails_closed(bad):
    record = _record()
    record["execution_fidelity"]["status"] = bad
    with pytest.raises(ValueError):
        project_execution_fidelity_learning(record)


def test_missing_fidelity_status_fails_closed():
    record = _record()
    del record["execution_fidelity"]["status"]
    with pytest.raises(ValueError):
        project_execution_fidelity_learning(record)


def test_projection_is_deterministic_and_does_not_mutate_input():
    record = _record()
    before = deepcopy(record)

    first = project_execution_fidelity_learning(record)
    second = project_execution_fidelity_learning(record)

    assert first == second
    assert record == before
    assert first is not record
    assert first["decision_quality"]["details"] is not record["decision_quality"]["details"]


def test_fill_like_unowned_fields_do_not_create_owner_intent():
    record = _record()
    record["fills"] = [{"side": "BUY", "quantity": 100}]

    result = project_execution_fidelity_learning(record)

    assert "fills" not in result
    assert "owner_intent" not in result
    assert result["decision_quality"]["status"] == "UNKNOWN"
