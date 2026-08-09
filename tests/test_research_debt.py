from copy import deepcopy

import pytest

from scripts.research_debt import ResearchDebtError, project_debt_candidates, validate_debt


def coverage_fixture():
    return {
        "security_code": "6622",
        "as_of": "2026-08-09T14:00:00+09:00",
        "canonical_refs": ["company-research:6622:current"],
        "owner_uncertainties": [],
        "system_uncertainties": [],
        "sections": {
            "why_candidate": {"status": "SUPPORTED", "refs": ["candidate:6622"]},
            "business_driver": {"status": "SUPPORTED", "refs": ["research:6622:driver"]},
            "base_scenario": {
                "status": "OWNER_ASSUMPTION",
                "assumption_refs": ["scenario:6622:base"],
                "uncertainties": [
                    {"text": "Energy Management受注残の売上化速度を確認する", "provenance": "OWNER_ASSUMPTION"}
                ],
            },
            "bear_bull_range": {"status": "PARTIAL", "refs": ["scenario:6622:range"]},
            "valuation": {"status": "STALE", "refs": ["valuation:6622"]},
            "hypothesis": {"status": "NOT_YET_DEFINED"},
            "invalidation": {"status": "NOT_YET_DEFINED"},
            "market_expectation": {"status": "UNAVAILABLE"},
            "next_evidence": {"status": "DEFINED", "refs": ["checkpoint:6622:q2"]},
        },
    }


def test_maps_explicit_uncertainties_without_inference():
    source = coverage_fixture()
    result = project_debt_candidates(source)
    assert [row["section"] for row in result] == [
        "base_scenario",
        "bear_bull_range",
        "valuation",
        "hypothesis",
        "invalidation",
        "market_expectation",
    ]
    base = result[0]
    assert base["origin_type"] == "OWNER_ASSUMPTION"
    assert base["origin_ref"] == "scenario:6622:base"
    assert "Energy Management" in base["question"]
    assert base["materiality"] is None
    assert base["status"] == "OPEN"
    assert base["trade_recommendation"] is None


def test_supported_and_defined_sections_do_not_create_debt():
    source = coverage_fixture()
    for name, section in source["sections"].items():
        if name in {"invalidation", "next_evidence"}:
            section["status"] = "DEFINED"
        elif name == "hypothesis":
            section["status"] = "SUPPORTED"
        elif name == "market_expectation":
            section["status"] = "SUPPORTED"
        elif name == "valuation":
            section["status"] = "SUPPORTED"
        elif name == "base_scenario":
            section.clear(); section.update({"status": "SUPPORTED"})
        else:
            section["status"] = "SUPPORTED"
    assert project_debt_candidates(source) == []


def test_deterministic_non_mutating_projection():
    source = coverage_fixture()
    before = deepcopy(source)
    first = project_debt_candidates(source)
    second = project_debt_candidates(source)
    assert first == second
    assert source == before
    assert len({row["debt_id"] for row in first}) == len(first)


def test_waiting_is_not_negative_or_trade_block():
    record = validate_debt(
        {
            "security_code": "6622",
            "section": "base_scenario",
            "question": "次回決算で受注売上転換を確認する",
            "origin_type": "OWNER_ASSUMPTION",
            "origin_ref": "scenario:6622:base",
            "created_at": "2026-08-09T14:00:00+09:00",
            "materiality": "HIGH",
            "expected_evidence": [
                {
                    "type": "EARNINGS",
                    "description": "Q2 segment order/revenue",
                    "not_before": "2026-11-01",
                    "expected_by": "2026-11-10",
                }
            ],
            "status": "WAITING_FOR_EVIDENCE",
        }
    )
    assert record["status"] == "WAITING_FOR_EVIDENCE"
    assert record["trade_recommendation"] is None


def test_resolved_requires_auditable_resolution():
    base = {
        "security_code": "6622",
        "section": "valuation",
        "question": "Valuationを更新する",
        "origin_type": "STALE",
        "origin_ref": "valuation:6622",
        "created_at": "2026-08-09T14:00:00+09:00",
        "materiality": "MEDIUM",
        "expected_evidence": [],
        "status": "RESOLVED",
    }
    with pytest.raises(ResearchDebtError):
        validate_debt(base)
    base.update(
        {
            "resolved_at": "2026-08-10T09:00:00+09:00",
            "resolution_ref": "valuation:6622:2026-08-10",
            "resolution": "最新Valuationで再確認済み",
        }
    )
    assert validate_debt(base)["status"] == "RESOLVED"


def test_non_resolved_cannot_smuggle_resolution_fields():
    with pytest.raises(ResearchDebtError):
        validate_debt(
            {
                "security_code": "6622",
                "section": "hypothesis",
                "question": "仮説を確認する",
                "origin_type": "NOT_YET_DEFINED",
                "origin_ref": "reasoning-coverage:6622:hypothesis",
                "created_at": "2026-08-09T14:00:00+09:00",
                "materiality": None,
                "expected_evidence": [],
                "status": "OPEN",
                "resolution": "後付け解消",
            }
        )


def test_materiality_is_not_inferred_from_origin_status():
    result = project_debt_candidates(coverage_fixture())
    assert all(row["materiality"] is None for row in result)


def test_no_buy_sell_or_do_not_trade_output():
    payload = str(project_debt_candidates(coverage_fixture()))
    assert "BUY" not in payload
    assert "SELL" not in payload
    assert "DO_NOT_TRADE" not in payload
