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
