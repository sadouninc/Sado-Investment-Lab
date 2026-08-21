from __future__ import annotations

import pytest

from scripts.intraday_subsector_aggregation import (
    aggregate_intraday_subsector_snapshot,
    append_snapshot_history,
)


SECTOR = {
    "id": "healthcare-pharmaceutical",
    "label": "Pharmaceutical",
    "medium_term_regime": "COLD",
}
SUBSECTOR = {
    "id": "biotechnology",
    "label": "Biotechnology",
    "taxonomy_version": "theme-v1",
    "as_of": "2026-08-14",
    "source_or_authority": "canonical-theme-taxonomy",
}


def build(**overrides):
    values = {
        "observed_at": "2026-08-14T10:00:00+09:00",
        "source": "fixture",
        "freshness": "FRESH",
        "benchmark": "TOPIX",
        "benchmark_return": 0.01,
        "sector": SECTOR,
        "subsector": SUBSECTOR,
        "membership_count": 5,
        "constituents": [
            {"security_code": "4588", "name": "Oncolys", "intraday_return": 0.08, "turnover_ratio": 2.0},
            {"security_code": "4592", "name": "SanBio", "intraday_return": 0.04, "turnover_ratio": 1.8},
            {"security_code": "A003", "name": "C", "intraday_return": 0.02, "turnover_ratio": 1.4},
            {"security_code": "A004", "name": "D", "intraday_return": 0.01, "turnover_ratio": 1.1},
            {"security_code": "A005", "name": "E", "intraday_return": -0.01, "turnover_ratio": 0.9},
        ],
    }
    values.update(overrides)
    return aggregate_intraday_subsector_snapshot(**values)


def test_broad_inflow_aggregates_expected_raw_metrics():
    snapshot = build()
    obs = snapshot["observations"]
    assert obs["intraday_return"] == pytest.approx(0.028)
    assert obs["relative_return"] == pytest.approx(0.018)
    assert obs["rising_count"] == 4
    assert obs["constituent_count"] == 5
    assert obs["breadth"] == pytest.approx(0.8)
    assert obs["median_constituent_return"] == pytest.approx(0.02)
    assert obs["turnover_ratio"] == pytest.approx(1.4)
    assert snapshot["leaders"][0]["security_code"] == "4588"
    assert snapshot["flow_state"] == "UNKNOWN"
    assert snapshot["acceleration_state"] == "UNKNOWN"


def test_single_leader_spike_keeps_high_concentration_and_narrow_breadth():
    snapshot = build(
        membership_count=5,
        constituents=[
            {"security_code": "4588", "name": "Oncolys", "intraday_return": 0.10},
            {"security_code": "A002", "name": "B", "intraday_return": -0.01},
            {"security_code": "A003", "name": "C", "intraday_return": -0.02},
            {"security_code": "A004", "name": "D", "intraday_return": -0.01},
            {"security_code": "A005", "name": "E", "intraday_return": -0.03},
        ],
    )
    obs = snapshot["observations"]
    assert obs["breadth"] == pytest.approx(0.2)
    assert obs["concentration_top1"] == pytest.approx(1.0)


def test_partial_observations_do_not_coerce_missing_return_to_zero():
    snapshot = build(
        membership_count=5,
        constituents=[
            {"security_code": "4588", "name": "Oncolys", "intraday_return": 0.08},
            {"security_code": "4592", "name": "SanBio", "intraday_return": None},
            {"security_code": "A003", "name": "C", "intraday_return": 0.02},
        ],
    )
    obs = snapshot["observations"]
    assert snapshot["data_completeness"] == "PARTIAL"
    assert obs["constituent_count"] == 2
    assert obs["breadth"] == pytest.approx(1.0)
    assert obs["intraday_return"] == pytest.approx(0.05)


def test_missing_benchmark_keeps_relative_return_null():
    snapshot = build(benchmark_return=None)
    assert snapshot["observations"]["benchmark_return"] is None
    assert snapshot["observations"]["relative_return"] is None


def test_leader_order_has_deterministic_security_code_tie_break():
    snapshot = build(
        membership_count=2,
        constituents=[
            {"security_code": "2000", "name": "B", "intraday_return": 0.05},
            {"security_code": "1000", "name": "A", "intraday_return": 0.05},
        ],
    )
    assert [item["security_code"] for item in snapshot["leaders"]] == ["1000", "2000"]


def test_repeated_same_snapshot_is_idempotent():
    snapshot = build()
    once = append_snapshot_history([], snapshot)
    twice = append_snapshot_history(once, snapshot)
    assert twice == once
    assert len(twice) == 1


def test_two_intraday_snapshots_are_append_only_and_comparable_later():
    morning = build(observed_at="2026-08-14T10:00:00+09:00")
    midday = build(observed_at="2026-08-14T12:30:00+09:00")
    history = append_snapshot_history([], morning)
    history = append_snapshot_history(history, midday)
    assert len(history) == 2
    assert [item["observed_at"] for item in history] == [
        "2026-08-14T10:00:00+09:00",
        "2026-08-14T12:30:00+09:00",
    ]


def test_reversal_replay_sequence_aggregation_distinguishes_isolated_resilience_from_breadth_recovery():
    """Verify raw aggregation across sequence RISK_OFF_BROAD -> ISOLATED_RESILIENCE -> BREADTH_RECOVERY -> PARTIAL_OR_STALE."""
    # 1. RISK_OFF_BROAD: Broad decline
    s1 = build(
        observed_at="2026-08-14T09:15:00+09:00",
        benchmark_return=-0.015,
        membership_count=5,
        constituents=[
            {"security_code": "4588", "name": "Oncolys", "intraday_return": -0.020, "turnover_ratio": 1.1},
            {"security_code": "4592", "name": "SanBio", "intraday_return": -0.018, "turnover_ratio": 1.0},
            {"security_code": "A003", "name": "C", "intraday_return": -0.015, "turnover_ratio": 0.9},
            {"security_code": "A004", "name": "D", "intraday_return": -0.012, "turnover_ratio": 0.8},
            {"security_code": "A005", "name": "E", "intraday_return": -0.025, "turnover_ratio": 1.2},
        ],
    )
    obs1 = s1["observations"]
    assert obs1["rising_count"] == 0
    assert obs1["breadth"] == pytest.approx(0.0)
    assert obs1["concentration_top1"] is None
    assert s1["data_completeness"] == "COMPLETE"
    assert s1["flow_state"] == "UNKNOWN"

    # 2. ISOLATED_RESILIENCE: Single leader turns positive while rest stay negative
    s2 = build(
        observed_at="2026-08-14T09:45:00+09:00",
        benchmark_return=-0.010,
        membership_count=5,
        constituents=[
            {"security_code": "4588", "name": "Oncolys", "intraday_return": 0.050, "turnover_ratio": 2.2},
            {"security_code": "4592", "name": "SanBio", "intraday_return": -0.010, "turnover_ratio": 1.1},
            {"security_code": "A003", "name": "C", "intraday_return": -0.012, "turnover_ratio": 0.9},
            {"security_code": "A004", "name": "D", "intraday_return": -0.008, "turnover_ratio": 0.8},
            {"security_code": "A005", "name": "E", "intraday_return": -0.020, "turnover_ratio": 1.0},
        ],
    )
    obs2 = s2["observations"]
    assert obs2["rising_count"] == 1
    assert obs2["breadth"] == pytest.approx(0.2)
    assert obs2["concentration_top1"] == pytest.approx(1.0)
    assert s2["leaders"][0]["security_code"] == "4588"
    assert s2["leaders"][0]["intraday_return"] == pytest.approx(0.050)

    # 3. BREADTH_RECOVERY: Broad participation turns positive
    s3 = build(
        observed_at="2026-08-14T10:30:00+09:00",
        benchmark_return=0.002,
        membership_count=5,
        constituents=[
            {"security_code": "4588", "name": "Oncolys", "intraday_return": 0.077, "turnover_ratio": 2.5},
            {"security_code": "4592", "name": "SanBio", "intraday_return": 0.041, "turnover_ratio": 2.0},
            {"security_code": "A003", "name": "C", "intraday_return": 0.025, "turnover_ratio": 1.5},
            {"security_code": "A004", "name": "D", "intraday_return": 0.018, "turnover_ratio": 1.3},
            {"security_code": "A005", "name": "E", "intraday_return": -0.005, "turnover_ratio": 1.0},
        ],
    )
    obs3 = s3["observations"]
    assert obs3["rising_count"] == 4
    assert obs3["breadth"] == pytest.approx(0.8)
    assert obs3["concentration_top1"] == pytest.approx(0.077 / (0.077 + 0.041 + 0.025 + 0.018))
    assert obs3["breadth"] > obs2["breadth"]
    assert obs3["concentration_top1"] < obs2["concentration_top1"]

    # 4. PARTIAL_OR_STALE: Data feed stale or missing constituent returns
    s4 = build(
        observed_at="2026-08-14T11:30:00+09:00",
        freshness="STALE",
        benchmark_return=0.005,
        membership_count=5,
        constituents=[
            {"security_code": "4588", "name": "Oncolys", "intraday_return": 0.080, "turnover_ratio": 2.6},
            {"security_code": "4592", "name": "SanBio", "intraday_return": None, "turnover_ratio": None},
            {"security_code": "A003", "name": "C", "intraday_return": 0.020, "turnover_ratio": 1.4},
        ],
    )
    obs4 = s4["observations"]
    assert s4["freshness"] == "STALE"
    assert s4["data_completeness"] == "PARTIAL"
    assert obs4["constituent_count"] == 2
    assert obs4["rising_count"] == 2
    assert obs4["intraday_return"] == pytest.approx(0.050)
