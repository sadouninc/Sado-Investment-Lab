from copy import deepcopy

import pytest

from scripts.opportunity_cost_ledger import (
    capture_opportunity_set,
    deterministic_opportunity_set_id,
    validate_opportunity_set,
)


def sample():
    return {
        "decision_ref": "decision:2026-08-09:001",
        "captured_at": "2026-08-09T16:45:00+09:00",
        "actor": "SADO",
        "capital_context": {
            "available_cash": None,
            "margin_capacity": None,
            "known_constraints": [],
        },
        "chosen_action": {"security_code": "6622", "action": "BUY"},
        "alternatives": [
            {
                "security_code": "7974",
                "action": "BUY",
                "source": "CANDIDATE_SELECTOR",
                "candidate_ref": "candidate:7974:v1",
                "rank_at_decision": 2,
                "research_ref": None,
                "valuation_ref": None,
                "hypothesis_ref": None,
                "why_feasible": "判断時点でeligible candidateだった",
                "why_not_chosen": "ResearchがMISSINGだった",
                "data_status": "MISSING",
            },
            {
                "action": "CASH",
                "source": "SYSTEM",
                "why_feasible": "投資を見送り現金を維持できる",
                "data_status": "CURRENT",
            },
        ],
        "selection_rule": "TOP_N_ELIGIBLE_PLUS_OWNER_NAMED",
        "snapshot_freshness": "captured_at時点の参照状態を固定",
    }


def test_capture_adds_deterministic_identity_and_cash():
    result = capture_opportunity_set(sample())
    assert result["opportunity_set_id"] == deterministic_opportunity_set_id(
        "decision:2026-08-09:001", "2026-08-09T16:45:00+09:00"
    )
    cash = next(item for item in result["alternatives"] if item["action"] == "CASH")
    assert cash["security_code"] is None
    assert cash["source"] == "SYSTEM"


def test_idempotent_retry_returns_same_snapshot():
    first = capture_opportunity_set(sample())
    second = capture_opportunity_set(sample(), existing=first)
    assert second == first


def test_immutable_snapshot_rejects_later_winner_insertion():
    first = capture_opportunity_set(sample())
    changed = sample()
    changed["alternatives"].append({
        "security_code": "4063",
        "action": "BUY",
        "source": "OWNER_NAMED",
        "why_feasible": "後から追加",
        "data_status": "CURRENT",
    })
    with pytest.raises(ValueError, match="immutable"):
        capture_opportunity_set(changed, existing=first)


def test_candidate_rank_is_frozen_and_requires_provenance():
    value = sample()
    del value["alternatives"][0]["candidate_ref"]
    with pytest.raises(ValueError, match="candidate_ref"):
        validate_opportunity_set(value)

    value = sample()
    value["alternatives"][0]["rank_at_decision"] = None
    with pytest.raises(ValueError, match="rank_at_decision"):
        validate_opportunity_set(value)


def test_missing_research_remains_missing_not_zero_or_current():
    result = validate_opportunity_set(sample())
    candidate = next(item for item in result["alternatives"] if item["security_code"] == "7974")
    assert candidate["data_status"] == "MISSING"
    assert candidate["research_ref"] is None


def test_cash_cannot_be_disguised_as_security():
    value = sample()
    value["alternatives"][1]["security_code"] = "7974"
    with pytest.raises(ValueError, match="must not have security_code"):
        validate_opportunity_set(value)


def test_duplicate_alternative_rejected():
    value = sample()
    value["alternatives"].append(deepcopy(value["alternatives"][0]))
    with pytest.raises(ValueError, match="duplicate alternatives"):
        validate_opportunity_set(value)


def test_chosen_action_cannot_also_be_alternative():
    value = sample()
    value["alternatives"].append({
        "security_code": "6622",
        "action": "BUY",
        "source": "OWNER_NAMED",
        "why_feasible": "same",
        "data_status": "CURRENT",
    })
    with pytest.raises(ValueError, match="chosen action"):
        validate_opportunity_set(value)


def test_timezone_is_required():
    value = sample()
    value["captured_at"] = "2026-08-09T16:45:00"
    with pytest.raises(ValueError, match="timezone"):
        validate_opportunity_set(value)


def test_input_is_not_mutated():
    value = sample()
    before = deepcopy(value)
    validate_opportunity_set(value)
    assert value == before
