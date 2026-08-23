from copy import deepcopy

import pytest

import scripts.market_compass_universe_projection as projection


def _portfolio(as_of="2026-08-08", code="6702"):
    return {
        "as_of": as_of,
        "verification_status": "VERIFIED",
        "positions": [{"security_code": code, "security_name": "富士通", "quantity": 100}],
    }


def _watch(exit_date="2026-08-12", code="6702"):
    return {"candidates": [{"security_code": code, "name": "富士通", "exit_date": exit_date}]}


def _pass_evidence(code, as_of, expected_taxonomy_version, payload, mapping):
    return {"security_code": code, "status": "PASS", "reason": None}


def test_snapshot_after_confirmed_exit_projects_reentry_only(monkeypatch):
    monkeypatch.setattr(projection, "resolve_security_intraday_evidence", _pass_evidence)
    result = projection.project_market_compass_universe(
        _portfolio(), _watch(), {"6702": {}}, evidence_as_of="2026-08-21", expected_taxonomy_version="v1"
    )
    assert result["current_holdings"] == []
    assert [row["security_code"] for row in result["reentry_watch"]] == ["6702"]
    assert result["reentry_watch"][0]["portfolio_authority_status"] == "STALE_RELATIVE_TO_EXIT"


def test_newer_holding_snapshot_projects_current_only(monkeypatch):
    monkeypatch.setattr(projection, "resolve_security_intraday_evidence", _pass_evidence)
    result = projection.project_market_compass_universe(
        _portfolio(as_of="2026-08-15"), _watch(), {"6702": {}}, evidence_as_of="2026-08-21", expected_taxonomy_version="v1"
    )
    assert [row["security_code"] for row in result["current_holdings"]] == ["6702"]
    assert result["reentry_watch"] == []


def test_unverified_position_only_fails_membership_closed(monkeypatch):
    monkeypatch.setattr(projection, "resolve_security_intraday_evidence", _pass_evidence)
    portfolio = _portfolio()
    portfolio["verification_status"] = "UNKNOWN"
    result = projection.project_market_compass_universe(
        portfolio, {}, {"6702": {}}, evidence_as_of="2026-08-21", expected_taxonomy_version="v1"
    )
    assert result["current_holdings"] == []
    assert result["membership_unknown"][0]["membership"] == "MEMBERSHIP_UNKNOWN"
    assert result["membership_unknown"][0]["portfolio_authority_status"] == "UNKNOWN"


def test_missing_verification_status_position_only_fails_membership_closed(monkeypatch):
    monkeypatch.setattr(projection, "resolve_security_intraday_evidence", _pass_evidence)
    portfolio = _portfolio()
    del portfolio["verification_status"]
    result = projection.project_market_compass_universe(
        portfolio, {}, {"6702": {}}, evidence_as_of="2026-08-21", expected_taxonomy_version="v1"
    )
    assert result["current_holdings"] == []
    assert result["membership_unknown"][0]["membership"] == "MEMBERSHIP_UNKNOWN"
    assert result["membership_unknown"][0]["portfolio_authority_status"] == "UNKNOWN"


def test_unverified_stale_snapshot_still_yields_confirmed_reentry(monkeypatch):
    monkeypatch.setattr(projection, "resolve_security_intraday_evidence", _pass_evidence)
    portfolio = _portfolio()
    portfolio["verification_status"] = "UNKNOWN"
    result = projection.project_market_compass_universe(
        portfolio, _watch(), {"6702": {}}, evidence_as_of="2026-08-21", expected_taxonomy_version="v1"
    )
    assert result["current_holdings"] == []
    assert [row["security_code"] for row in result["reentry_watch"]] == ["6702"]
    assert result["reentry_watch"][0]["portfolio_authority_status"] == "STALE_RELATIVE_TO_EXIT"


def test_uncomparable_temporal_authority_fails_membership_closed(monkeypatch):
    monkeypatch.setattr(projection, "resolve_security_intraday_evidence", _pass_evidence)
    result = projection.project_market_compass_universe(
        _portfolio(as_of="not-a-date"), _watch(), {"6702": {}}, evidence_as_of="2026-08-21", expected_taxonomy_version="v1"
    )
    assert result["current_holdings"] == []
    assert result["reentry_watch"] == []
    assert result["membership_unknown"][0]["membership"] == "MEMBERSHIP_UNKNOWN"


def test_missing_evidence_is_per_security_unknown_and_inputs_immutable(monkeypatch):
    monkeypatch.setattr(projection, "resolve_security_intraday_evidence", _pass_evidence)
    portfolio = _portfolio(code="1321")
    watch = _watch(code="6702")
    before = (deepcopy(portfolio), deepcopy(watch))
    result = projection.project_market_compass_universe(
        portfolio, watch, {}, evidence_as_of="2026-08-21", expected_taxonomy_version="v1"
    )
    rows = result["current_holdings"] + result["reentry_watch"]
    assert [row["security_code"] for row in rows] == ["1321", "6702"]
    assert all(row["intraday_evidence"]["status"] == "UNKNOWN" for row in rows)
    assert portfolio == before[0]
    assert watch == before[1]


def test_expected_resolver_value_error_fails_closed(monkeypatch):
    def fail(*args, **kwargs):
        raise ValueError("invalid authority input")

    monkeypatch.setattr(projection, "resolve_security_intraday_evidence", fail)
    result = projection.project_market_compass_universe(
        _portfolio(), {}, {"6702": {}}, evidence_as_of="2026-08-21", expected_taxonomy_version="v1"
    )
    evidence = result["current_holdings"][0]["intraday_evidence"]
    assert evidence["status"] == "UNKNOWN"
    assert evidence["reason"] == "RESOLVER_FAILURE"


def test_expected_resolver_type_error_fails_closed(monkeypatch):
    def fail(*args, **kwargs):
        raise TypeError("malformed resolver input")

    monkeypatch.setattr(projection, "resolve_security_intraday_evidence", fail)
    result = projection.project_market_compass_universe(
        _portfolio(), {}, {"6702": {}}, evidence_as_of="2026-08-21", expected_taxonomy_version="v1"
    )
    evidence = result["current_holdings"][0]["intraday_evidence"]
    assert evidence["status"] == "UNKNOWN"
    assert evidence["reason"] == "RESOLVER_FAILURE"


def test_unexpected_resolver_key_error_is_not_masked(monkeypatch):
    def fail(*args, **kwargs):
        raise KeyError("unexpected implementation defect")

    monkeypatch.setattr(projection, "resolve_security_intraday_evidence", fail)
    with pytest.raises(KeyError, match="unexpected implementation defect"):
        projection.project_market_compass_universe(
            _portfolio(), {}, {"6702": {}}, evidence_as_of="2026-08-21", expected_taxonomy_version="v1"
        )


def test_w33_stale_snapshot_does_not_override_confirmed_exits(monkeypatch):
    monkeypatch.setattr(projection, "resolve_security_intraday_evidence", _pass_evidence)
    codes = ["3778", "4588", "5801", "6702"]
    portfolio = {
        "as_of": "2026-08-08",
        "verification_status": "VERIFIED",
        "positions": [{"security_code": code, "security_name": code} for code in codes],
    }
    watch = {
        "candidates": [
            {"security_code": "3778", "exit_date": "2026-08-14"},
            {"security_code": "4588", "exit_date": "2026-08-13"},
            {"security_code": "5801", "exit_date": "2026-08-13"},
            {"security_code": "6702", "exit_date": "2026-08-12"},
        ]
    }
    result = projection.project_market_compass_universe(
        portfolio, watch, {code: {} for code in codes}, evidence_as_of="2026-08-21", expected_taxonomy_version="v1"
    )
    assert result["current_holdings"] == []
    assert [row["security_code"] for row in result["reentry_watch"]] == codes


def test_schema_bridge_preserves_evaluator_fields_and_source_refs(monkeypatch):
    monkeypatch.setattr(projection, "resolve_security_intraday_evidence", _pass_evidence)
    portfolio = {
        "as_of": "2026-08-08",
        "verification_status": "VERIFIED",
        "base_snapshot": "verified-2026-08-08",
        "authority": "sbi_verified_position_snapshot",
        "source_references": {"snapshot_id": "verified-2026-08-08"},
        "positions": [
            {
                "security_code": "6622",
                "security_name": "ダイヘン",
                "fundamental_integrity": "PASS",
                "excess_decline_score": 15,
                "valuation_reset_score": 20,
                "fundamental_strength_score": 25,
                "risk_stabilization_score": 10,
                "confidence": "HIGH",
            }
        ],
    }
    watch = {
        "candidates": [
            {
                "security_code": "6376",
                "name": "日機装",
                "exit_date": "2026-08-14",
                "fundamental_integrity": "PASS",
                "fundamental_strength_score": 25,
                "notes": "Strongest candidate",
                "fundamental_evidence": {"thesis": "STRENGTHENING"},
            }
        ]
    }
    result = projection.project_market_compass_universe(
        portfolio, watch, {}, evidence_as_of="2026-08-21", expected_taxonomy_version="v1"
    )
    assert result["portfolio_base_snapshot"] == "verified-2026-08-08"
    assert result["portfolio_source_references"] == {"snapshot_id": "verified-2026-08-08"}

    holding = result["current_holdings"][0]
    assert holding["fundamental_integrity"] == "PASS"
    assert holding["scores"] == {
        "excess_decline": 15,
        "valuation_reset": 20,
        "fundamental_strength": 25,
        "risk_stabilization": 10,
    }
    assert holding["confidence"] == "HIGH"

    reentry = result["reentry_watch"][0]
    assert reentry["fundamental_integrity"] == "PASS"
    assert reentry["scores"] == {
        "excess_decline": None,
        "valuation_reset": None,
        "fundamental_strength": 25,
        "risk_stabilization": None,
    }
    assert reentry["notes"] == "Strongest candidate"
    assert reentry["fundamental_evidence"] == {"thesis": "STRENGTHENING"}
