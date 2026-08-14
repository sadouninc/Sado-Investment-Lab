from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.intraday_subsector_validation_packet import (
    build_candidate_validation_packet,
    score_profile_replay,
    validate_validation_cases,
    validate_validation_spec,
)


def _snapshot(observed_at: str, *, relative_return: float, breadth: float) -> dict:
    intraday_return = relative_return + 0.005
    rising = int(breadth * 4)
    return {
        "schema_version": 1,
        "observed_at": observed_at,
        "source": "historical-fixture",
        "freshness": "FRESH",
        "data_completeness": "COMPLETE",
        "benchmark": "TOPIX",
        "sector": {
            "id": "pharmaceutical",
            "label": "Pharmaceutical",
            "medium_term_regime": "COLD",
        },
        "subsector": {
            "id": "biotechnology",
            "label": "Biotechnology",
            "taxonomy_version": "theme-v1",
            "as_of": "2026-08-14",
            "source_or_authority": "fixture-taxonomy",
        },
        "observations": {
            "intraday_return": intraday_return,
            "benchmark_return": 0.005,
            "relative_return": relative_return,
            "rising_count": rising,
            "constituent_count": 4,
            "breadth": rising / 4,
            "median_constituent_return": relative_return,
            "turnover_ratio": 1.2,
            "concentration_top1": 0.25,
        },
        "leaders": [],
        "flow_state": "UNKNOWN",
        "acceleration_state": "UNKNOWN",
    }


def _profile(version: str, threshold: float) -> dict:
    return {
        "version": version,
        "source_or_authority": "candidate-only",
        "rationale": "test candidate, not approved",
        "created_at": "2026-08-14T15:00:00+09:00",
        "flow_rules": [
            {
                "state": "STATE_POS",
                "all": [
                    {
                        "field": "observations.relative_return",
                        "op": ">=",
                        "value": threshold,
                    }
                ],
            },
            {
                "state": "STATE_NEG",
                "all": [
                    {
                        "field": "observations.relative_return",
                        "op": "<",
                        "value": threshold,
                    }
                ],
            },
        ],
        "acceleration_rules": [],
    }


def _spec() -> dict:
    return {
        "version": "validation-v1",
        "source_or_authority": "external-label-contract",
        "rationale": "test semantics supplied explicitly",
        "created_at": "2026-08-14T15:05:00+09:00",
        "positive_states": ["STATE_POS"],
        "negative_states": ["STATE_NEG"],
        "target_transition_states": ["STATE_POS"],
    }


def _cases() -> list[dict]:
    return [
        {
            "case_id": "case-low",
            "observed_at": "2026-08-14T09:30:00+09:00",
            "label_source_or_authority": "annotated-fixture",
            "rationale": "externally labelled negative example",
            "expected_signal": "NEGATIVE",
            "accepted_flow_states": ["STATE_NEG"],
        },
        {
            "case_id": "case-high",
            "observed_at": "2026-08-14T10:00:00+09:00",
            "label_source_or_authority": "annotated-fixture",
            "rationale": "externally labelled positive example",
            "expected_signal": "POSITIVE",
            "accepted_flow_states": ["STATE_POS"],
        },
    ]


def test_validation_spec_has_no_implicit_state_semantics() -> None:
    with pytest.raises(ValueError):
        validate_validation_spec(
            {
                "version": "v1",
                "source_or_authority": "fixture",
                "rationale": "missing mappings must fail",
                "created_at": "2026-08-14T15:05:00+09:00",
            }
        )


def test_duplicate_case_identity_fails_closed() -> None:
    cases = _cases()
    duplicate = deepcopy(cases[0])
    duplicate["observed_at"] = "2026-08-14T11:00:00+09:00"
    with pytest.raises(ValueError, match="duplicate case_id"):
        validate_validation_cases([*cases, duplicate])


def test_unknown_output_is_not_coerced_to_negative_proxy() -> None:
    replay = [
        {
            "observed_at": "2026-08-14T10:00:00+09:00",
            "flow_state": "UNKNOWN",
        }
    ]
    metrics = score_profile_replay(replay, [_cases()[1]], _spec())
    assert metrics["unknown_output_count"] == 1
    assert metrics["false_negative_proxy_count"] == 0


def test_candidate_packet_compares_without_winner_or_recommendation() -> None:
    history = [
        _snapshot(
            "2026-08-14T09:30:00+09:00", relative_return=0.005, breadth=0.25
        ),
        _snapshot(
            "2026-08-14T10:00:00+09:00", relative_return=0.03, breadth=0.75
        ),
    ]
    packet = build_candidate_validation_packet(
        history=history,
        profiles=[_profile("candidate-a", 0.01), _profile("candidate-b", 0.04)],
        cases=_cases(),
        validation_spec=_spec(),
    )
    assert set(packet["candidates"]) == {"candidate-a", "candidate-b"}
    assert "winner" not in packet
    assert "recommendation" not in packet
    assert packet["candidates"]["candidate-a"]["metrics"]["accepted_match_count"] == 2
    assert packet["candidates"]["candidate-b"]["metrics"]["false_negative_proxy_count"] == 1


def test_transition_timing_is_deterministic_from_replay_order() -> None:
    history = [
        _snapshot(
            "2026-08-14T10:00:00+09:00", relative_return=0.03, breadth=0.75
        ),
        _snapshot(
            "2026-08-14T09:30:00+09:00", relative_return=0.005, breadth=0.25
        ),
    ]
    packet = build_candidate_validation_packet(
        history=history,
        profiles=[_profile("candidate-a", 0.01)],
        cases=_cases(),
        validation_spec=_spec(),
    )
    metrics = packet["candidates"]["candidate-a"]["metrics"]
    assert metrics["first_target_transition_at"] == "2026-08-14T10:00:00+09:00"
