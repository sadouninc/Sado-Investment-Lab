from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.apply_intraday_flow_classifier import (
    apply_classification,
    load_input_snapshots,
    write_output_jsonl,
)


@pytest.fixture
def threshold_profile():
    return {
        "version": "test-v1",
        "source_or_authority": "test",
        "rationale": "test profile",
        "created_at": "2026-08-14T00:00:00Z",
        "flow_rules": [
            {
                "state": "STRONG_INFLOW",
                "all": [
                    {"field": "observations.relative_return", "op": ">=", "value": 0.025},
                    {"field": "observations.breadth", "op": ">=", "value": 0.6},
                ],
            },
            {
                "state": "INFLOW",
                "all": [
                    {"field": "observations.relative_return", "op": ">=", "value": 0.01},
                ],
            },
            {"state": "MIXED", "all": []},
        ],
        "acceleration_rules": [
            {
                "state": "ACCELERATING",
                "all": [
                    {"field": "delta.relative_return", "op": ">=", "value": 0.01},
                ],
            },
            {"state": "STABLE", "all": []},
        ],
    }


@pytest.fixture
def raw_snapshot():
    return {
        "schema_version": 1,
        "observed_at": "2026-08-14T10:00:00+09:00",
        "source": "test",
        "freshness": "FRESH",
        "data_completeness": "COMPLETE",
        "benchmark": "TOPIX",
        "sector": {"id": "test", "label": "Test", "medium_term_regime": "NEUTRAL"},
        "subsector": {
            "id": "test",
            "label": "Test",
            "taxonomy_version": "v1",
            "as_of": "2026-08-14",
            "source_or_authority": "test",
        },
        "observations": {
            "intraday_return": 0.03,
            "benchmark_return": 0.005,
            "relative_return": 0.025,
            "rising_count": 8,
            "constituent_count": 10,
            "breadth": 0.8,
            "median_constituent_return": 0.02,
            "turnover_ratio": 1.5,
            "concentration_top1": 0.3,
        },
        "leaders": [],
        "flow_state": "UNKNOWN",
        "acceleration_state": "UNKNOWN",
    }


def test_apply_classification_classifies_flow_state(threshold_profile, raw_snapshot):
    """Classifier must assign flow_state based on profile rules."""
    classified = apply_classification([raw_snapshot], threshold_profile)
    assert len(classified) == 1
    assert classified[0]["flow_state"] == "STRONG_INFLOW"
    assert classified[0]["acceleration_state"] == "UNKNOWN"  # No previous snapshot


def test_apply_classification_with_multiple_snapshots_classifies_acceleration(
    threshold_profile, raw_snapshot
):
    """With multiple snapshots, classifier must compute acceleration_state."""
    snapshot1 = dict(raw_snapshot)
    snapshot1["observed_at"] = "2026-08-14T10:00:00+09:00"
    snapshot1["observations"]["relative_return"] = 0.01
    
    snapshot2 = dict(raw_snapshot)
    snapshot2["observed_at"] = "2026-08-14T11:00:00+09:00"
    snapshot2["observations"]["relative_return"] = 0.025
    
    classified = apply_classification([snapshot1, snapshot2], threshold_profile)
    assert len(classified) == 2
    assert classified[0]["acceleration_state"] == "UNKNOWN"  # First snapshot
    assert classified[1]["acceleration_state"] == "ACCELERATING"  # Delta +0.015


def test_load_input_snapshots_json_array(tmp_path, raw_snapshot):
    """load_input_snapshots must handle JSON array format."""
    path = tmp_path / "input.json"
    path.write_text(json.dumps([raw_snapshot]), encoding="utf-8")
    snapshots = load_input_snapshots(path)
    assert len(snapshots) == 1
    assert snapshots[0]["schema_version"] == 1
