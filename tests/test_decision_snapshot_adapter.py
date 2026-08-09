from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.decision_snapshot_adapter import (
    DecisionSnapshotAdapterError,
    build_decision_snapshot_bundle,
    capture_decision_snapshot_bundle,
)
from scripts.investment_decision_journal import validate_decision


def decision(*, retrospective: bool = False):
    return validate_decision(
        {
            "security_code": "6622",
            "decided_at": "2026-08-09T10:30:00+09:00",
            "decision": "BUY",
            "actor": "SADO",
            "confidence": "MEDIUM",
            "owner_judgment": {
                "why_now": "Q1後のResearchを確認した",
                "biggest_risk": "需要鈍化",
                "what_changes_my_mind": "受注が明確に悪化する",
            },
            "system_snapshot": {},
            "evidence_refs": [],
            "retrospective_note": retrospective,
        }
    )


def rec(component_ref, observed_at, data, *, security_code="6622"):
    return {
        "ref": component_ref,
        "security_code": security_code,
        "observed_at": observed_at,
        "data": data,
    }


def complete_sources():
    return {
        "portfolio": [
            rec(
                "portfolio:2026-08-09T10:00",
                "2026-08-09T10:00:00+09:00",
                {
                    "position_state": "OWNED",
                    "quantity": 100,
                    "account_context": "CASH",
                    "as_of": "2026-08-09T10:00:00+09:00",
                    "freshness": "CURRENT",
                },
            )
        ],
        "market_price": [
            rec(
                "price:6622:2026-08-09T10:20",
                "2026-08-09T10:20:00+09:00",
                {
                    "value": 12000.0,
                    "as_of": "2026-08-09T10:20:00+09:00",
                    "status": "CURRENT",
                },
            )
        ],
        "research": [
            rec(
                "research:6622:v3",
                "2026-08-09T09:30:00+09:00",
                {"status": "CURRENT"},
            )
        ],
        "valuation": [
            rec(
                "valuation:6622:v3",
                "2026-08-09T09:40:00+09:00",
                {
                    "bear": 20.8,
                    "base": 16.5,
                    "bull": 14.1,
                    "target_fiscal_year": "FY2027",
                    "price_as_of": "2026-08-09T09:35:00+09:00",
                    "warnings": [],
                },
            )
        ],
        "hypothesis": [
            rec(
                "hypothesis:6622:v2",
                "2026-08-09T09:45:00+09:00",
                {
                    "health": "INTACT",
                    "must_happen": ["データセンター需要継続"],
                    "invalidation_conditions": ["受注急減"],
                    "next_checkpoints": ["FY2027-Q2"],
                },
            )
        ],
        "expectations": [
            rec(
                "expectation:6622:pre-decision",
                "2026-08-09T10:10:00+09:00",
                {
                    "status": "OK",
                    "company_guidance_ref": "guidance:6622:FY2027",
                    "external_consensus_ref": "consensus:6622:2026-08-09T10:10",
                    "sado_scenario_ref": "research:6622:v3",
                },
            )
        ],
        "risk_preflight": [
            rec(
                "risk:6622:2026-08-09T10:25",
                "2026-08-09T10:25:00+09:00",
                {"status": "WARN"},
            )
        ],
        "evidence": [
            rec(
                "fact:6622:orders:q1",
                "2026-08-09T09:00:00+09:00",
                {"relation": "REFERENCES"},
            )
        ],
        "checkpoints": [
            rec(
                "event:6622:q2-results",
                "2026-08-09T08:00:00+09:00",
                {"status": "SCHEDULED"},
            )
        ],
        "opportunity_set": [
            rec(
                "opp:for-decision",
                "2026-08-09T10:29:00+09:00",
                {"decision_ref": decision()["decision_id"]},
            )
        ],
    }


def test_complete_decision_time_bundle():
    result = build_decision_snapshot_bundle(decision(), sources=complete_sources())
    assert result["snapshot_status"] == "COMPLETE"
    assert result["portfolio"]["quantity"] == 100
    assert result["valuation"]["base"] == 16.5
    assert result["hypothesis"]["health"] == "INTACT"
    assert result["expectations"]["external_consensus_ref"].startswith("consensus:")
    assert result["risk_preflight"]["status"] == "WARN"
    assert result["evidence_refs"] == ["fact:6622:orders:q1"]
    assert result["checkpoint_refs"] == ["event:6622:q2-results"]
    assert result["opportunity_set_ref"] == "opp:for-decision"


def test_missing_consensus_remains_partial():
    sources = complete_sources()
    sources["expectations"] = []
    result = build_decision_snapshot_bundle(decision(), sources=sources)
    assert result["snapshot_status"] == "PARTIAL"
    assert result["expectations"]["status"] == "UNAVAILABLE"
    assert "expectations" in result["missing_components"]


def test_latest_before_decision_excludes_future_research():
    sources = complete_sources()
    sources["research"].append(
        rec("research:6622:future", "2026-08-09T11:00:00+09:00", {"status": "CURRENT"})
    )
    result = build_decision_snapshot_bundle(decision(), sources=sources)
    assert result["research"]["ref"] == "research:6622:v3"
    assert "research:6622:future" not in result["source_refs"]


def test_post_decision_consensus_revision_does_not_leak():
    sources = complete_sources()
    sources["expectations"].append(
        rec(
            "expectation:6622:post-decision",
            "2026-08-09T10:31:00+09:00",
            {"status": "OK", "external_consensus_ref": "consensus:new"},
        )
    )
    result = build_decision_snapshot_bundle(decision(), sources=sources)
    assert result["expectations"]["ref"] == "expectation:6622:pre-decision"


def test_stale_portfolio_is_preserved_not_promoted_to_current():
    sources = complete_sources()
    sources["portfolio"][0]["data"]["freshness"] = "STALE"
    result = build_decision_snapshot_bundle(decision(), sources=sources)
    assert result["portfolio"]["freshness"] == "STALE"


def test_risk_unknown_and_not_run_are_distinct():
    sources = complete_sources()
    sources["risk_preflight"][0]["data"]["status"] = "UNKNOWN"
    assert build_decision_snapshot_bundle(decision(), sources=sources)["risk_preflight"]["status"] == "UNKNOWN"
    sources["risk_preflight"] = []
    assert build_decision_snapshot_bundle(decision(), sources=sources)["risk_preflight"]["status"] == "NOT_RUN"


def test_retrospective_note_does_not_backfill_from_current_future_data():
    sources = {
        "research": [
            rec("research:6622:current", "2026-08-09T12:00:00+09:00", {"status": "CURRENT"})
        ]
    }
    result = build_decision_snapshot_bundle(decision(retrospective=True), sources=sources)
    assert result["research"] == {"ref": None, "status": "MISSING"}
    assert result["snapshot_status"] == "UNKNOWN"


def test_same_input_rerun_is_idempotent_and_conflict_is_rejected():
    bundle = build_decision_snapshot_bundle(decision(), sources=complete_sources())
    assert capture_decision_snapshot_bundle(bundle, bundle) == bundle
    changed = deepcopy(bundle)
    changed["research"]["ref"] = "research:rewritten"
    with pytest.raises(DecisionSnapshotAdapterError, match="immutable"):
        capture_decision_snapshot_bundle(changed, bundle)


def test_adapter_rejects_owner_field_generation():
    sources = complete_sources()
    sources["research"][0]["owner_judgment"] = {"why_now": "invented"}
    with pytest.raises(DecisionSnapshotAdapterError, match="owner decision"):
        build_decision_snapshot_bundle(decision(), sources=sources)


def test_source_without_event_time_does_not_use_date_only_as_of():
    sources = complete_sources()
    sources["research"] = [
        {
            "ref": "research:date-only",
            "security_code": "6622",
            "data": {"status": "CURRENT", "as_of": "2026-08-09"},
        }
    ]
    with pytest.raises(DecisionSnapshotAdapterError, match="date-only as_of"):
        build_decision_snapshot_bundle(decision(), sources=sources)


def test_opportunity_set_absence_stays_null():
    sources = complete_sources()
    sources["opportunity_set"] = []
    result = build_decision_snapshot_bundle(decision(), sources=sources)
    assert result["opportunity_set_ref"] is None


def test_inputs_are_not_mutated():
    original_decision = decision()
    sources = complete_sources()
    before_decision = deepcopy(original_decision)
    before_sources = deepcopy(sources)
    build_decision_snapshot_bundle(original_decision, sources=sources)
    assert original_decision == before_decision
    assert sources == before_sources
