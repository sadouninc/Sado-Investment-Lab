from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / ".github" / "pages" / "scenario_delta.py"
spec = importlib.util.spec_from_file_location("scenario_delta", MODULE_PATH)
assert spec and spec.loader
scenario_delta = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = scenario_delta
spec.loader.exec_module(scenario_delta)

ScenarioSnapshot = scenario_delta.ScenarioSnapshot
build_scenario_delta = scenario_delta.build_scenario_delta


def test_previous_snapshot_is_not_mutated() -> None:
    previous = ScenarioSnapshot("Base", eps=100.0, price=1000.0, forward_per=10.0, premise="前回前提")
    current = ScenarioSnapshot("Bull", eps=120.0, price=1500.0, forward_per=12.5, premise="現在前提")
    before = copy.deepcopy(previous)

    result = build_scenario_delta(previous, current)

    assert previous == before
    assert result.previous == before
    assert result.current == current


def test_business_improves_but_price_runs_ahead() -> None:
    previous = ScenarioSnapshot("Base", eps=100.0, price=1000.0, forward_per=10.0)
    current = ScenarioSnapshot("Bull", eps=120.0, price=1500.0, forward_per=12.5)

    result = build_scenario_delta(previous, current)

    assert result.earnings_direction == "IMPROVED"
    assert result.price_direction == "IMPROVED"
    assert result.valuation_direction == "NARROWED"
    assert result.scenario_transition == "Base→Bull"
    assert "業績見通しは改善" in result.summary_ja
    assert "valuation余地は縮小" in result.summary_ja


def test_lower_forward_per_expands_valuation_headroom() -> None:
    previous = ScenarioSnapshot("Base", eps=100.0, price=1200.0, forward_per=12.0)
    current = ScenarioSnapshot("Base", eps=120.0, price=1200.0, forward_per=10.0)

    result = build_scenario_delta(previous, current)

    assert result.earnings_direction == "IMPROVED"
    assert result.price_direction == "UNCHANGED"
    assert result.valuation_direction == "EXPANDED"
    assert result.scenario_transition == "Base維持"


def test_missing_values_fail_closed_as_unknown() -> None:
    previous = ScenarioSnapshot("Base", eps=100.0, price=1000.0, forward_per=10.0)
    current = ScenarioSnapshot("UNKNOWN", eps=None, price=1100.0, forward_per=None)

    result = build_scenario_delta(previous, current)

    assert result.earnings_direction == "UNKNOWN"
    assert result.price_direction == "IMPROVED"
    assert result.valuation_direction == "UNKNOWN"
    assert result.scenario_transition == "UNKNOWN"
    assert result.summary_ja == "前回との差分を確定するための情報が不足しています。"
