from __future__ import annotations

import pytest
from scripts.market_compass_intraday_evidence import adapt_intraday_subsector_to_market_compass


def make_valid_payload() -> dict:
    return {
        "schema_version": 1,
        "observed_at": "2026-08-20T09:30:00Z",
        "source": "tse_intraday_feed",
        "freshness": "FRESH",
        "data_completeness": "COMPLETE",
        "benchmark": "TOPIX",
        "sector": {
            "id": "sec_tech",
            "label": "Technology",
            "medium_term_regime": "EXPANSION",
        },
        "subsector": {
            "id": "sub_semi_equip",
            "label": "Semiconductor Equipment",
            "taxonomy_version": "v1.2",
            "as_of": "2026-08-20T09:30:00Z",
            "source_or_authority": "TSE_TAXONOMY_V1",
        },
        "observations": {
            "intraday_return": 0.025,
            "benchmark_return": 0.005,
            "relative_return": 0.020,
            "rising_count": 8,
            "constituent_count": 10,
            "breadth": 0.8,
            "median_constituent_return": 0.022,
            "turnover_ratio": 1.15,
            "concentration_top1": 0.35,
        },
        "leaders": [
            {
                "security_code": "8035",
                "name": "Tokyo Electron",
                "intraday_return": 0.031,
            }
        ],
        "flow_state": "UNKNOWN",
        "acceleration_state": "UNKNOWN",
    }


def test_adapt_fresh_complete_payload():
    payload = make_valid_payload()
    result = adapt_intraday_subsector_to_market_compass(payload)

    assert result["schema_version"] == 1
    assert result["subsector"]["id"] == "sub_semi_equip"
    assert result["data_quality"]["freshness"] == "FRESH"
    assert result["data_quality"]["data_completeness"] == "COMPLETE"
    assert result["data_quality"]["status"] == "PASS"
    assert result["data_quality"]["is_fail_closed"] is False
    assert result["metrics"]["relative_return"] == 0.020
    assert result["metrics"]["breadth"] == 0.8
    assert result["investment_authority"] == "READ_ONLY_EVIDENCE"
    assert result["trade_recommendation"] is None


def test_adapt_stale_payload_fails_closed():
    payload = make_valid_payload()
    payload["freshness"] = "STALE"
    result = adapt_intraday_subsector_to_market_compass(payload)

    assert result["data_quality"]["freshness"] == "STALE"
    assert result["data_quality"]["status"] == "STALE"
    assert result["data_quality"]["is_fail_closed"] is True


def test_adapt_partial_payload_fails_closed():
    payload = make_valid_payload()
    payload["data_completeness"] = "PARTIAL"
    result = adapt_intraday_subsector_to_market_compass(payload)

    assert result["data_quality"]["data_completeness"] == "PARTIAL"
    assert result["data_quality"]["status"] == "PARTIAL"
    assert result["data_quality"]["is_fail_closed"] is True


def test_adapt_unknown_payload_fails_closed():
    payload = make_valid_payload()
    payload["freshness"] = "UNKNOWN"
    result = adapt_intraday_subsector_to_market_compass(payload)

    assert result["data_quality"]["freshness"] == "UNKNOWN"
    assert result["data_quality"]["status"] == "UNKNOWN"
    assert result["data_quality"]["is_fail_closed"] is True


def test_invalid_payload_raises():
    payload = make_valid_payload()
    payload["observations"]["intraday_return"] = "INVALID"
    with pytest.raises(ValueError):
        adapt_intraday_subsector_to_market_compass(payload)


def test_missing_nested_key_raises_value_error_fail_closed():
    payload = make_valid_payload()
    del payload["subsector"]["id"]
    with pytest.raises(ValueError, match="subsector missing required fields: id"):
        adapt_intraday_subsector_to_market_compass(payload)


def test_mock_validator_drift_raises_value_error_fail_closed(monkeypatch):
    payload = make_valid_payload()

    # Simulate validator returning an incomplete object missing a required key
    def incomplete_validator(_p):
        v = make_valid_payload()
        del v["observations"]["relative_return"]
        return v

    monkeypatch.setattr(
        "scripts.market_compass_intraday_evidence.validate_intraday_subsector_flow",
        incomplete_validator,
    )

    with pytest.raises(ValueError, match="Payload validation failed: missing required key"):
        adapt_intraday_subsector_to_market_compass(payload)
