import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.intraday_subsector_flow import validate_intraday_subsector_flow

FIXTURES = Path("data/fixtures/intraday-subsector-flow-v1.json")


def cases():
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


def test_three_product_fixtures_validate_without_classification():
    validated = [validate_intraday_subsector_flow(item) for item in cases()]
    assert len(validated) == 3
    assert all(item["flow_state"] == "UNKNOWN" for item in validated)
    assert all(item["acceleration_state"] == "UNKNOWN" for item in validated)


def test_medium_term_sector_regime_and_intraday_subsector_observation_coexist():
    item = validate_intraday_subsector_flow(cases()[0])
    assert item["sector"]["medium_term_regime"] == "COLD"
    assert item["subsector"]["label"] == "Biotechnology"
    assert item["observations"]["breadth"] == 0.8
    assert item["leaders"][0]["security_code"] == "4588"


def test_relative_return_is_reproducible_from_raw_inputs():
    item = validate_intraday_subsector_flow(cases()[0])
    obs = item["observations"]
    assert obs["relative_return"] == pytest.approx(
        obs["intraday_return"] - obs["benchmark_return"]
    )


def test_breadth_must_be_derived_from_counts():
    item = deepcopy(cases()[0])
    item["observations"]["breadth"] = 0.7
    with pytest.raises(ValueError, match="breadth must equal"):
        validate_intraday_subsector_flow(item)


def test_partial_stale_keeps_missing_values_null_not_zero():
    item = validate_intraday_subsector_flow(cases()[2])
    assert item["freshness"] == "STALE"
    assert item["data_completeness"] == "PARTIAL"
    assert item["observations"]["breadth"] is None
    assert item["observations"]["turnover_ratio"] is None
    assert item["observations"]["relative_return"] is None


def test_missing_raw_returns_cannot_have_synthetic_relative_return():
    item = deepcopy(cases()[2])
    item["observations"]["relative_return"] = 0
    with pytest.raises(ValueError, match="relative_return must be null"):
        validate_intraday_subsector_flow(item)


def test_pr1_cannot_set_investment_significant_flow_threshold_state():
    item = deepcopy(cases()[0])
    item["flow_state"] = "STRONG_INFLOW"
    with pytest.raises(ValueError, match="must remain UNKNOWN"):
        validate_intraday_subsector_flow(item)


def test_taxonomy_provenance_is_required_without_creating_parallel_membership():
    item = deepcopy(cases()[0])
    item["subsector"]["source_or_authority"] = ""
    with pytest.raises(ValueError, match="source_or_authority"):
        validate_intraday_subsector_flow(item)
