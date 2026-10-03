from copy import deepcopy

import pytest

from scripts.company_episode_execution_fidelity_view import (
    CompanyEpisodeExecutionFidelityViewError,
    FIDELITY_EXPLANATION_JA,
    VIEW_VERSION,
    build_company_episode_execution_fidelity_view,
)


def _episode():
    return {
        "episode_id": "episode:6622:abc123",
        "security_code": "6622",
        "status": "OPEN",
        "decision_refs": ["decision:6622:1", "decision:6622:2"],
    }


def _learning_record(fidelity_status="MATCH", outcome_status="POSITIVE", quality_status="SUPPORTED"):
    return {
        "decision_quality": {
            "status": quality_status,
            "canonical_refs": ["decision:6622:1"],
        },
        "execution_fidelity": {
            "status": fidelity_status,
            "canonical_refs": ["intent:6622:1", "execution:6622:1"],
        },
        "outcome": {
            "status": outcome_status,
            "canonical_refs": ["outcome:6622:1"],
        },
    }


def test_three_axes_are_independently_represented():
    episode = _episode()
    records = {"decision:6622:1": _learning_record()}

    result = build_company_episode_execution_fidelity_view(episode, records)

    decision = result["decisions"][0]
    assert decision["decision_quality"]["status"] == "SUPPORTED"
    assert decision["execution_fidelity"]["status"] == "MATCH"
    assert decision["outcome"]["status"] == "POSITIVE"
    assert decision["decision_quality"]["label_ja"] == "裏付けあり"
    assert decision["execution_fidelity"]["label_ja"] == "一致"
    assert decision["outcome"]["label_ja"] == "好結果"


def test_view_version_and_header_fields():
    result = build_company_episode_execution_fidelity_view(_episode(), {})
    assert result["type"] == "COMPANY_EPISODE_EXECUTION_FIDELITY_VIEW"
    assert result["view_version"] == VIEW_VERSION
    assert result["episode_ref"] == "episode:6622:abc123"
    assert result["security_code"] == "6622"
    assert result["episode_status"] == "OPEN"


def test_japanese_explanation_clarifies_fidelity_is_not_quality_scoring():
    result = build_company_episode_execution_fidelity_view(_episode(), {})
    assert result["fidelity_explanation_ja"] == FIDELITY_EXPLANATION_JA
    assert "投資判断の質" in FIDELITY_EXPLANATION_JA
    assert "採点する指標ではありません" in FIDELITY_EXPLANATION_JA


def test_missing_learning_record_fails_closed_to_unknown_not_match():
    episode = _episode()
    result = build_company_episode_execution_fidelity_view(episode, {})

    for decision in result["decisions"]:
        assert decision["decision_quality"]["status"] == "UNKNOWN"
        assert decision["execution_fidelity"]["status"] == "UNKNOWN"
        assert decision["outcome"]["status"] == "UNKNOWN"
        assert decision["execution_fidelity"]["canonical_refs"] == []


@pytest.mark.parametrize(
    "fidelity_status",
    ["UNKNOWN", "NOT_JUDGABLE", "NOT_EXECUTED", "PARTIAL_MATCH"],
)
def test_fail_closed_fidelity_states_remain_visible_and_not_promoted(fidelity_status):
    episode = _episode()
    records = {"decision:6622:1": _learning_record(fidelity_status=fidelity_status)}

    result = build_company_episode_execution_fidelity_view(episode, records)

    decision = result["decisions"][0]
    assert decision["execution_fidelity"]["status"] == fidelity_status
    assert decision["execution_fidelity"]["status"] != "MATCH"


def test_canonical_refs_are_preserved_for_drill_down():
    episode = _episode()
    records = {"decision:6622:1": _learning_record()}

    result = build_company_episode_execution_fidelity_view(episode, records)
    decision = result["decisions"][0]

    assert decision["decision_quality"]["canonical_refs"] == ["decision:6622:1"]
    assert decision["execution_fidelity"]["canonical_refs"] == [
        "intent:6622:1",
        "execution:6622:1",
    ]
    assert decision["outcome"]["canonical_refs"] == ["outcome:6622:1"]


def test_negative_outcome_does_not_change_decision_quality_or_fidelity():
    episode = _episode()
    records = {
        "decision:6622:1": _learning_record(
            outcome_status="NEGATIVE", quality_status="SUPPORTED", fidelity_status="MATCH"
        )
    }

    result = build_company_episode_execution_fidelity_view(episode, records)
    decision = result["decisions"][0]

    assert decision["outcome"]["status"] == "NEGATIVE"
    assert decision["decision_quality"]["status"] == "SUPPORTED"
    assert decision["execution_fidelity"]["status"] == "MATCH"


def test_no_trade_action_or_recommendation_is_emitted():
    result = build_company_episode_execution_fidelity_view(_episode(), {})
    assert result["trade_action"] is None
    assert "recommendation" not in result
    for decision in result["decisions"]:
        assert "trade_action" not in decision
        assert "recommendation" not in decision


def test_does_not_mutate_inputs():
    episode = _episode()
    records = {"decision:6622:1": _learning_record()}
    episode_before = deepcopy(episode)
    records_before = deepcopy(records)

    build_company_episode_execution_fidelity_view(episode, records)

    assert episode == episode_before
    assert records == records_before


@pytest.mark.parametrize(
    "mutator",
    [
        lambda e: e.pop("episode_id"),
        lambda e: e.pop("security_code"),
        lambda e: e.pop("status"),
        lambda e: e.update({"decision_refs": "not-a-list"}),
        lambda e: e.update({"decision_refs": [""]}),
    ],
)
def test_malformed_episode_fails_closed(mutator):
    episode = _episode()
    mutator(episode)
    with pytest.raises(CompanyEpisodeExecutionFidelityViewError):
        build_company_episode_execution_fidelity_view(episode, {})


def test_malformed_learning_record_fails_closed():
    episode = _episode()
    records = {"decision:6622:1": {"execution_fidelity": {"status": "BOGUS"}}}
    with pytest.raises(CompanyEpisodeExecutionFidelityViewError):
        build_company_episode_execution_fidelity_view(episode, records)


def test_non_mapping_learning_records_container_fails_closed():
    episode = _episode()
    with pytest.raises(CompanyEpisodeExecutionFidelityViewError):
        build_company_episode_execution_fidelity_view(episode, ["not", "a", "mapping"])
