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


def test_coexisting_same_timestamp_distinct_series() -> None:
    profile = _profile("candidate-a", 0.015)
    ts = "2026-08-14T09:30:00+09:00"
    bio = _snapshot(observed_at=ts, relative_return=0.02)
    med = _snapshot(observed_at=ts, relative_return=0.01)
    med["subsector"] = {
        "id": "medical_devices",
        "label": "Medical Devices",
        "taxonomy_version": "theme-v1",
        "as_of": "2026-08-14",
        "source_or_authority": "existing-theme-taxonomy",
    }

    replay = replay_profile([bio, med], profile)
    assert len(replay) == 2
    keys = [r["series_key"] for r in replay]
    assert len(set(keys)) == 2
    assert all(r["acceleration_state"] == "UNKNOWN" for r in replay)


def test_interleaved_series_replay_only_compares_same_series() -> None:
    profile = _profile("candidate-a", 0.015)
    ts1 = "2026-08-14T09:30:00+09:00"
    ts2 = "2026-08-14T10:00:00+09:00"

    a1 = _snapshot(observed_at=ts1, relative_return=0.005)
    a2 = _snapshot(observed_at=ts2, relative_return=0.02)

    b1 = _snapshot(observed_at=ts1, relative_return=0.03)
    b1["subsector"] = {
        "id": "medical_devices",
        "label": "Medical Devices",
        "taxonomy_version": "theme-v1",
        "as_of": "2026-08-14",
        "source_or_authority": "existing-theme-taxonomy",
    }
    b2 = _snapshot(observed_at=ts2, relative_return=0.01)
    b2["subsector"] = deepcopy(b1["subsector"])

    replay = replay_profile([a1, b1, a2, b2], profile)
    assert len(replay) == 4

    rows_by_row_key = {r["row_key"]: r for r in replay}
    a2_row = rows_by_row_key[a2["subsector"]["taxonomy_version"] + ":" + a2["sector"]["id"] + ":" + a2["subsector"]["id"] + ":" + a2["source"] + ":" + ts2]
    b2_row = rows_by_row_key[b2["subsector"]["taxonomy_version"] + ":" + b2["sector"]["id"] + ":" + b2["subsector"]["id"] + ":" + b2["source"] + ":" + ts2]

    assert a2_row["acceleration_state"] == "ACCELERATING"
    assert b2_row["acceleration_state"] == "DECELERATING"


def test_direct_cross_series_acceleration_fails_closed() -> None:
    profile = _profile("candidate-a", 0.015)
    bio = _snapshot(relative_return=0.005)
    med = _snapshot(relative_return=0.02)
    med["subsector"] = {
        "id": "medical_devices",
        "label": "Medical Devices",
        "taxonomy_version": "theme-v1",
        "as_of": "2026-08-14",
        "source_or_authority": "existing-theme-taxonomy",
    }

    acc = classify_acceleration(bio, med, profile)
    assert acc["acceleration_state"] == "UNKNOWN"
    assert acc["classification_reason"] == "CROSS_SERIES_MISMATCH"


def test_shuffled_input_yields_deterministic_replay() -> None:
    profile = _profile("candidate-a", 0.015)
    ts1 = "2026-08-14T09:30:00+09:00"
    ts2 = "2026-08-14T10:00:00+09:00"

    a1 = _snapshot(observed_at=ts1, relative_return=0.005)
    a2 = _snapshot(observed_at=ts2, relative_return=0.02)
    b1 = _snapshot(observed_at=ts1, relative_return=0.01)
    b1["subsector"] = {
        "id": "medical_devices",
        "label": "Medical Devices",
        "taxonomy_version": "theme-v1",
        "as_of": "2026-08-14",
        "source_or_authority": "existing-theme-taxonomy",
    }
    b2 = _snapshot(observed_at=ts2, relative_return=0.025)
    b2["subsector"] = deepcopy(b1["subsector"])

    r1 = replay_profile([a1, b1, a2, b2], profile)
    r2 = replay_profile([b2, a2, b1, a1], profile)
    assert r1 == r2


def test_idempotent_and_conflicting_duplicate_row_key() -> None:
    profile = _profile("candidate-a", 0.015)
    snap1 = _snapshot(relative_return=0.02)
    snap2 = deepcopy(snap1)

    r = replay_profile([snap1, snap2], profile)
    assert len(r) == 1

    conflicting = deepcopy(snap1)
    conflicting["observations"]["relative_return"] = 0.05
    conflicting["observations"]["intraday_return"] = 0.055
    with pytest.raises(ValueError, match="conflicting duplicate snapshot"):
        replay_profile([snap1, conflicting], profile)
