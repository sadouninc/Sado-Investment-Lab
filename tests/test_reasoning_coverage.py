import copy
import importlib.util
from pathlib import Path

import pytest

MODULE = Path(__file__).parents[1] / "scripts" / "reasoning_coverage.py"
spec = importlib.util.spec_from_file_location("reasoning_coverage", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(mod)


def base_record():
    return {
        "security_code": "6622",
        "as_of": "2026-08-09T21:00:00+09:00",
        "canonical_refs": ["research:6622", "hypothesis:6622"],
        "sections": {
            "why_candidate": {"status": "SUPPORTED", "refs": ["candidate:6622"]},
            "business_driver": {"status": "SUPPORTED", "known": ["driver:energy"]},
            "base_scenario": {"status": "SUPPORTED", "value_ref": "forward:6622:base"},
            "bear_bull_range": {"status": "SUPPORTED"},
            "valuation": {"status": "SUPPORTED", "refs": ["forward-per:6622"]},
            "hypothesis": {"status": "SUPPORTED", "refs": ["hypothesis:6622"]},
            "invalidation": {"status": "DEFINED", "conditions": ["condition:q2-margin"]},
            "market_expectation": {"status": "SUPPORTED", "refs": ["expectation:6622"]},
            "next_evidence": {"status": "DEFINED", "items": ["event:q2"]},
        },
        "owner_uncertainties": [],
        "system_uncertainties": [],
    }


def test_all_supported_is_well_supported_and_no_trade_output():
    out = mod.project_reasoning_coverage(base_record())
    assert out["overall"] == "WELL_SUPPORTED"
    assert out["next_research_actions"] == []
    text = repr(out)
    assert "BUY" not in text and "SELL" not in text and "DO_NOT_TRADE" not in text


def test_base_partial_remains_partial_not_prohibition():
    record = base_record()
    record["sections"]["base_scenario"] = {
        "status": "PARTIAL",
        "value_ref": "forward:6622:base",
        "uncertainties": [{"text": "利益化の時間差", "provenance": "UNKNOWN"}],
    }
    out = mod.project_reasoning_coverage(record)
    assert out["overall"] == "PARTIAL"
    assert out["sections"]["base_scenario"]["status"] == "PARTIAL"


def test_invalidation_not_defined_is_research_gap():
    record = base_record()
    record["sections"]["invalidation"] = {"status": "NOT_YET_DEFINED", "conditions": []}
    out = mod.project_reasoning_coverage(record)
    assert out["overall"] == "RESEARCH_GAPS"
    assert out["sections"]["invalidation"]["status"] == "NOT_YET_DEFINED"


def test_consensus_unavailable_is_not_neutralized():
    record = base_record()
    record["sections"]["market_expectation"] = {"status": "UNAVAILABLE", "refs": []}
    out = mod.project_reasoning_coverage(record)
    assert out["overall"] == "RESEARCH_GAPS"
    assert out["sections"]["market_expectation"]["status"] == "UNAVAILABLE"


def test_conflicting_source_dominates_overall():
    record = base_record()
    record["sections"]["hypothesis"] = {"status": "CONFLICTING", "refs": ["source:a", "source:b"]}
    assert mod.project_reasoning_coverage(record)["overall"] == "CONFLICTING"


def test_owner_uncertainty_must_be_owner_entered_provenance():
    record = base_record()
    record["owner_uncertainties"] = [{"text": "Base +5億への自信", "provenance": "OWNER_ASSUMPTION"}]
    out = mod.project_reasoning_coverage(record)
    assert out["owner_uncertainties"][0]["provenance"] == "OWNER_ASSUMPTION"
    record["owner_uncertainties"][0]["provenance"] = "SYSTEM_DERIVED"
    with pytest.raises(mod.ReasoningCoverageError):
        mod.project_reasoning_coverage(record)


def test_stale_valuation_remains_stale():
    record = base_record()
    record["sections"]["valuation"] = {"status": "STALE", "refs": ["price:old"]}
    out = mod.project_reasoning_coverage(record)
    assert out["overall"] == "PARTIAL"
    assert out["sections"]["valuation"]["status"] == "STALE"


def test_owner_assumption_is_not_promoted_to_supported():
    record = base_record()
    record["sections"]["base_scenario"] = {
        "status": "OWNER_ASSUMPTION",
        "value_ref": "owner-scenario:6622",
        "assumption_refs": ["owner-note:1"],
    }
    out = mod.project_reasoning_coverage(record)
    assert out["overall"] == "PARTIAL"
    assert out["sections"]["base_scenario"]["status"] == "OWNER_ASSUMPTION"


def test_deterministic_and_non_mutating():
    record = base_record()
    record["canonical_refs"] = ["z", "a", "a"]
    before = copy.deepcopy(record)
    first = mod.project_reasoning_coverage(record)
    second = mod.project_reasoning_coverage(record)
    assert first == second
    assert first["canonical_refs"] == ["a", "z"]
    assert record == before


def test_supplied_overall_cannot_override_projection():
    record = base_record()
    record["overall"] = "RESEARCH_GAPS"
    with pytest.raises(mod.ReasoningCoverageError):
        mod.project_reasoning_coverage(record)
