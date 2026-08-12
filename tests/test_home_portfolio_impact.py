from __future__ import annotations

from copy import deepcopy

from scripts.home_portfolio_impact import project_portfolio_impact


def test_projects_canonical_holdings_without_inventing_impact():
    dataset = {
        "source_status": [
            {
                "name": "portfolio",
                "status": "OK",
                "as_of": "2026-08-12",
                "source_reference": "data/canonical/portfolio-state.json",
            }
        ],
        "portfolio": {
            "positions": [
                {"security_code": "6622", "name": "ダイヘン", "quantity": 100},
                {"security_code": "3110", "name": "日東紡", "quantity": 200},
            ]
        },
    }
    before = deepcopy(dataset)

    result = project_portfolio_impact(dataset)

    assert result["status"] == "OK"
    assert result["as_of"] == "2026-08-12"
    assert [row["security_code"] for row in result["positions"]] == ["6622", "3110"]
    assert result["impact_state"] == "UNKNOWN"
    assert "未接続" in result["impact_reason"]
    assert "BUY/SELL" in result["impact_reason"]
    assert dataset == before


def test_stale_holdings_remain_visible_but_not_promoted_to_current():
    dataset = {
        "source_status": [
            {"name": "portfolio", "status": "STALE", "as_of": "2026-08-01", "reason": "snapshot is stale"}
        ],
        "portfolio": {"positions": [{"security_code": "6622", "name": "ダイヘン"}]},
    }

    result = project_portfolio_impact(dataset)

    assert result["status"] == "STALE"
    assert result["positions"][0]["security_code"] == "6622"
    assert result["impact_state"] == "UNKNOWN"
    assert result["reason"] == "snapshot is stale"


def test_missing_portfolio_fails_closed_without_empty_means_no_holdings():
    dataset = {
        "source_status": [
            {"name": "portfolio", "status": "MISSING", "reason": "canonical portfolio source not found"}
        ],
        "portfolio": None,
    }

    result = project_portfolio_impact(dataset)

    assert result["status"] == "MISSING"
    assert result["positions"] == []
    assert result["impact_state"] == "UNAVAILABLE"
    assert "判定しません" in result["impact_reason"]


def test_missing_source_status_fails_closed():
    result = project_portfolio_impact({"portfolio": {"positions": [{"name": "ダイヘン"}]}})

    assert result["status"] == "MISSING"
    assert result["positions"] == []
    assert result["impact_state"] == "UNAVAILABLE"
