from copy import deepcopy

import pytest

from scripts.policy_lead_time_v2 import PolicyLeadTimeError, evaluate_policy_lead_time_v2


def case(**updates):
    payload = {
        "policy_t0": "2026-01-10",
        "raw_first_warming_date": "2026-01-15",
        "raw_first_inflow_date": "2026-01-20",
        "reliable_first_warming_date": "2026-01-15",
        "reliable_first_inflow_date": "2026-01-20",
        "data_quality": "OK",
        "limitations": [],
        "post_policy_persistence": False,
        "post_policy_reacceleration": False,
    }
    payload.update(updates)
    return payload


def test_policy_leads_when_reliable_market_state_is_after_policy():
    result = evaluate_policy_lead_time_v2(case())
    assert result["classification"] == "POLICY_LEADS"
    assert result["reliable_first"]["policy_to_warming_days"] == 5
    assert result["reliable_first"]["policy_to_inflow_days"] == 10


def test_market_leads_when_reliable_state_precedes_policy_without_post_policy_confirmation():
    result = evaluate_policy_lead_time_v2(
        case(
            raw_first_warming_date="2026-01-02",
            raw_first_inflow_date="2026-01-05",
            reliable_first_warming_date="2026-01-02",
            reliable_first_inflow_date="2026-01-05",
        )
    )
    assert result["classification"] == "MARKET_LEADS"
    assert result["reliable_first"]["policy_to_inflow_days"] == -5


def test_policy_confirmation_requires_explicit_post_policy_persistence():
    result = evaluate_policy_lead_time_v2(
        case(
            reliable_first_warming_date="2026-01-02",
            reliable_first_inflow_date="2026-01-05",
            post_policy_persistence=True,
        )
    )
    assert result["classification"] == "POLICY_CONFIRMATION"


def test_reacceleration_after_policy_is_explicit_and_distinct():
    result = evaluate_policy_lead_time_v2(
        case(
            reliable_first_warming_date="2026-01-02",
            reliable_first_inflow_date="2026-01-05",
            post_policy_persistence=True,
            post_policy_reacceleration=True,
        )
    )
    assert result["classification"] == "REACCELERATION_AFTER_POLICY"


def test_partial_data_never_becomes_reliable_classification():
    result = evaluate_policy_lead_time_v2(case(data_quality="PARTIAL"))
    assert result["classification"] == "DATA_LIMITED"
    assert result["raw_first"]["warming_date"] == "2026-01-15"
    assert result["reliable_first"]["warming_date"] == "2026-01-15"


def test_retrospective_membership_limitation_is_preserved():
    result = evaluate_policy_lead_time_v2(
        case(data_quality="LIMITED", limitations=["RETROSPECTIVE_MEMBERSHIP", "BENCHMARK_PROXY"])
    )
    assert result["classification"] == "DATA_LIMITED"
    assert result["limitations"] == ["BENCHMARK_PROXY", "RETROSPECTIVE_MEMBERSHIP"]
    assert result["policy_evidence_in_market_score"] is False


def test_ai_dc_shape_preserves_raw_market_lead_and_reliable_post_policy_dates():
    result = evaluate_policy_lead_time_v2(
        case(
            policy_t0="2024-10-04",
            raw_first_inflow_date="2024-09-26",
            raw_first_warming_date="2024-11-05",
            reliable_first_warming_date="2024-11-06",
            reliable_first_inflow_date="2024-11-08",
            data_quality="LIMITED",
            limitations=["RETROSPECTIVE_MEMBERSHIP", "BENCHMARK_PROXY"],
        )
    )
    assert result["raw_first"]["policy_to_inflow_days"] == -8
    assert result["reliable_first"]["policy_to_warming_days"] == 33
    assert result["reliable_first"]["policy_to_inflow_days"] == 35
    assert result["classification"] == "DATA_LIMITED"


def test_same_day_is_inconclusive_with_date_precision_only():
    result = evaluate_policy_lead_time_v2(
        case(reliable_first_warming_date="2026-01-10", reliable_first_inflow_date=None)
    )
    assert result["classification"] == "INCONCLUSIVE"


def test_missing_reliable_state_is_not_converted_to_zero_days():
    result = evaluate_policy_lead_time_v2(
        case(reliable_first_warming_date=None, reliable_first_inflow_date=None)
    )
    assert result["classification"] == "INCONCLUSIVE"
    assert result["reliable_first"]["policy_to_warming_days"] is None
    assert result["reliable_first"]["policy_to_inflow_days"] is None


def test_reacceleration_requires_explicit_persistence_evidence():
    with pytest.raises(PolicyLeadTimeError, match="requires post_policy_persistence"):
        evaluate_policy_lead_time_v2(case(post_policy_reacceleration=True))


def test_evaluator_is_deterministic_and_non_mutating():
    source = case(limitations=["BENCHMARK_PROXY"])
    before = deepcopy(source)
    first = evaluate_policy_lead_time_v2(source)
    second = evaluate_policy_lead_time_v2(source)
    assert first == second
    assert source == before
