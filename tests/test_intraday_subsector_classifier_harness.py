from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.intraday_subsector_classifier_harness import (
    classify_acceleration,
    classify_flow,
    compare_profiles,
    replay_profile,
    validate_threshold_profile,
)


def _snapshot(
    *,
    observed_at: str = "2026-08-14T09:30:00+09:00",
    relative_return: float = 0.02,
    breadth: float = 0.75,
    freshness: str = "FRESH",
    completeness: str = "COMPLETE",
) -> dict:
    intraday_return = relative_return + 0.005
    rising = 3 if breadth == 0.75 else 2
    total = 4
    return {
        "schema_version": 1,
        "observed_at": observed_at,
        "source": "historical-fixture",
        "freshness": freshness,
        "data_completeness": completeness,
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
            "source_or_authority": "existing-theme-taxonomy",
        },
        "observations": {
            "intraday_return": intraday_return,
            "benchmark_return": 0.005,
            "relative_return": relative_return,
            "rising_count": rising,
            "constituent_count": total,
            "breadth": rising / total,
            "median_constituent_return": 0.018,
            "turnover_ratio": 1.6,
            "concentration_top1": 0.42,
        },
        "leaders": [
            {"security_code": "4588", "name": "Oncolys Bio", "intraday_return": 0.077}
        ],
        "flow_state": "UNKNOWN",
        "acceleration_state": "UNKNOWN",
    }


def _profile(version: str, strong_min: float) -> dict:
    return {
        "version": version,
        "source_or_authority": "OWNER_CANDIDATE_NOT_APPROVED",
        "rationale": "Historical validation candidate only; not an approved investment threshold.",
        "created_at": "2026-08-14T15:00:00Z",
        "flow_rules": [
            {
                "state": "STRONG_INFLOW",
                "all": [
                    {"field": "observations.relative_return", "op": ">=", "value": strong_min},
                    {"field": "observations.breadth", "op": ">=", "value": 0.7},
                ],
            },
            {
                "state": "INFLOW",
                "all": [
                    {"field": "observations.relative_return", "op": ">", "value": 0.0}
                ],
            },
        ],
        "acceleration_rules": [
            {
                "state": "ACCELERATING",
                "all": [
                    {"field": "delta.relative_return", "op": ">=", "value": 0.01}
                ],
            },
            {
                "state": "DECELERATING",
                "all": [
                    {"field": "delta.relative_return", "op": "<=", "value": -0.01}
                ],
            },
        ],
    }


def test_profile_requires_explicit_provenance_and_rules() -> None:
    with pytest.raises(ValueError, match="source_or_authority"):
        validate_threshold_profile(
            {
                "version": "candidate-a",
                "rationale": "comparison only",
                "created_at": "2026-08-14T15:00:00Z",
                "flow_rules": [],
                "acceleration_rules": [],
            }
        )


def test_classifier_has_no_implicit_default_profile() -> None:
    with pytest.raises(TypeError):
        classify_flow(_snapshot())  # type: ignore[call-arg]


def test_same_snapshot_can_differ_between_explicit_candidate_profiles() -> None:
    snapshot = _snapshot(relative_return=0.02, breadth=0.75)
    loose = classify_flow(snapshot, _profile("candidate-loose", 0.015))
    strict = classify_flow(snapshot, _profile("candidate-strict", 0.03))

    assert loose["flow_state"] == "STRONG_INFLOW"
    assert strict["flow_state"] == "INFLOW"
    assert loose["profile_version"] != strict["profile_version"]


def test_stale_or_partial_snapshot_fails_closed_to_unknown() -> None:
    profile = _profile("candidate-a", 0.015)
    stale = _snapshot(freshness="STALE")
    partial = _snapshot(completeness="PARTIAL")

    assert classify_flow(stale, profile)["flow_state"] == "UNKNOWN"
    assert classify_flow(partial, profile)["flow_state"] == "UNKNOWN"
    assert classify_flow(stale, profile)["classification_reason"] == "FAIL_CLOSED_DATA_QUALITY"


def test_acceleration_uses_only_explicit_delta_rule() -> None:
    profile = _profile("candidate-a", 0.015)
    previous = _snapshot(relative_return=0.005)
    current = _snapshot(
        observed_at="2026-08-14T10:00:00+09:00", relative_return=0.02
    )

    result = classify_acceleration(previous, current, profile)
    assert result["acceleration_state"] == "ACCELERATING"


def test_replay_is_deterministic_and_sorted_by_observed_at() -> None:
    profile = _profile("candidate-a", 0.015)
    later = _snapshot(
        observed_at="2026-08-14T10:00:00+09:00", relative_return=0.02
    )
    earlier = _snapshot(
        observed_at="2026-08-14T09:30:00+09:00", relative_return=0.005
    )

    first = replay_profile([later, earlier], profile)
    second = replay_profile([deepcopy(later), deepcopy(earlier)], deepcopy(profile))

    assert first == second
    assert first[0]["observed_at"] == "2026-08-14T09:30:00+09:00"
    assert first[0]["acceleration_state"] == "UNKNOWN"
    assert first[1]["acceleration_state"] == "ACCELERATING"


def test_compare_profiles_never_selects_a_winner() -> None:
    history = [_snapshot(relative_return=0.02, breadth=0.75)]
    packet = compare_profiles(
        history,
        [_profile("candidate-loose", 0.015), _profile("candidate-strict", 0.03)],
    )

    assert set(packet) == {"candidate-loose", "candidate-strict"}
    assert "winner" not in packet
    assert packet["candidate-loose"][0]["flow_state"] == "STRONG_INFLOW"
    assert packet["candidate-strict"][0]["flow_state"] == "INFLOW"
